import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add parent and project root to path for imports
ROOT = Path(__file__).parent.parent.resolve()
sys.path.append(str(ROOT))
sys.path.append(str(ROOT.parent))

from utils.rag_advisor import PDMS2Advisor, advisor

# Load environment variables
load_dotenv(ROOT / ".env")

class RAGTester(PDMS2Advisor):
    """
    A specialized version of PDMS2Advisor for testing purposes.
    Allows overriding database calls with mock data.
    """
    def __init__(self):
        super().__init__()
        self.mock_performance = {}
        self.test_results = []

    def set_mock_performance(self, uid: str, performance: list):
        """Inject mock performance data for a specific UID"""
        self.mock_performance[uid] = performance

    def get_child_performance(self, uid: str):
        """Override to return mock data if available, otherwise call super"""
        if uid in self.mock_performance:
            print(f"[Tester] Using mock performance for {uid}")
            return self.mock_performance[uid]
        return super().get_child_performance(uid)

    def _ensure_schema(self):
        """Override to skip database schema checks during testing"""
        pass

    def generate_advice(self, uid: str, force: bool = True) -> dict:
        """
        Modified generate_advice that returns more metadata for evaluation.
        """
        if not self._initialized:
            self.initialize()

        perf = self.get_child_performance(uid)
        if not perf:
            return {"error": "No performance data"}

        weaknesses = [p for p in perf if p['score'] < 2]
        
        # Capture retrieval info
        retrieved_docs = []
        context_parts = []
        if weaknesses:
            for w in weaknesses:
                query = f"PDMS2 {w['task_name']} {w['task_id']}"
                results = self.vector_store.similarity_search(query, k=2)
                for res in results:
                    retrieved_docs.append({
                        "query": query,
                        "content": res.page_content,
                        "metadata": res.metadata
                    })
                    context_parts.append(res.page_content)
        
        context = "\n---\n".join(set(context_parts))

        # 4. Generate Prompt
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
        start_time = datetime.now()
        try:
            if self.model:
                response = self.model.invoke(prompt)
                advice_text = response.content
            else:
                # Mock fallback if no API key
                advice_text = f"#### [MOCK ADVICE - NO API KEY]\n\n**這是一個模擬的回覆，因為系統未偵測到 AI_API_KEY。**\n\n以下是針對您的情況檢索到的背景知識：\n\n{context[:500]}..."
                print(f"[Tester] AI_API_KEY missing, using mock fallback for {uid}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return {
                "uid": uid,
                "performance": perf,
                "weaknesses": weaknesses,
                "retrieved_docs": retrieved_docs,
                "advice": advice_text,
                "duration": duration,
                "status": "success"
            }
        except Exception as e:
            return {
                "uid": uid,
                "error": str(e),
                "status": "failed"
            }

def evaluate_response(result):
    """
    Perform heuristic evaluation on the generated response.
    """
    if result.get("status") != "success":
        return {"score": 0, "critique": "Generation failed."}

    advice = result["advice"]
    weaknesses = result["weaknesses"]
    
    metrics = {
        "has_markdown_headers": "###" in advice or "##" in advice,
        "has_lists": "- " in advice or "1. " in advice,
        "mention_weaknesses": all(w['task_name'] in advice for w in weaknesses),
        "activity_count": advice.count("- ") + advice.count("1. ") + advice.count("2. ") + advice.count("3. ") + advice.count("4. "),
        "length": len(advice)
    }
    
    score = 0
    if metrics["has_markdown_headers"]: score += 20
    if metrics["has_lists"]: score += 20
    if metrics["mention_weaknesses"]: score += 30
    if metrics["activity_count"] >= 3: score += 30
    
    return {
        "score": score,
        "metrics": metrics,
        "critique": "Check if activities are relevant to the tasks."
    }

def run_tests():
    tester = RAGTester()
    
    # Define test cases
    test_cases = [
        {
            "uid": "test_fine_motor_stack",
            "desc": "Child struggles with stacking blocks (Ch1)",
            "perf": [
                {"task_id": "Ch1-t1", "task_name": "string_blocks", "score": 0},
                {"task_id": "Ch1-t2", "task_name": "pyramid", "score": 1},
                {"task_id": "Ch1-t3", "task_name": "stair", "score": 2}
            ]
        },
        {
            "uid": "test_drawing",
            "desc": "Child struggles with drawing (Ch2)",
            "perf": [
                {"task_id": "Ch2-t1", "task_name": "draw_circle", "score": 1},
                {"task_id": "Ch2-t2", "task_name": "draw_square", "score": 1},
                {"task_id": "Ch2-t3", "task_name": "draw_cross", "score": 2}
            ]
        },
        {
            "uid": "test_cutting",
            "desc": "Child struggles with cutting (Ch3)",
            "perf": [
                {"task_id": "Ch3-t1", "task_name": "cut_circle", "score": 0},
                {"task_id": "Ch3-t4", "task_name": "cut_line", "score": 2}
            ]
        }
    ]

    results = []
    print("="*50)
    print("RAG TEST RUNNER")
    print("="*50)

    for case in test_cases:
        print(f"\nRunning test: {case['desc']} ({case['uid']})")
        tester.set_mock_performance(case['uid'], case['perf'])
        
        result = tester.generate_advice(case['uid'])
        if result["status"] == "success":
            eval_data = evaluate_response(result)
            result["evaluation"] = eval_data
            print(f"Done. Duration: {result['duration']:.2f}s | Score: {eval_data['score']}/100")
        else:
            print(f"Failed: {result.get('error')}")
        
        results.append(result)

    # Generate Report
    report_path = ROOT / "scripts" / f"rag_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# RAG Evaluation Report\n\n")
        f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Summary\n\n")
        f.write("| Case | Status | Duration | Score | Critique |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        for i, r in enumerate(results):
            case_desc = test_cases[i]['desc']
            status = r['status']
            duration = f"{r.get('duration', 0):.2f}s"
            score = r.get('evaluation', {}).get('score', 0)
            critique = r.get('evaluation', {}).get('critique', 'N/A')
            f.write(f"| {case_desc} | {status} | {duration} | {score} | {critique} |\n")
        
        f.write("\n## Detailed Results\n\n")
        for i, r in enumerate(results):
            f.write(f"### Case {i+1}: {test_cases[i]['desc']}\n")
            f.write(f"**UID:** {r['uid']} | **Score:** {r.get('evaluation', {}).get('score', 0)}/100\n\n")
            
            if r['status'] == "success":
                f.write("<details>\n<summary>🔍 檢索到的參考文獻 (Retrieved Context)</summary>\n\n")
                for doc in r['retrieved_docs']:
                    f.write(f"- **Source:** {doc['metadata'].get('source', 'Unknown')}\n")
                    # Limit snippet to 150 chars and clean up newlines
                    clean_content = doc['content'].replace('\n', ' ')[:150]
                    f.write(f"  - *Content:* {clean_content}...\n")
                f.write("\n</details>\n\n")
                
                f.write("<details open>\n<summary>📝 AI 生成建議 (Advice)</summary>\n\n")
                f.write(f"{r['advice']}\n")
                f.write("\n</details>\n\n")
            else:
                f.write(f"❌ **Error:** {r.get('error')}\n\n")
            f.write("---\n")

    print(f"\nReport generated: {report_path}")

if __name__ == "__main__":
    run_tests()
