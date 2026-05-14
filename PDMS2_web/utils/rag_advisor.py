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

        # Cleanup corrupted (0-byte) files in model_cache
        cache_dir = ROOT / "model_cache"
        if cache_dir.exists():
            for p in cache_dir.rglob("*"):
                if p.is_file() and p.stat().st_size == 0:
                    try:
                        p.unlink()
                        print(f"[RAG] Removed corrupted file: {p.name}")
                    except: pass

        # Initialize Embeddings (Local)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            cache_folder=str(cache_dir)
        )

        # Load and Index Documents
        self._index_documents()
        self._ensure_schema()

        # Initialize LLM (Requires API Key)
        if AI_API_KEY:
            self.model = ChatOpenAI(
                model=AI_MODEL,
                openai_api_key=AI_API_KEY,
                openai_api_base=AI_BASE_URL,
                temperature=0.7
            )
            print(f"[RAG] Advisor initialized with model {AI_MODEL}.")
        else:
            print("[RAG] Warning: AI_API_KEY not set. LLM features will be disabled.")

        self._initialized = True
        print(f"[RAG] Advisor initialization complete.")

    def _ensure_schema(self):
        """確保 ai_advice_history 支援歷史紀錄（多筆 uid）"""
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    # Migrate to multi-row history: replace uid PK with auto-increment id
                    cur.execute("SHOW COLUMNS FROM ai_advice_history LIKE 'id'")
                    if not cur.fetchone():
                        cur.execute("""
                            ALTER TABLE ai_advice_history
                                DROP PRIMARY KEY,
                                ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST,
                                ADD INDEX idx_uid (uid)
                        """)
                        print("[RAG] Migrated ai_advice_history to multi-row history schema.")
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"[RAG] Schema check warning: {e}")

    def check_advice_status(self, uid: str) -> dict:
        """檢查快取建議是否存在，以及與當前分數是否一致"""
        if not self._initialized:
            self.initialize()
        try:
            perf = self.get_child_performance(uid)
            current_sig = "|".join(
                f"{p['task_id']}:{p['score']}"
                for p in sorted(perf, key=lambda x: x['task_id'])
            )
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT advice, score_signature, updated_at "
                        "FROM ai_advice_history WHERE uid=%s "
                        "ORDER BY id DESC LIMIT 1",
                        (uid,)
                    )
                    row = cur.fetchone()
            finally:
                conn.close()

            if not row:
                return {"has_advice": False, "is_fresh": False, "advice": None, "generated_at": None}
            return {
                "has_advice": True,
                "is_fresh": row["score_signature"] == current_sig,
                "advice": row["advice"],
                "generated_at": str(row["updated_at"]) if row.get("updated_at") else None,
            }
        except Exception as e:
            print(f"[RAG] check_advice_status failed for {uid}: {e}")
            return {"has_advice": False, "is_fresh": False, "advice": None, "generated_at": None}

    def _index_documents(self):
        persist_directory = str(ROOT / "rag_db")
        chroma_db_file = Path(persist_directory) / "chroma.sqlite3"

        # Load existing index if present — skip re-indexing
        if chroma_db_file.exists():
            self.vector_store = Chroma(
                persist_directory=persist_directory,
                embedding_function=self.embeddings
            )
            print(f"[RAG] Loaded existing vector store from {persist_directory}")
            return

        # First run: build index from documents
        docs_dir = ROOT / RAG_DOCS_PATH
        all_docs = []

        # Parse PDMS2.md specifically for better chunking
        pdms_md = docs_dir / "PDMS2.md"
        if pdms_md.exists():
            content = pdms_md.read_text(encoding="utf-8")
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
                        item_info = {headers[i]: cols[i] for i in range(len(cols))}
                        doc_text = f"Item #{item_info.get('Item #')}: {item_info.get('Item NAME')}\n"
                        doc_text += f"Target Age: {item_info.get('Age in months')} months\n"
                        doc_text += f"Procedure: {item_info.get('Procedure')}\n"
                        doc_text += f"Criteria: {item_info.get('Criteria')}"
                        all_docs.append(Document(
                            page_content=doc_text,
                            metadata={"source": "PDMS2.md", "item_id": item_info.get("Item #"), "type": "pdms_item"}
                        ))

        # Load other markdown files normally
        for file_path in docs_dir.glob("*.md"):
            if file_path.name == "PDMS2.md":
                continue
            content = file_path.read_text(encoding="utf-8")
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            for chunk in splitter.split_text(content):
                all_docs.append(Document(page_content=chunk, metadata={"source": file_path.name}))

        if all_docs:
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
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=30
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

    def generate_advice(self, uid: str, force: bool = False) -> str:
        if not self._initialized:
            self.initialize()

        if not self._initialized:
            return "AI 顧問尚未初始化（可能缺少 API Key），請聯絡系統管理員。"

        # 1. 取得兒童表現
        perf = self.get_child_performance(uid)
        if not perf:
            return "找不到該兒童的施測紀錄。"

        # 建立分數簽名，格式: task1:score|task2:score... (排序以確保一致性)
        perf_sorted = sorted(perf, key=lambda x: x['task_id'])
        score_sig = "|".join([f"{p['task_id']}:{p['score']}" for p in perf_sorted])

        # 檢查快取（force=True 時略過）
        if not force:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT advice, score_signature FROM ai_advice_history "
                        "WHERE uid=%s ORDER BY id DESC LIMIT 1",
                        (uid,)
                    )
                    cache = cur.fetchone()
                    if cache and cache['score_signature'] == score_sig:
                        print(f"[RAG] Using cached advice for {uid}")
                        return cache['advice']
            except Exception as e:
                print(f"[RAG] Cache check failed: {e}")
            finally:
                conn.close()

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
        weaknesses_str = "\n".join([f"- {w['task_name']} (ID: {w['task_id']}): 得分 {w['score']}" for w in weaknesses])

        # 4. 產生 Prompt 並呼叫 LLM
        prompt = f"""
你是一位專業的兒童發展專家（職能治療師）。請針對以下評估結果提供家長建議。

### 兒童表現與背景資訊：
{context}

### 待加強項目（得分未達精熟）：
{weaknesses_str}

### 寫作指南：
1. **整合性總結**：不要分開列出每個項目，請將相似的弱項歸類，給出一個整體的發展現況總結。
2. **精簡活動建議**：提供 3-4 個針對性的居家遊戲活動，需具備操作性、趣味性且生活化。
3. **專業語氣**：溫和、鼓勵且具專業洞察。
4. **禁止結尾推銷**：**絕對不要**在最後詢問是否要整理「居家練習表」或「打勾表」。
5. **長度適中**：保持內容精煉，不要過於冗長。

請直接開始撰寫建議內容：
"""
        try:
            response = self.model.invoke(prompt)
            advice_text = response.content
            
            # 5. 儲存至歷史紀錄
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO ai_advice_history (uid, advice, score_signature) "
                        "VALUES (%s, %s, %s)",
                        (uid, advice_text, score_sig)
                    )
                conn.commit()
                print(f"[RAG] Saved new advice for {uid} to history.")
            except Exception as e:
                print(f"[RAG] Failed to save advice for {uid}: {e}")
            finally:
                conn.close()

            return advice_text
        except Exception as e:
            return f"生成建議時發生錯誤: {str(e)}"

# Singleton instance
advisor = PDMS2Advisor()
