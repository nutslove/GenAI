import os
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ボットトークンとソケットモードハンドラーを使ってアプリを初期化します
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.event("app_mention")
def message_hello(event, say, ack, client):
    ack()

    # イベントがトリガーされたチャンネルへ say() でメッセージを送信
    input_text = re.sub("<@.+>", "", event["text"]).strip() # botへのメンションを削除
    thread_ts = event.get("thread_ts", event["ts"])  # スレッドタイムスタンプを取得

    # メンションされたメッセージにリアクションを追加
    client.reactions_add(
        channel=event["channel"],
        name="thumbsup",  # 追加するスタンプの名前（例: "thumbsup"）
        timestamp=event["ts"]  # メンションされたメッセージのタイムスタンプ
    )

    say(
        text=f"こんにちは、<@{event['user']}> さん！",
        thread_ts=thread_ts
    )
    say(
        text=f"次のメッセージを受け取りました: {input_text}",
        thread_ts=thread_ts
    )
    

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start() # アプリを起動
