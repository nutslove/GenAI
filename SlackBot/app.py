import os
import time
import re
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import boto3
import json

# アプリを初期化
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
    process_before_response=True, # デフォルトではすべてのリクエストを処理した後にレスポンスを返すが、Trueにすることでリクエストを処理する前にレスポンスを返す
)

# Slack API クライアント
slack_client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))

def send_sqs_message(queue_url, system, region, message_text, thread_ts, channel_id):
    sqs = boto3.client("sqs")
    try:
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=message_text,
            MessageGroupId="error_message", # FIFOキュー内の順序を保証する単位 (FIFOキューの場合のみ必要)
            MessageDeduplicationId=str(time.time_ns()),
            # FIFO SQSで"コンテンツに基づく重複排除"を有効にしてない場合、MessageDeduplicationIdも指定する必要がある
            MessageAttributes={
                'thread_ts': {
                    'StringValue': thread_ts,
                    'DataType': 'String'
                },
                'channel_id': {
                    'StringValue': channel_id,
                    'DataType': 'String'
                },
                'system': {
                    'StringValue': system,
                    'DataType': 'String'
                },
                'region': {
                    'StringValue': region,
                    'DataType': 'String'
                }
            }
        )
    except Exception as e:
        print("Error sending message to sqs:", str(e))

@app.action("execute_action")
def handle_execute(ack, body, say):
    # ボタンクリックを確認
    ack()
    thread_ts = body["message"]["ts"]
    channel_id = body["channel"]["id"]
    message_text = body["message"]["blocks"][0]["text"]["text"]
    user = body["user"]["id"]
    system = "unknown"
    region = "unknown"

    try:
        send_sqs_message(os.environ.get("SQS_QUEUE_URL"), system, region, message_text, thread_ts, channel_id)
    except Exception as e:
        print("Error sending message to sqs:", str(e))

    say(
        text=f"<@{user}> さん\n 障害について原因分析を行います。しばらくお待ちください。",
        thread_ts=thread_ts,
        channel=channel_id
    )

@app.action("rethink_action")
def handle_rethink(ack, body, say):
    # ボタンクリックを確認
    ack()
    user = body["user"]["id"]
    say(
        text=f"<@{user}> さん、再度原因分析を行い、対処方法を考えます。",
        thread_ts=body["message"]["ts"]
    )

@app.action("execute_with_info_action")
def open_modal(ack, body, client):
    ack()  # ボタンクリックの確認

    # ボタンで渡された値を取得
    message_text = body["actions"][0]["value"]
    channel_id = body["channel"]["id"]
    thread_ts = body["message"]["ts"]

    # モーダルを開く
    client.views_open(
        trigger_id=body["trigger_id"],  # ボタンクリック時に含まれる trigger_id
        view={
            "type": "modal",
            "callback_id": "modal_callback",
            "private_metadata": f"{channel_id},{thread_ts}",  # channel_id と thread_ts を格納
            "title": {
                "type": "plain_text",
                "text": "モーダル入力"
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"エラーメッセージ内容:\n*{message_text}*"
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_block3", # block_id は一意である必要がある
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "error_message",
                        "initial_value": message_text,  # 初期値としてセット
                        "multiline": True
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "エラーメッセージ内容"
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "system",
                        # "multiline": True
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "System名を入力してください"
                    }
                },
                {
                    "type": "input",
                    "block_id": "input_block2", # block_id は一意である必要がある
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "region",
                        # "multiline": True
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "リージョン名(e.g. ap-northeast-1)を入力してください"
                    }
                }
            ],
            "submit": {
                "type": "plain_text",
                "text": "送信"
            }
        }
    )

@app.view("modal_callback")
def handle_modal_submission(ack, body, say):
    # モーダル送信を確認
    ack()

    # `private_metadata` から channel_id と thread_ts を取得
    # say() でスレッドに返信するために channel_id と thread_tsが必要だけど、モーダルビューのコールバックにはそれらが含まれていないため、モーダルを開くときに `private_metadata` に格納しておく
    private_metadata = body["view"]["private_metadata"]
    channel_id, thread_ts = private_metadata.split(",")

    # view_stateからメッセージを取得
    view_state = body["view"]["state"]["values"]
    print("view_state:\n\t",view_state)

    # ユーザー入力を取得
    user = body["user"]["id"]
    system = body["view"]["state"]["values"]["input_block"]["system"]["value"]
    region = body["view"]["state"]["values"]["input_block2"]["region"]["value"]
    message_text = body["view"]["state"]["values"]["input_block3"]["error_message"]["value"]

    try:
        send_sqs_message(os.environ.get("SQS_QUEUE_URL"),system, region, message_text, thread_ts, channel_id)
    except Exception as e:
        print("Error sending message to sqs:", str(e))

    say(
        text=f"<@{user}> さん\n `{system}` システムの `{region}` リージョン上のの障害について原因分析を行います。しばらくお待ちください。",
        thread_ts=thread_ts,
        channel=channel_id
    )

    #################################################################################################################################
    # LLM処理に時間がかかり、Slack側で"Slackになかなか接続できません。"とエラーになるため、SQSにメッセージを送信して非同期処理を行うように変更 #
    #################################################################################################################################
    # response = rag_analysis(message_text ,system, region)

    # # 処理を実行
    # say(
    #     text=response,
    #     thread_ts=thread_ts,
    #     channel=channel_id
    # )

@app.event("app_mention")
def init(event, say, ack, client):
    ack()

    print("event:\n\t",event)

    # メンション内容の処理
    text = event["text"]  # メンションに含まれるテキスト
    input_text = re.sub("<@.+?>", "", text).strip()  # メンション部分を除去
    thread_ts = event["ts"]  # スレッドタイムスタンプを取得

    say(
        thread_ts=thread_ts,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"以下のエラーメッセージを受け取りました\n ```\n{input_text}\n```\n*以下のいずれかのアクションを選択してください*"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "情報を補足せず原因分析処理実行"
                        },
                        "value": "execute_value",
                        "action_id": "execute_action"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "情報を補足して原因分析処理実行"
                        },
                        "value": f"{input_text}",
                        "action_id": "execute_with_info_action"
                    }
                ]
            }
        ]
    )

# Slack外部からのカスタムエンドポイント
def custom_endpoint(event, context):
    # # 独自の認証ロジック (例: トークン検証)
    # auth_token = request.headers.get("Authorization")
    # if auth_token != os.environ.get("CUSTOM_AUTH_TOKEN"):
    #     return jsonify({"error": "Unauthorized"}), 401

    print("event:\t",event)
    print("context:\t",context)

    # GrafanaからのWebhookの場合
    if "grafana" in event["headers"].get("user-agent").lower():
        body = event["body"]
        print("body:\t",body)

        # bodyのJSONデータを取得
        # body_json = json.loads(event.get('body', '{}'))
        body_json = json.loads(body)

        # alertsのデータを取得
        # alerts = body_json.get('alerts', [])
        alerts = body_json["alerts"]

        # 各alertの情報を取得
        for i, alert in enumerate(alerts):
            status = alert.get('status', 'N/A')
            labels = alert.get('labels', {})
            alertname = labels["alertname"]
            annotations = alert.get('annotations', {})
            value_string = alert.get('valueString', 'N/A')
            message = labels.get('message', 'N/A')
            system = labels.get('sid', 'N/A')
            region = labels.get('region', 'N/A')

            print(f"Alert {i+1}:")
            print(f"  Status: {status}")
            print(f"  Labels: {labels}")
            print(f"  Annotations: {annotations}")
            print(f"  ValueString: {value_string}")
            print(f"  Alertname: {alertname}")
            print(f"  Message: {message}")
            print("-" * 40)

    channel_id = os.environ.get("SLACK_CHANNEL_ID")

    try:
        # Slack API でメッセージを投稿
        response = slack_client.chat_postMessage(
            channel=channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"`{system}` システムの `{region}` リージョン上で以下のアラートが発生しました。原因分析を行いますので、しばらくお待ちください。\n\n *Alert Name*\n{alertname}\n\n *Log Message*\n```{message}```"
                    }
                }
            ]
        )            

        print("response:\t",response)
    except SlackApiError as e:
        print(f"Got an error: {e.response['error']}")
    thread_ts = response["ts"]

    try:
        send_sqs_message(os.environ.get("SQS_QUEUE_URL"),system, region, message, thread_ts, channel_id)
    except Exception as e:
        print("Error sending message to sqs:", str(e))

    slack_client.reactions_add(
        channel=channel_id,
        # name="go",
        name="thumbsup",
        timestamp=thread_ts
    )
    # slack_client.chat_postMessage(
    #     channel=channel_id,
    #     text="thread message",
    #     thread_ts=thread_ts
    # )


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