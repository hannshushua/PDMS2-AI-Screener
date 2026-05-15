import os
import re
import pymysql
import secrets
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime
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

        # Initialize LLM
        if AI_API_KEY:
            self.model = ChatOpenAI(
                model=AI_MODEL,
                openai_api_key=AI_API_KEY,
                openai_api_base=AI_BASE_URL,
                temperature=0.7
            )
            print(f"[RAG] Advisor initialized with model {AI_MODEL}.")
        else:
            print("[RAG] Warning: AI_API_KEY not set.")

        self._initialized = True

    def _ensure_schema(self):
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SHOW COLUMNS FROM ai_advice_history LIKE 'id'")
                    if not cur.fetchone():
                        cur.execute("""
                            ALTER TABLE ai_advice_history
                                DROP PRIMARY KEY,
                                ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST,
                                ADD INDEX idx_uid (uid)
                        """)
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"[RAG] Schema check warning: {e}")

    def _index_documents(self):
        persist_directory = str(ROOT / "rag_db")
        chroma_db_file = Path(persist_directory) / "chroma.sqlite3"

        if chroma_db_file.exists():
            self.vector_store = Chroma(
                persist_directory=persist_directory,
                embedding_function=self.embeddings
            )
            print(f"[RAG] Loaded existing vector store.")
            return

        docs_dir = ROOT / RAG_DOCS_PATH
        all_docs = []

        # Parse PDMS2.md (Custom Table Parser)
        pdms_md = docs_dir / "PDMS2.md"
        if pdms_md.exists():
            content = pdms_md.read_text(encoding="utf-8")
            lines = content.splitlines()
            for line in lines:
                if line.startswith("|") and "Task ID" not in line and "---" not in line:
                    cols = [c.strip() for c in line.split("|") if c.strip()]
                    if len(cols) >= 6:
                        task_id = cols[0].replace("**", "")
                        item_num = cols[1]
                        age_mo = cols[2]
                        item_name = cols[3]
                        proc = cols[4]
                        crit = cols[5]
                        
                        doc_text = f"Task ID: {task_id}\nItem: {item_name} (#{item_num})\n"
                        doc_text += f"Age: {age_mo} months\nProcedure: {proc}\nCriteria: {crit}"
                        
                        all_docs.append(Document(
                            page_content=doc_text,
                            metadata={"source": "PDMS2.md", "task_id": task_id}
                        ))

        # Load other markdown files
        for file_path in docs_dir.glob("*.md"):
            if file_path.name == "PDMS2.md": continue
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
            print(f"[RAG] Indexed {len(all_docs)} chunks.")

    def get_db_connection(self):
        return pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor
        )

    def _get_age_months(self, uid):
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT birthday FROM user_list WHERE uid = %s", (uid,))
                row = cur.fetchone()
                if not row or not row['birthday']: return None
                birthday = row['birthday']
                if isinstance(birthday, str):
                    birthday = datetime.strptime(birthday, "%Y-%m-%d")
                today = datetime.now()
                return (today.year - birthday.year) * 12 + today.month - birthday.month
        except: return None
        finally: conn.close()

    def get_child_performance(self, uid: str) -> List[Dict[str, Any]]:
        conn = self.get_db_connection()
        performance = []
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT task_id, task_name FROM task_list")
                tasks = cur.fetchall()
                for task in tasks:
                    table_name = task['task_name']
                    cur.execute(f"SELECT score, test_date FROM `{table_name}` WHERE uid=%s ORDER BY test_date DESC LIMIT 1", (uid,))
                    row = cur.fetchone()
                    if row:
                        performance.append({
                            "task_id": task['task_id'], "task_name": table_name,
                            "score": row['score'], "date": row['test_date']
                        })
        finally: conn.close()
        return performance

    def _get_score_signature(self, perf):
        perf_sorted = sorted(perf, key=lambda x: x['task_id'])
        return "|".join([f"{p['task_id']}:{p['score']}" for p in perf_sorted])

    def check_advice_status(self, uid: str) -> dict:
        if not self._initialized: self.initialize()
        perf = self.get_child_performance(uid)
        if not perf:
            return {"has_advice": False, "is_fresh": False, "advice": None, "generated_at": None}

        score_sig = self._get_score_signature(perf)
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT advice, score_signature, generated_at FROM ai_advice_history WHERE uid=%s ORDER BY id DESC LIMIT 1",
                    (uid,)
                )
                row = cur.fetchone()
        finally:
            conn.close()

        if not row:
            return {"has_advice": False, "is_fresh": False, "advice": None, "generated_at": None}

        is_fresh = row["score_signature"] == score_sig
        generated_at = row["generated_at"].isoformat() if row["generated_at"] else None
        return {"has_advice": True, "is_fresh": is_fresh, "advice": row["advice"], "generated_at": generated_at}

    def generate_advice(self, uid: str, age_months: int = None, force: bool = False) -> str:
        if not self._initialized: self.initialize()
        if not self.model: return "AI 顧問不可用。"

        if age_months is None:
            age_months = self._get_age_months(uid)
        
        perf = self.get_child_performance(uid)
        if not perf: return "找不到施測紀錄。"

        score_sig = self._get_score_signature(perf)
        
        # Cache check
        if not force:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT advice FROM ai_advice_history WHERE uid=%s AND score_signature=%s ORDER BY id DESC LIMIT 1", (uid, score_sig))
                    row = cur.fetchone()
                    if row: return row['advice']
            finally: conn.close()

        # RAG Retrieval
        weaknesses = [p for p in perf if p['score'] < 2]
        if not weaknesses: return "兒童表現優異，建議維持現狀。"

        context_parts = []
        age_filter = f"{age_months} months" if age_months else ""
        for w in weaknesses:
            query = f"PDMS2 {w['task_id']} {w['task_name']} {age_filter}"
            results = self.vector_store.similarity_search(query, k=2)
            for res in results: context_parts.append(res.page_content)

        context = "\n---\n".join(set(context_parts))
        weaknesses_str = "\n".join([f"- {w['task_name']} (ID: {w['task_id']}): 得分 {w['score']}" for w in weaknesses])
        age_info = f"兒童年齡：{age_months} 個月" if age_months else "年齡資訊：未提供"

        prompt = f"""
你是一位專業的兒童職能治療師。針對以下 PDMS-2 評估結果提供整合性建議。

### 兒童資訊：
- {age_info}
- 待加強項目：
{weaknesses_str}

### 專業背景：
{context}

### 指令：
1. **整合總結**：歸類相似弱項，給出整體發展總結。
2. **居家建議**：提供 3-4 個針對性且有趣的居家活動。
3. **專業語氣**：溫暖且專業。
4. **【強制規定】**：你的回覆最後一句話，必須是關於給家長的支持或鼓勵，**絕對禁止**詢問「是否需要進一步協助」、「是否需要整理表格/計畫」等任何後續服務。寫完建議與鼓勵後請立刻停止。

請開始撰寫：
"""
        try:
            response = self.model.invoke(prompt)
            advice_text = response.content.strip()
            
            # Post-processing: remove unwanted sentences
            import re
            # Match any sentence starting with these keywords until the end of the text
            pattern = re.compile(r'(如果您|如您|若您|如果|若)(願意|希望|需要).*(整理|計畫|表格|衛教單|報告).*$', re.DOTALL)
            advice_text = re.sub(pattern, '', advice_text).strip()
            
            # Also catch variations like "我也可以進一步..."
            pattern2 = re.compile(r'(我也可以|我可以)(進一步|幫您).*(整理|計畫|表格|衛教單|報告).*$', re.DOTALL)
            advice_text = re.sub(pattern2, '', advice_text).strip()

            # Remove trailing empty lines
            lines = advice_text.splitlines()
            while lines and not lines[-1].strip():
                lines.pop()

            advice_text = '\n'.join(lines)
            # Save to history
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO ai_advice_history (uid, advice, score_signature) VALUES (%s, %s, %s)", (uid, advice_text, score_sig))
                conn.commit()
            finally: conn.close()
            return advice_text
        except Exception as e:
            return f"錯誤: {e}"

advisor = PDMS2Advisor()
