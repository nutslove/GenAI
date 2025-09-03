from langchain_google_genai import GoogleGenerativeAIEmbeddings,ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/nutslove/GCP_VertexAI/service-account-key.json"

embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    temperature=0,
    max_tokens=1024,
    # max_retries=2,
    # verbose=True
)
prompt_template = PromptTemplate(
    input_variables=["input_text"],
    template="Generate a detailed response to the following input: {input_text}"
)

prompt = prompt_template.format(input_text=input("Input: "))
response = llm.invoke(prompt)
print("Response:", response)