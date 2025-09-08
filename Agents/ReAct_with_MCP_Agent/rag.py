from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVectorStore,PGEngine
from sqlalchemy.ext.asyncio import create_async_engine
from langchain_core.documents import Document
import os
import uuid
import asyncio

vars = {
    "GOOGLE_APPLICATION_CREDENTIALS": "/home/nutslove/GCP_VertexAI/service-account-key.json",
    "connection": "postgresql+psycopg://postgres:postgres@192.168.0.241:30432/postgres", # postgresql+psycopg://ユーザー名:パスワード@ホスト:ポート/データベース名
    # "postgresql+psycopg://postgres:postgres@localhost:5432/postgres" # postgresql+psycopg://ユーザー名:パスワード@ホスト:ポート/データベース名
    "create_table_for_vectorstore": False
}

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = vars["GOOGLE_APPLICATION_CREDENTIALS"]
connection = vars["connection"]

async def create_table_for_vectorstore(pg_engine: PGEngine, table_name: str, vector_size: int):
    # Tableを作成するので、初回だけ実行すること
    await pg_engine.ainit_vectorstore_table(
        table_name=table_name,
        vector_size=vector_size,
    )

async def main():
  engine = create_async_engine(
    connection,
  )
  pg_engine = PGEngine.from_engine(engine=engine)

  TABLE_NAME = "incident_manager"
  VECTOR_SIZE = 3072

  # Tableを作成するので、初回だけ実行すること
  if vars["create_table_for_vectorstore"]:
    await create_table_for_vectorstore(pg_engine, TABLE_NAME, VECTOR_SIZE)

  embedding = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")
  store = await PGVectorStore.create(
    engine=pg_engine,
    table_name=TABLE_NAME,
    embedding_service=embedding,
  )

  docs = [
    Document(page_content="Apples and oranges"),
    Document(page_content="Cars and airplanes"),
    Document(page_content="Train")
  ]

  await store.aadd_documents(docs)

  query = "I'd like a fruit."
  results = await store.asimilarity_search(
    query,
    k=1
  )
  print(results)

if __name__ == "__main__":
  asyncio.run(main())