import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
load_dotenv(ROOT / "PDMS2_web" / ".env")

def test_embeddings():
    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL")
    
    print(f"Testing Embeddings API: {base_url}")
    
    embeddings = OpenAIEmbeddings(
        openai_api_key=api_key,
        openai_api_base=base_url
    )
    
    try:
        vector = embeddings.embed_query("這是一段測試文字。")
        print(f"Success! Vector dimension: {len(vector)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_embeddings()
