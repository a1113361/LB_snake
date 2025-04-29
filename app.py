from flask import Flask, request, abort
import os
from dotenv import load_dotenv
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from handlers import default, faq, news
import requests  # 用來呼叫 Ollama
import re

load_dotenv()
app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# --- 新增一個函式：呼叫本地的 Ollama ---
def ask_ollama(prompt):
    url = "https://e5c7-2001-b400-e758-e07f-8958-e3e-4a6c-8982.ngrok-free.app/api/generate"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "deepseek-r1:1.5b",
        "prompt": f"請用繁體中文回答以下問題：{prompt}",
        "stream": False
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Ollama 回應內容: {response.text}")
        result = response.json()
        ai_reply = result.get("response", "很抱歉，AI 回覆失敗了喔。")
        ai_reply = clean_response(ai_reply)
        return ai_reply
    except requests.exceptions.RequestException as e:
        print(f"Ollama 請求錯誤：{e}")
        return "很抱歉，無法聯繫 Ollama。"
    except ValueError as e:
        print(f"Ollama 回應錯誤：{e}")
        return "Ollama 回應格式錯誤。"

def clean_response(response_text):
    cleaned_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL)
    return cleaned_text.strip()

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    print(f"收到訊息：{repr(msg)}")

    reply = faq.handle(msg)
    if reply:
        print("FAQ 命中")
    else:
        reply = news.handle(msg)
        if reply:
            print("NEWS 命中")
        else:
            print("沒命中，走 fallback ➔ 叫 Ollama 回答")
            ai_reply = ask_ollama(msg) 
            reply = TextSendMessage(text=ai_reply)

    line_bot_api.reply_message(event.reply_token, reply)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
