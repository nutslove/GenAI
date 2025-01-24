### Bedrockで使えるモデルID一覧を確認するPython
import boto3

bedrock = boto3.client('bedrock', region_name='ap-northeast-1')

# 利用可能なモデルの一覧を取得
response = bedrock.list_foundation_models(byOutputModality='TEXT')

# モデルIDの一覧を表示
model_ids = [model['modelId'] for model in response['modelSummaries']]
for model_id in model_ids:
    print(model_id)