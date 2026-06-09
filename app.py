import os
from flask import Flask, request
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from openai import OpenAI

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

handler = WebhookHandler(LINE_CHANNEL_SECRET)
client = OpenAI(api_key=OPENAI_API_KEY)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

# 一時保存。本番ではDB化する
tasks = {}

@app.route("/", methods=["GET"])
def home():
    return "ADHD LINE companion AI is running"

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return "OK"

def reply(event, text):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text)]
            )
        )

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    if user_id not in tasks:
        tasks[user_id] = []

    if user_text.startswith("追加 "):
        task = user_text.replace("追加 ", "", 1).strip()
        tasks[user_id].append(task)
        reply(event, f"登録したよ。\n\n□ {task}")
        return

    if user_text == "タスク":
        if not tasks[user_id]:
            reply(event, "今のタスクは空だよ。")
            return

        task_list = "\n".join([f"{i+1}. {t}" for i, t in enumerate(tasks[user_id])])
        reply(event, f"今のタスク\n\n{task_list}")
        return

    if user_text.startswith("完了 "):
        try:
            num = int(user_text.replace("完了 ", "", 1).strip())
            done_task = tasks[user_id].pop(num - 1)
            reply(event, f"完了にしたよ。\n\n✅ {done_task}\n\nえらい。ちゃんと一個減らした。")
        except:
            reply(event, "番号が見つからなかった。\n例：完了 1")
        return

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=f"""
あなたはADHD向けLINE伴走AIです。
ユーザーは石井ちゃんです。

役割：
・頭の中を整理する
・忘れ物や先延ばしを減らす
・責めずに背中を押す
・次の行動を小さくする

回答ルール：
・短く
・やさしく
・結論から
・必要なら「今やること」を1〜3個に絞る

ユーザー: {user_text}
"""
    )

    reply(event, response.output_text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
