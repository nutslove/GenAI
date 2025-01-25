import os
import re
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# アプリを初期化
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
    process_before_response=True, # デフォルトではすべてのリクエストを処理した後にレスポンスを返すが、Trueにすることでリクエストを処理する前にレスポンスを返す
)

# Slack API クライアント
slack_client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.event("app_mention")
def root_cause_analysis(event, say, ack, client):
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

# Slack外部からのカスタムエンドポイント
def custom_endpoint(event, context):
    # # 独自の認証ロジック (例: トークン検証)
    # auth_token = request.headers.get("Authorization")
    # if auth_token != os.environ.get("CUSTOM_AUTH_TOKEN"):
    #     return jsonify({"error": "Unauthorized"}), 401

    # print("event:\t",event)
    # print("context:\t",context)

    try:
        # Slack API でメッセージを投稿
        response = slack_client.chat_postMessage(
            channel="C088L0UP5J7",
            text="test message from custom endpoint"
        )
        print("response:\t",response)
    except SlackApiError as e:
        print(f"Got an error: {e.response['error']}")
    ts = response["ts"]
    slack_client.reactions_add(
        channel="C088L0UP5J7",
        name="go",
        timestamp=ts
    )
    slack_client.chat_postMessage(
        channel="C088L0UP5J7",
        text="thread message",
        thread_ts=ts
    )


# Lambdaイベントハンドラー
def handler(event, context):
    # Lambdaイベントタイプによる分岐
    # print("event:\t",event)
    if "Slackbot" not in event["headers"].get("user-agent"): # Slackからの場合はuser-agentに"Slackbot"が含まれる
        # Slack以外からのリクエストを処理
        return custom_endpoint(event, context)
    else:
        # Slackからのリクエストを処理
        slack_handler = SlackRequestHandler(app=app)
        return slack_handler.handle(event, context)