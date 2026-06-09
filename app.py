import os
import re
import sqlite3
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

DB_PATH = "tasks.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def get_tasks():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, title, done FROM tasks ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return rows


def add_task(title):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO tasks (title, done) VALUES (?, 0)", (title,))
    conn.commit()
    conn.close()


def mark_done_by_number(number):
    rows = get_tasks()
    if number < 1 or number > len(rows):
        return None

    task_id, title, done = rows[number - 1]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

    return title


def delete_by_number(number):
    rows = get_tasks()
    if number < 1 or number > len(rows):
        return None

    task_id, title, done = rows[number - 1]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

    return title


init_db()


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
    text = text.replace("　", " ").strip()
    text = text.lower()
    normalized = text.replace(" ", "")

    if text.startswith("追加 "):
        task_text = text.replace("追加 ", "", 1).strip()

        if not task_text:
            return "追加する内容が空っぽだよ。\n例：追加 明日14時 法務局"

        add_task(task_text)
        rows = get_tasks()

        return f"石井ちゃん、保存した。\n\n{len(rows)}. {task_text}"

    if normalized in ["タスク", "一覧", "リスト"]:
        rows = get_tasks()

        if not rows:
            return "今のタスクは空っぽ。"

        lines = ["今のタスク一覧"]
        for i, row in enumerate(rows, start=1):
            task_id, title, done = row
            mark = "✅" if done == 1 else "□"
            lines.append(f"{i}. {mark} {title}")

        return "\n".join(lines)

    if normalized.startswith("完了"):
        num = extract_number(normalized)

        if num is None:
            return "完了する番号を入れて。\n例：完了 1"

        title = mark_done_by_number(num)

        if title is None:
            return "その番号のタスクはないよ。"

        return f"完了にした。\n\n{num}. ✅ {title}"

    if normalized.startswith("削除"):
        num = extract_number(normalized)

        if num is None:
            return "削除する番号を入れて。\n例：削除 1"

        title = delete_by_number(num)

        if title is None:
            return "その番号のタスクはないよ。"

        return f"削除した。\n\n{title}"

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
