import json

def lambda_handler(event, context):
    """
    Lambda関数のエントリポイント
    SQSから送信されたメッセージを処理します。
    """
    try:
        # SQSからのイベントには Records が含まれる
        for record in event['Records']:
            # メッセージ本文を取得
            message_body = record['body']
            
            # MessageAttributesを取得
            message_attributes = record.get('messageAttributes', {})
            
            # 属性の取り出し
            thread_ts = message_attributes.get('thread_ts', {}).get('stringValue', None)
            channel_id = message_attributes.get('channel_id', {}).get('stringValue', None)
            system = message_attributes.get('system', {}).get('stringValue', None)
            region = message_attributes.get('region', {}).get('stringValue', None)

            # メッセージ内容をログに出力
            print("Message Body:", message_body)
            print("thread_ts:", thread_ts)
            print("channel_id:", channel_id)
            print("system:", system)
            print("region:", region)
            
            # 必要に応じてここでビジネスロジックを実行
            # 例: メッセージ内容をデータベースに保存、他のサービスを呼び出すなど
    except Exception as e:
        print("Error processing messages:", str(e))
        raise e

    return {
        'statusCode': 200,
        'body': json.dumps('Message processed successfully')
    }