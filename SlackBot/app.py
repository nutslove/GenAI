import os
import re
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler

# アプリを初期化
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
    process_before_response=True, # デフォルトではすべてのリクエストを処理した後にレスポンスを返すが、Trueにすることでリクエストを処理する前にレスポンスを返す
)

@app.event("app_mention")
def message_hello(event, say):
    # イベントがトリガーされたチャンネルへ say() でメッセージを送信
    input_text = re.sub("<@.+>", "", event["text"]).strip() # botへのメンションを削除
    thread_ts = event.get("thread_ts", event["ts"])  # スレッドタイムスタンプを取得

    say(
        text=f"こんにちは、<@{event['user']}> さん！",
        thread_ts=thread_ts
    )
    say(
        text=f"次のメッセージを受け取りました: {input_text}",
        thread_ts=thread_ts
    )

# Lambdaイベントハンドラー
def handler(event, context):
    slack_handler = SlackRequestHandler(app=app)
    return slack_handler.handle(event, context)