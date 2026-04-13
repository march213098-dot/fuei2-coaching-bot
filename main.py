from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import anthropic
import os

app = Flask(__name__)

handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))
line_config = Configuration(access_token=os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
claude = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

SYSTEM_PROMPT = """你是富永二通訊處（TP128）吳睿倫分處經理打造的專屬AI顧問，專門協助壽險業務團隊。

你的服務對象可能是：
- 新人業務員（剛入行、還在摸索）
- 資深業務員（有經驗但遇到瓶頸）
- 主管（SP/AM/UM，需要輔導技巧）
- 分處經理（組織發展、策略規劃）

你熟悉以下核心知識：

【輔導三架構】
1. 績效輔導：活動量管理→開發能力→客戶經營→成交
2. 職涯發展輔導：新人90天計畫、晉升路徑（SP→AM→UM→分處經理）
3. 心靈輔導：挫折陪伴、動機確認、低潮支持

【主管八大輔導盲點】
1. 期待過高未建立動機
2. 思考頻率不同產生誤解
3. 情緒帶入輔導
4. 複製自己的成功模式
5. 只看結果忽略過程
6. 過度包容或過度嚴格
7. 急著給答案讓夥伴過度依賴
8. 未建立信任就輔導

【新人90天定著】
- 第一個月生存期：活下來、賺到第一筆錢、建立節奏
- 第二個月動能期：有成交、有成就感、建立信心
- 第三個月穩定期：看見職涯方向、主動投入

【增員核心】
- 零成本創業概念
- 緣故→校園→104→隨機增員
- 增員黃金話術與拒絕處理

【Coaching黃金三問】
1. 你現在卡在哪？
2. 你比較擅長什麼方式？
3. 我們一起找到你適合的方法。

【各職級重點】
- SP：行銷50%+增員50%，建立習慣
- AM：增員30%+組織30%+輔導40%
- UM：行銷20%+增員20%+管理60%

回答原則：
- 使用繁體中文
- 根據對方身份調整語氣：對新人鼓勵親切，對主管專業直接
- 回答具體實用，給可以馬上執行的建議
- 適時引用實際話術或問句範例
- 回答長度適中，重點清楚"""

IDENTITY_MAP = {
    '1': '新人業務員（入行未滿一年）',
    '2': '資深業務員（入行一年以上）',
    '3': '主管（SP/AM/UM）',
    '4': '分處經理',
}

WELCOME_MESSAGE = """你好！我是富永二通訊處的專屬AI顧問 🤝

請問你目前的身份是？
1️⃣ 新人業務員（入行未滿一年）
2️⃣ 資深業務員（入行一年以上）
3️⃣ 主管（SP/AM/UM）
4️⃣ 分處經理

直接回覆數字就可以！"""

user_histories = {}
user_profiles = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_msg = event.message.text.strip()

    # 第一次對話
    if user_id not in user_histories:
        user_histories[user_id] = []
        user_profiles[user_id] = None
        with ApiClient(line_config) as api_client:
            MessagingApi(api_client).reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=WELCOME_MESSAGE)]
                )
            )
        return

    # 尚未選擇身份，處理數字或文字選擇
    if user_profiles[user_id] is None:
        if user_msg in IDENTITY_MAP:
            identity = IDENTITY_MAP[user_msg]
        else:
            # 模糊匹配
            identity = None
            for key, val in IDENTITY_MAP.items():
                if any(k in user_msg for k in ['新人', '剛入行']):
                    identity = IDENTITY_MAP['1']
                    break
                elif any(k in user_msg for k in ['資深', '一年以上']):
                    identity = IDENTITY_MAP['2']
                    break
                elif any(k in user_msg for k in ['主管', 'SP', 'AM', 'UM']):
                    identity = IDENTITY_MAP['3']
                    break
                elif any(k in user_msg for k in ['經理', '分處']):
                    identity = IDENTITY_MAP['4']
                    break

            if identity is None:
                with ApiClient(line_config) as api_client:
                    MessagingApi(api_client).reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="請回覆數字 1、2、3 或 4 選擇你的身份，或直接說明你的狀況（例如：我是新人、我是主管）")]
                        )
                    )
                return

        user_profiles[user_id] = identity
        greeting = f"了解！你是{identity} 👍\n\n有什麼問題都可以問我，例如：\n· 被客戶拒絕怎麼辦？\n· 不知道要找誰談保險\n· 怎麼做增員開口？\n· 業績起不來怎麼辦？"
        with ApiClient(line_config) as api_client:
            MessagingApi(api_client).reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=greeting)]
                )
            )
        return

    # 正常對話
    identity_context = f"【使用者身份：{user_profiles[user_id]}】\n\n"
    user_histories[user_id].append({
        "role": "user",
        "content": identity_context + user_msg if len(user_histories[user_id]) == 0 else user_msg
    })

    if len(user_histories[user_id]) > 20:
        user_histories[user_id] = user_histories[user_id][-20:]

    try:
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=SYSTEM_PROMPT + f"\n\n【本次服務對象：{user_profiles[user_id]}】請根據此身份調整回答的深度與語氣。",
            messages=user_histories[user_id]
        )
        reply_text = response.content[0].text
        user_histories[user_id].append({"role": "assistant", "content": reply_text})
    except Exception as e:
        reply_text = "抱歉，目前服務暫時無法使用，請稍後再試。"

    with ApiClient(line_config) as api_client:
        MessagingApi(api_client).reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

@app.route("/")
def index():
    return "富永二 Coaching Bot 運行中！"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
