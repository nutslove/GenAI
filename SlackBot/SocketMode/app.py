import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ボットトークンとソケットモードハンドラーを使ってアプリを初期化します
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.event("app_mention")
def message_hello(event, say):
    # イベントがトリガーされたチャンネルへ say() でメッセージを送信
    text = event["text"]
    print(text)
    # say(f"メンションを受け取りました: {text}")
    say(f"こんにちは、<@{event['user']}> さん！")
    

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start() # アプリを起動
