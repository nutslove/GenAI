import boto3
import os
from langchain.chains import RetrievalQA
from langchain_aws import ChatBedrock, ChatBedrockConverse
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_aws.retrievers import AmazonKnowledgeBasesRetriever

os.getenv('LANGSMITH_API_KEY')
os.getenv('LANGSMITH_TRACING')

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant that proposes the causes, impacts, and solutions for issues based on the provided information.\n\
            Let's think step by step.\n\
            Must answer in Japanese.",
        ),
        ("human", "{input}"),
    ]
)

prompt_for_rag = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant that compares the given Error Message with the Data from RAG to determine whether the Error Message corresponds to a known issue.\n\
            If it is identified as a known issue, provide the relevant information from the Data from RAG.\n\
            If it is determined to be a new issue, propose the possible causes, impacts, and solutions for the Error Message..\n\
            Must answer in Japanese.",
        ),
        ("human", "## Error Message\n{error_message}\n\n## Data from RAG\n{data_from_rag}"),
    ]
)

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

def main():
    query = input("エラーメッセージを入力してください:\n")
    chain = retriever | (lambda docs: "\n\n".join(doc.page_content for doc in docs))
    result = chain.invoke(query)
    print("result:\n",result)

    ### 上記と同じ処理
    # response = retriever.invoke(query)
    # result = ""
    # for doc in response:
    #     result += doc.page_content+"\n\n"
    # print("result:\n",result)

    chain = prompt_for_rag | llm | StrOutputParser()
    response = chain.invoke({
        "error_message": query,
        "data_from_rag": result,
    })
    print(response)
    ### StrOutputParser()を使わない場合は`.content`で取り出す必要があるけど、StrOutputParser()を使う場合は不要
    # print(response.content)

if __name__ == '__main__':
    main()