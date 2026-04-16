from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import anthropic
import os
from supabase import create_client

app = Flask(__name__)

handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))
line_config = Configuration(access_token=os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
claude = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
supabase = create_client(
    os.environ.get('SUPABASE_URL'),
    os.environ.get('SUPABASE_KEY')
)

SYSTEM_PROMPT = """你是富永二通訊處（TP128）吳睿倫分處經理打造的專屬AI顧問，專門協助壽險業務團隊。

你的服務對象可能是：
- 新人業務員（剛入行、還在摸索）
- 資深業務員（有經驗但遇到瓶頸）
- 主管（SP/AM/UM，需要輔導技巧）
- 分處經理（組織發展、策略規劃）

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

【Coaching黃金三問】
1. 你現在卡在哪？
2. 你比較擅長什麼方式？
3. 我們一起找到你適合的方法。

回答原則：
- 使用繁體中文
- 根據對方身份調整語氣：對新人鼓勵親切，對主管專業直接
- 回答具體實用，給可以馬上執行的建議
- 適時引用實際話術或問句範例
- 每次回覆控制在1500字以內，內容多時提醒使用者繼續追問
- 優先參考【參考筆記】的內容來回答"""

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

MAX_LEN = 4500

def split_message(text):
    if len(text) <= MAX_LEN:
        return [text]
    parts = []
    while len(text) > MAX_LEN:
        split_pos = text[:MAX_LEN].rfind('\n')
        if split_pos == -1:
            split_pos = MAX_LEN
        parts.append(text[:split_pos].strip())
        text = text[split_pos:].strip()
    if text:
        parts.append(text)
    return parts

def search_notes(query, limit=5):
    try:
        # 用關鍵字搜尋相關筆記
        keywords = query[:50]
        res = supabase.table('notes').select('title,content').ilike('content', f'%{keywords[:20]}%').limit(limit).execute()
        if res.data:
            return res.data
        # 如果沒找到，用標題搜尋
        res2 = supabase.table('notes').select('title,content').limit(limit).execute()
        return res2.data if res2.data else []
    except:
        return []

def get_user(user_id):
    try:
        res = supabase.table('users').select('*').eq('user_id', user_id).execute()
        return res.data[0] if res.data else None
    except:
        return None

def save_user(user_id, identity):
    try:
        supabase.table('users').upsert({'user_id': user_id, 'identity': identity}).execute()
    except:
        pass

def get_history(user_id):
    try:
        res = supabase.table('conversations').select('role,content').eq('user_id', user_id).order('created_at').limit(20).execute()
        return [{'role': r['role'], 'content': r['content']} for r in res.data]
    except:
        return []

def save_message(user_id, role, content):
    try:
        supabase.table('conversations').insert({'user_id': user_id, 'role': role, 'content': content}).execute()
    except:
        pass

pending_replies = {}

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

    def send_reply(text):
        with ApiClient(line_config) as api_client:
            MessagingApi(api_client).reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=text)]
                )
            )

    # 處理「繼續」指令
    if user_msg in ['繼續', '繼續看', 'continue']:
        if user_id in pending_replies and pending_replies[user_id]:
            next_part = pending_replies[user_id].pop(0)
            if pending_replies[user_id]:
                next_part += '\n\n（還有更多，請回覆「繼續」）'
            send_reply(next_part)
            return

    # 從資料庫取得使用者資料
    user = get_user(user_id)

    # 第一次對話
    if not user:
        save_user(user_id, None)
        send_reply(WELCOME_MESSAGE)
        return

    # 尚未選擇身份
    if not user.get('identity'):
        identity = None
        if user_msg in IDENTITY_MAP:
            identity = IDENTITY_MAP[user_msg]
        else:
            if any(k in user_msg for k in ['新人', '剛入行']):
                identity = IDENTITY_MAP['1']
            elif any(k in user_msg for k in ['資深', '一年以上']):
                identity = IDENTITY_MAP['2']
            elif any(k in user_msg for k in ['主管', 'SP', 'AM', 'UM']):
                identity = IDENTITY_MAP['3']
            elif any(k in user_msg for k in ['經理', '分處']):
                identity = IDENTITY_MAP['4']

        if not identity:
            send_reply('請回覆數字 1、2、3 或 4 選擇你的身份，或直接說明你的狀況（例如：我是新人、我是主管）')
            return

        save_user(user_id, identity)
        greeting = f"了解！你是{identity} 👍\n\n有什麼問題都可以問我，例如：\n· 被客戶拒絕怎麼辦？\n· 七分鐘自我介紹怎麼說？\n· 問卷開發話術是什麼？\n· 業績起不來怎麼辦？\n· 財富金字塔怎麼講？"
        send_reply(greeting)
        return

    # 搜尋相關筆記
    notes = search_notes(user_msg)
    notes_context = ""
    if notes:
        notes_context = "\n\n【參考筆記】\n"
        for note in notes[:3]:
            notes_context += f"\n--- {note['title']} ---\n{note['content'][:500]}\n"

    # 正常對話
    identity = user.get('identity', '')
    history = get_history(user_id)

    # 把筆記內容加進使用者的問題裡
    enriched_msg = user_msg + notes_context
    history.append({'role': 'user', 'content': enriched_msg})
    save_message(user_id, 'user', user_msg)

    try:
        response = claude.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=1500,
            system=SYSTEM_PROMPT + f'\n\n【本次服務對象：{identity}】請根據此身份調整回答的深度與語氣。',
            messages=history
        )
        reply_text = response.content[0].text
        save_message(user_id, 'assistant', reply_text)
    except Exception as e:
        reply_text = '抱歉，目前服務暫時無法使用，請稍後再試。'

    parts = split_message(reply_text)
    if len(parts) > 1:
        pending_replies[user_id] = parts[1:]
        send_reply(parts[0] + '\n\n（內容較長，請回覆「繼續」看下一部分）')
    else:
        send_reply(reply_text)

@app.route('/')
def index():
    return '富永二 Coaching Bot 運行中！'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
