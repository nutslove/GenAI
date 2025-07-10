import os
from langchain_google_vertexai import VertexAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from google.cloud import aiplatform

# Set your GOOGLE_APPLICATION_CREDENTIALS environment variable
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./service-account-key.json"

PROJECT_ID = os.getenv("PROJECT_ID")

# Initialize Vertex AI
aiplatform.init(project=PROJECT_ID, location='global')

vertex_ai_llm = VertexAI(
    #model_name="gemini-2.0-flash-001",
    model_name="gemini-2.0-flash-lite-001",
    max_output_tokens=1024,
    temperature=0.2,
    verbose=True
)

# プロンプトテンプレートの定義
prompt_template = PromptTemplate(
    input_variables=["input_text"],
    template="Generate a detailed response to the following input: {input_text}"
)

def generate_response(input_text: str) -> str:
    """より現代的な方法でのレスポンス生成"""
    try:
        # プロンプトの作成
        prompt = prompt_template.format(input_text=input_text)

        # LLMに直接問い合わせ
        response = vertex_ai_llm.invoke(prompt)

        return response
    except Exception as e:
        return f"Error: {str(e)}"

# 使用例
modern_response = generate_response("Explain the significance of variable names in programming.")
print("Response:", modern_response)