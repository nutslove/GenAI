import os
import re
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from langchain_aws import ChatBedrock, ChatBedrockConverse
from langchain_aws.retrievers import AmazonKnowledgeBasesRetriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
import boto3

# アプリを初期化
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
    process_before_response=True, # デフォルトではすべてのリクエストを処理した後にレスポンスを返すが、Trueにすることでリクエストを処理する前にレスポンスを返す
)

# Slack API クライアント
slack_client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))

llm = ChatBedrock(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    model_kwargs={
        "temperature": 0.1,
        # "max_tokens": 8000,
    }
)

retriever = AmazonKnowledgeBasesRetriever(
    knowledge_base_id=os.getenv('KNOWLEDGEBASE_ID'),
    retrieval_config={
        "vectorSearchConfiguration": {
            "numberOfResults": 4
        }
    },
)

prompt_for_rag = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant that compares the given Error Message with the Data from RAG to determine whether the Error Message corresponds to a known issue.\n\
            If it is identified as a known issue, provide the relevant information from the Data from RAG.\n\
            If it is determined to be a new issue, propose the possible causes, impacts, and solutions for the Error Message.\n\
            Regarding the solution, suggest commands to investigate and solve the issue.\
            Must answer in Japanese.",
        ),
        ("human", "## Error Message\n{error_message}\n\n## Data from RAG\n{data_from_rag}"),
    ]
)

# def cause_analysis():
## 原因分析処理を実装

def rag_analysis(message_text: str, system: str, region: str) -> str:
    chain = retriever | (lambda docs: "\n\n".join(doc.page_content for doc in docs))
    result = chain.invoke(message_text)
    chain = prompt_for_rag | llm | StrOutputParser()
    response = chain.invoke({
        "error_message": message_text,
        "data_from_rag": result,
    })
    return response

@app.action("execute_action")
def handle_execute(ack, body, say):
    # ボタンクリックを確認
    ack()
    user = body["user"]["id"]
    say(
        text=f"<@{user}> さん、実行しました！",
        thread_ts=body["message"]["ts"]    
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
            "private_metadata": f"{channel_id},{thread_ts},{message_text}",  # channel_id と thread_ts を格納
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
    channel_id, thread_ts, message_text = private_metadata.split(",")


    # ユーザー入力を取得
    user = body["user"]["id"]
    system = body["view"]["state"]["values"]["input_block"]["system"]["value"]
    region = body["view"]["state"]["values"]["input_block2"]["region"]["value"]

    response = rag_analysis(message_text ,system, region)

    # 処理を実行
    say(
        # text=f"<@{user}> さんが '{system}'システムの'{region}'リージョンの障害について処理を実行しました",
        text=response,
        thread_ts=thread_ts,
        channel=channel_id
    )

@app.event("app_mention")
def init(event, say, ack, client):

    print("event:\n\t",event)

    ack()

    # メンション内容の処理
    text = event.get("text", "")  # メンションに含まれるテキスト
    input_text = re.sub("<@.+?>", "", text).strip()  # メンション部分を除去
    thread_ts = event.get("thread_ts", event["ts"])  # スレッドタイムスタンプを取得

    say(
        thread_ts=thread_ts,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"エラーメッセージを受け取りました: {input_text}\n以下のいずれかのアクションを選択してください："
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


    # ack()

    # # イベントがトリガーされたチャンネルへ say() でメッセージを送信
    # input_text = re.sub("<@.+>", "", event["text"]).strip() # botへのメンションを削除
    # thread_ts = event.get("thread_ts", event["ts"])  # スレッドタイムスタンプを取得
    # # メンションされたメッセージにリアクションを追加
    # client.reactions_add(
    #     channel=event["channel"],
    #     name="thumbsup",  # 追加するスタンプの名前（例: "thumbsup"）
    #     timestamp=event["ts"]  # メンションされたメッセージのタイムスタンプ
    # )

    # say(
    #     text=f"こんにちは、<@{event['user']}> さん！",
    #     thread_ts=thread_ts
    # )
    # say(
    #     text=f"次のメッセージを受け取りました: {input_text}",
    #     thread_ts=thread_ts
    # )

# Slack外部からのカスタムエンドポイント
def custom_endpoint(event, context):
    # # 独自の認証ロジック (例: トークン検証)
    # auth_token = request.headers.get("Authorization")
    # if auth_token != os.environ.get("CUSTOM_AUTH_TOKEN"):
    #     return jsonify({"error": "Unauthorized"}), 401

    print("event:\t",event)
    print("context:\t",context)

    channel_id = os.environ.get("SLACK_CHANNEL_ID")

    try:
        # Slack API でメッセージを投稿
        response = slack_client.chat_postMessage(
            channel=channel_id,
            # text="test message from custom endpoint"
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"以下のいずれかのアクションを選択してください："
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "実行"
                            },
                            "value": "execute_value",
                            "action_id": "execute_action"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "再考"
                            },
                            "value": "rethink_value",
                            "action_id": "rethink_action"
                        }
                    ]
                }
            ]
        )
        print("response:\t",response)
    except SlackApiError as e:
        print(f"Got an error: {e.response['error']}")
    ts = response["ts"]
    slack_client.reactions_add(
        channel=channel_id,
        # name="go",
        name="thumbsup",
        timestamp=ts
    )
    slack_client.chat_postMessage(
        channel=channel_id,
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