import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
load_dotenv(ROOT / "PDMS2_web" / ".env")

def test_api():
    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL")
    model_name = os.getenv("AI_MODEL")
    
    print(f"Testing API: {base_url}")
    print(f"Model: {model_name}")
    
    llm = ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base=base_url
    )
    
    try:
        res = llm.invoke("你好，請用繁體中文自我介紹。")
        print("Response:")
        print(res.content)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
