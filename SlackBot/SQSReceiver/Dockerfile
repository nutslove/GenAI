# https://gallery.ecr.aws/lambda/python
# Windows環境で`docker build --platform linux/amd64 --provenance=false -t slackbot-v1 .`と`--platform linux/amd64 --provenance=false`をつけることでエラーを回避
# https://stackoverflow.com/questions/65608802/cant-deploy-container-image-to-lambda-function
FROM public.ecr.aws/lambda/python:3.13
COPY requirements.txt app.py ${LAMBDA_TASK_ROOT}/
RUN pip3 install -r requirements.txt
CMD [ "app.handler" ]