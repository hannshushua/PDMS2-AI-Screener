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

    def generate_advice(self, uid: str, age_months: int = None, force: bool = True) -> dict:
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
        age_filter = f"{age_months} months" if age_months else ""
        if weaknesses:
            for w in weaknesses:
                query = f"PDMS2 {w['task_name']} {w['task_id']} {age_filter}"
                results = self.vector_store.similarity_search(query, k=2)
                for res in results:
                    retrieved_docs.append({
                        "query": query,
                        "content": res.page_content,
                        "metadata": res.metadata
                    })
                    context_parts.append(res.page_content)
        
        context = "\n---\n".join(set(context_parts))

        # 3. Generate Prompt
        weaknesses_str = "\n".join([f"- {w['task_name']} (ID: {w['task_id']}): 得分 {w['score']}" for w in weaknesses])
        age_info = f"兒童年齡：{age_months} 個月" if age_months else "年齡資訊：未提供"

        prompt = f"""
你是一位專業的兒童發展專家（職能治療師）。請針對以下評估結果提供整合性的家長建議。

### 兒童資訊：
- {age_info}
- 待加強項目（得分未達精熟）：
{weaknesses_str}

### 參考專業背景（PDMS-2 標準與研究）：
{context}

### 寫作指令：
1. **整合性總結**：請勿條列式針對個別項目回答。請將相似的發展弱項（例如：積木與剪紙皆涉及手眼協調）歸類，給出一個整體的發展現況總結。
2. **分齡活動建議**：請根據兒童的「月份年齡」提供 3-4 個精確且適齡的居家練習活動。
3. **專業且溫暖**：語氣應具備職能治療師的專業感，同時對家長表達支持與鼓勵。
4. **絕對禁止結尾贅句**：**禁止**在最後出現「如果您希望，我也可以幫您整理居家訓練表/打勾表」或類似的主動提議。
5. **長度精煉**：避免冗長，重點放在如何在家幫助孩子。

請直接開始撰寫建議內容：
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
            "age_months": 36,
            "perf": [
                {"task_id": "Ch1-t1", "task_name": "string_blocks", "score": 0},
                {"task_id": "Ch1-t2", "task_name": "pyramid", "score": 1},
                {"task_id": "Ch1-t3", "task_name": "stair", "score": 2}
            ]
        },
        {
            "uid": "test_drawing",
            "desc": "Child struggles with drawing (Ch2)",
            "age_months": 48,
            "perf": [
                {"task_id": "Ch2-t1", "task_name": "draw_circle", "score": 1},
                {"task_id": "Ch2-t2", "task_name": "draw_square", "score": 1},
                {"task_id": "Ch2-t3", "task_name": "draw_cross", "score": 2}
            ]
        },
        {
            "uid": "test_cutting",
            "desc": "Child struggles with cutting (Ch3)",
            "age_months": 60,
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
        
        result = tester.generate_advice(case['uid'], age_months=case['age_months'])
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
