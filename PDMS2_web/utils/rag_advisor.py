import os
import re
import pymysql
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# RAG & LLM libraries
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document

# Load environment variables
ROOT = Path(__file__).parent.parent.resolve()
load_dotenv(ROOT / ".env")

AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
AI_MODEL = os.getenv("AI_MODEL", "gpt-3.5-turbo")
RAG_DOCS_PATH = os.getenv("RAG_DOCS_PATH", "../RAG")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "testPDMS")

class PDMS2Advisor:
    def __init__(self):
        self.embeddings = None
        self.vector_store = None
        self.model = None
        self._initialized = False

    def initialize(self):
        if self._initialized:
            return
        
        if not AI_API_KEY:
            print("[RAG] Warning: AI_API_KEY not set.")
            return

        self.model = ChatOpenAI(
            model=AI_MODEL,
            openai_api_key=AI_API_KEY,
            openai_api_base=AI_BASE_URL,
            temperature=0.7
        )
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            cache_folder=str(ROOT / "model_cache")
        )
        
        # Load and Index Documents
        self._index_documents()
        self._initialized = True
        print(f"[RAG] Advisor initialized successfully with model {AI_MODEL}.")

    def _index_documents(self):
        docs_dir = ROOT / RAG_DOCS_PATH
        all_docs = []
        
        # Parse PDMS2.md specifically for better chunking
        pdms_md = docs_dir / "PDMS2.md"
        if pdms_md.exists():
            content = pdms_md.read_text(encoding="utf-8")
            # Simple markdown table parser for PDMS2.md
            lines = content.splitlines()
            headers = []
            for line in lines:
                if line.startswith("|") and "Item #" in line:
                    headers = [h.strip() for h in line.split("|") if h.strip()]
                    continue
                if line.startswith("|") and "---" in line:
                    continue
                if line.startswith("|"):
                    cols = [c.strip() for c in line.split("|") if c.strip()]
                    if len(cols) >= 5:
                        # Item #, Age, Item NAME, Procedure, Criteria
                        item_info = {headers[i]: cols[i] for i in range(len(cols))}
                        doc_text = f"Item #{item_info.get('Item #')}: {item_info.get('Item NAME')}\n"
                        doc_text += f"Target Age: {item_info.get('Age in months')} months\n"
                        doc_text += f"Procedure: {item_info.get('Procedure')}\n"
                        doc_text += f"Criteria: {item_info.get('Criteria')}"
                        
                        all_docs.append(Document(
                            page_content=doc_text,
                            metadata={"source": "PDMS2.md", "item_id": item_info.get("Item #"), "type": "pdms_item"}
                        ))
        
        # Load other text/markdown files normally
        for file_path in docs_dir.glob("*.md"):
            if file_path.name == "PDMS2.md": continue
            content = file_path.read_text(encoding="utf-8")
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            chunks = splitter.split_text(content)
            for chunk in chunks:
                all_docs.append(Document(page_content=chunk, metadata={"source": file_path.name}))

        if all_docs:
            persist_directory = str(ROOT / "rag_db")
            self.vector_store = Chroma.from_documents(
                documents=all_docs,
                embedding=self.embeddings,
                persist_directory=persist_directory
            )
            print(f"[RAG] Indexed {len(all_docs)} chunks from {docs_dir}")

    def get_db_connection(self):
        return pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )

    def get_child_performance(self, uid: str) -> List[Dict[str, Any]]:
        conn = self.get_db_connection()
        performance = []
        try:
            with conn.cursor() as cur:
                # Get the list of tables (tasks)
                cur.execute("SELECT task_id, task_name FROM task_list")
                tasks = cur.fetchall()
                
                for task in tasks:
                    table_name = task['task_name']
                    # Get the latest score for this child in this task
                    cur.execute(f"SELECT score, test_date FROM `{table_name}` WHERE uid=%s ORDER BY test_date DESC, time DESC LIMIT 1", (uid,))
                    row = cur.fetchone()
                    if row:
                        performance.append({
                            "task_id": task['task_id'],
                            "task_name": table_name,
                            "score": row['score'],
                            "date": row['test_date']
                        })
        finally:
            conn.close()
        return performance

    def generate_advice(self, uid: str) -> str:
        if not self._initialized:
            self.initialize()
        
        if not self._initialized:
            return "AI 顧問尚未初始化（可能缺少 API Key），請聯絡系統管理員。"

        # 1. 取得兒童表現
        perf = self.get_child_performance(uid)
        if not perf:
            return "找不到該兒童的施測紀錄。"

        # 2. 篩選弱項 (分數 0 或 1)
        weaknesses = [p for p in perf if p['score'] < 2]
        if not weaknesses:
            return "該兒童表現優異，所有項目皆達標！建議繼續保持多元的活動練習。"

        # 3. 檢索相關知識
        context_parts = []
        for w in weaknesses:
            # 搜尋相關的 PDMS2 項目描述
            query = f"PDMS2 {w['task_name']} {w['task_id']}"
            results = self.vector_store.similarity_search(query, k=2)
            for res in results:
                context_parts.append(res.page_content)

        context = "\n---\n".join(set(context_parts))

        # 4. 產生 Prompt 並呼叫 LLM
        prompt = f"""
你是一位專業的兒童發展專家與職能治療師。
以下是一位兒童在 PDMS-2（皮巴迪發展運動量表）評估中的表現：
UID: {uid}
表現較弱的項目：
{chr(10).join([f"- {w['task_name']} (ID: {w['task_id']}): 得分 {w['score']}" for w in weaknesses])}

背景知識參考：
{context}

請根據以上資訊，為家長撰寫一份專業且親切的建議。內容應包括：
1. 簡單說明這些弱項代表的發展意義。
2. 提供 3-4 個家長可以在家裡帶小朋友做的訓練活動（居家活動），要簡單、有趣且具備可執行性。
3. 給予家長正向的鼓勵。

請使用繁體中文撰寫，並使用 Markdown 格式（例如標題、列表）。
"""
        try:
            response = self.model.invoke(prompt)
            return response.content
        except Exception as e:
            return f"生成建議時發生錯誤: {str(e)}"

# Singleton instance
advisor = PDMS2Advisor()
