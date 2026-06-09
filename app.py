import os
import re
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# まずはメモリ保存。Render再起動で消える。
tasks = []


@app.route("/", methods=["GET"])
def health_check():
    return "OK"


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()
    reply_text = make_reply(user_text)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )


def make_reply(text):
    global tasks

    if text.startswith("追加 "):
        task_text = text.replace("追加 ", "", 1).strip()

        if not task_text:
            return "追加する内容が空っぽだよ。\n例：追加 明日14時 法務局"

        tasks.append({
            "title": task_text,
            "done": False
        })

        return f"石井ちゃん、保存した。\n\n{len(tasks)}. {task_text}"

    if text in ["タスク", "一覧", "リスト"]:
        if not tasks:
            return "今のタスクは空っぽ。"

        lines = ["今のタスク一覧"]
        for i, task in enumerate(tasks, start=1):
            mark = "✅" if task["done"] else "□"
            lines.append(f"{i}. {mark} {task['title']}")

        return "\n".join(lines)

    if text.startswith("完了 "):
        num = extract_number(text)

        if num is None:
            return "完了する番号を入れて。\n例：完了 1"

        if num < 1 or num > len(tasks):
            return "その番号のタスクはないよ。"

        tasks[num - 1]["done"] = True
        return f"完了にした。\n\n{num}. ✅ {tasks[num - 1]['title']}"

    if text.startswith("削除 "):
        num = extract_number(text)

        if num is None:
            return "削除する番号を入れて。\n例：削除 1"

        if num < 1 or num > len(tasks):
            return "その番号のタスクはないよ。"

        deleted = tasks.pop(num - 1)
        return f"削除した。\n\n{deleted['title']}"

    return (
        "石井ちゃん、今できるのはこれ。\n\n"
        "追加 明日14時 法務局\n"
        "タスク\n"
        "完了 1\n"
        "削除 1"
    )


def extract_number(text):
    match = re.search(r"\d+", text)
    if not match:
        return None
    return int(match.group())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
