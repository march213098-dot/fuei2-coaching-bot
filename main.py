from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import anthropic
import os
import json
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

【鍾偉成講師核心知識庫】

■ 財富金字塔（個人退休理財規劃三階段）
1. 累積期：從開始工作起，目標存到第一桶金（100-200萬）
   - 最怕的風險：收入中斷、支出增加
   - 我們的工作：幫他收入不中斷、支出不增加
   - 商品重點：重大傷病（年收兩倍）、醫療、長照、壽險（年薪十年）
2. 給付期：資產創造被動收入，讓被動>主動
   - 退休是財務問題，不是年紀問題
   - 工具：儲蓄險、分紅保單、配息型商品
3. 傳承期：照顧好自己與另一半後，規劃財富傳承
   - 要討論：留下什麼、想給誰、什麼時候給、怎麼給

■ 七分鐘自我介紹（見客戶標準流程）
見客戶流程：3W自我介紹→填市場問卷→七分鐘自我介紹（財富金字塔）→激發興趣→下Close→轉介紹

逐字稿：「你過去有接觸過其他業務員嗎？我今天會跟你過去不太一樣，我們要做的是全方位的保險規劃。你覺得保險是保障人還是保障錢？第一個階段是累積期，目標存到第一桶金。從開始工作起就進入累積期，最怕的風險是收入中斷、支出增加。累積完一桶金就進入給付期，讓資產創造被動收入，讓被動大於主動。退休是財務的問題，不是年紀的問題。當可以照顧好自己與另一半，就進入傳承期。那你現在在哪一期？那我接下來幫你介紹這部分的規劃。」

■ 銷售話術：百萬計畫
「那我接下來跟你討論人生的第一個一百萬好嗎？剩下的四百萬你自己想辦法，我只幫你規劃好第一個一百萬。」
三個選擇：6年/10年/20年 → 每月14000/8000/4000
「你存的不是錢，是你的人生選擇權。」

■ 財務三率
投資報酬率（薪水越低越在意）、薪資儲蓄率（不想多花時間就提高這個）、能力變現率（業務員最重要）
保險業務員順序：變現>儲蓄>投資

■ 賓士理論（理財金三角）
50%生活花費；10%保障；40%理財
緊急預備金三個月薪水活存；保本存第一桶金；投資中高風險

■ 問卷開發流程（NPSS）
1. 列名單：先列長輩再列同輩，目標200人
2. 電話約訪（絕對不能用Line！）：寒暄→表明來意→時間二擇一→打預防針
   話術：「主管規定我一週要填15張市場理財調查問卷...」
3. 首次面談40分鐘：寒暄→自我介紹→問卷→激發興趣→轉介紹
4. 不論成交或未成交，都要要求轉介紹

■ 轉介紹四個問句+拒絕處理
問句：「你覺得我今天分享的東西，你會有壓力嗎？」「最大的收穫是什麼？」「幫我介紹身邊三到五個朋友」（把紙跟筆推出去）
拒絕：「我沒朋友」→把LINE打開前三個是誰就寫誰；「我想一下」→這是我的工作不應該是你的回家作業

■ 年齡區分銷售策略
年齡差15歲以內：顧問、專業分、需求→談賓士理論＋理財金三角
年齡差15歲以上：業務、朋友分、議題→長輩不需要保單檢視

■ 長輩拜訪四王牌
孝順牌、努力牌、謙虛請教牌、要求牌（請長輩當貴人轉介紹）

■ Z世代輔導策略
「年輕人成功的速度取決於曝光的速度」
自媒體經營可取代傳統訪量，與其盯訪量不如看曝光量

■ 增員三階段三件事
面談時：強調願景→強調使命→創造未來
起聘時：讓他願意找緣故→認同商品制度→「做業務千萬不能低調」
輔導時：七天訓練就上戰場→教完複製不到30%先不教新的→教過不會是主管的問題

■ 高鐵vs台鐵、組織發展六步驟、留人三感、非暴力溝通、主管核心思維
高鐵每節車廂都有動力；台鐵只有頭在拉
六步驟：晉升主任→獨立面談→直轄1+5→直轄1+10→第一代六組主管→帶夥伴衝人力
留人三感：歸屬感（被看見被需要）、安全感（容錯文化）、希望感（明確職涯藍圖）
「留才的本質不是綁住人，而是人才因有我而成長」

【謝佳芳總監核心知識庫】

■ 客戶關注五大問題
1. 萬一我掛了，資產規劃是否足夠保障家人？
2. 萬一我沒掛，發生失能/長照風險，家庭該如何因應？
3. 我該如何做好儲蓄理財規劃？
4. 我該如何做好退休金規劃？
5. 我該如何做好財富傳承？

■ 保單檢視三個核心問題
1. 你清楚你現在跟上帝喝咖啡，你保障是多少？
2. 退休那一刻，這張保單能創造多少被動所得？
3. 使用醫療資源時，這張保單如何照顧你？

■ 退休規劃：財務獨立=年度基本支出×25倍（4%提領率）
基本5萬/月→目標1500萬；10萬/月→目標3000萬

■ 財富傳承：55歲是重要規劃時機
資產低於2136萬重點談贈與；5億以上預留稅源重要
保單最佳設定：要、被、生存受益人都是同一人（小孩）

■ 約訪與首次面談
約訪給客戶任務：準備已有保單、金融資產狀況
首次面談40分鐘：自我介紹→財富管理架構→保單健診→搜集財務數據→下次見面簽約
「客戶喜歡的是跟他們一樣有足夠財富的業務，而不是想靠他們變有錢的業務。」

【林沅倨講師核心知識庫】

■ 核心觀念
「你可以不賣，客戶可以不買，但我們不能不會」
有錢人只把錢放在三個地方：股票、房地產、保單

■ 房產活化
「如果借錢不用還，你借不借？紙上富貴到現實財富，只差在觀念。」
「什麼事都不做，房子放到130年，你可以獲得一間更老的房子。如果現在開始規劃，15年後每年多領60萬，領一輩子，房子一樣沒貸款，一樣增值，一樣繼續住。像不像詐騙？」
四大風險：利率、匯率、基金、身故（身故=結清房貸，是加速器）

■ 財務思維四層級
第零層：財務不穩定→第一層：財務穩定（六個月預備金）
第二層：財務安全（被動收入支付基本開銷）→第三層：財務獨立
「工作是要賺到更多的時間，創造被動收入才能創造更多的時間。」

■ 核心語錄
「世界上沒有白走的路，因為你走的每一步，都算數！」
「不要讓自己變成一個有錢的窮人——資產再多，沒有現金流，你就是窮人。」

【富邦人壽新人獎勵與業務制度說明】

■ 業績制度
來這邊至少要以4C為目標；新人做4C不含新人獎金等於每月領8萬
富邦之星：12C/季=1.8萬/季；48C/年=年終6萬

■ 組織發展數學題
CA月產能2C年薪31萬；SP帶兩CA年薪61萬；AM年薪94萬 vs SP年薪70萬
同工不同酬，最短時間晉升是關鍵；大直轄精神：直轄人數比主管數重要

■ 新人獎勵重點
6C=年薪百萬基礎；月月獎金CA做3.3萬直接多領1.5萬；跨售60件=2.1萬獎金

■ 三台印鈔機：佣金+組織+階級（業務領42%，部長領82%）

■ 客戶開發漏斗
300名單→30進漏斗→12激發興趣→4遞送建議書→成交1個
100件入門；300件安全；500件吃香喝辣

回答原則：
- 使用繁體中文
- 根據對方身份調整語氣：對新人鼓勵親切，對主管專業直接
- 回答具體實用，給可以馬上執行的建議
- 適時引用實際話術或問句範例
- 每次回覆控制在1500字以內，內容多時提醒使用者繼續追問"""

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

    # 正常對話
    identity = user.get('identity', '')
    history = get_history(user_id)
    history.append({'role': 'user', 'content': user_msg})
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
