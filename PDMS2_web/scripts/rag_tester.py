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

    def generate_advice(self, uid: str, age_months: int = None, child_name: str = None, force: bool = True) -> dict:
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
                query = f"PDMS2 {w['task_id']} {w['task_name']} {age_filter}"
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
        child_name_str = child_name if child_name else "小朋友"
        age_info = f"兒童姓名：{child_name_str}\n- 兒童年齡：{age_months} 個月" if age_months else f"兒童姓名：{child_name_str}\n- 年齡資訊：未提供"

        prompt = f"""
你是一位專業的兒童職能治療師。針對以下 PDMS-2 評估結果提供整合性建議。

### 兒童資訊：
- {age_info}
- 待加強項目：
{weaknesses_str}

### 專業背景：
{context}

### 指令：
1. **整合總結**：請將相似的發展弱項歸類，針對 {child_name_str} 給出一個整體的發展現況總結，語氣要溫暖、專屬。
2. **居家建議**：提供 3-4 個針對性且有趣的居家活動。請結合 {child_name_str} 目前的年齡月份（{age_months or "36-72"} 個月），在活動中說明該活動對其當前月份年齡發展的意義與居家練習的調整。
3. **親切稱呼**：請在生成的內容（總結、居家活動、給家長鼓勵）中適當且自然地提到小朋友的名字「{child_name_str}」，使建議更貼近客製化 and 溫馨關懷。
4. **【強制規定】**：你的回覆最後一句話，必須是關於對家長及 {child_name_str} 的支持或鼓勵，**絕對禁止**詢問「是否需要進一步協助」、「是否需要整理表格/計畫」等任何後續服務。寫完建議與鼓勵後請立刻停止。

請開始撰寫：
"""
        start_time = datetime.now()
        try:
            if self.model:
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

CHINESE_MAP = {
    "string_blocks": ["string_blocks", "串珠", "穿珠珠"],
    "pyramid": ["pyramid", "金字塔"],
    "stair": ["stair", "階梯"],
    "build_wall": ["build_wall", "砌牆", "蓋牆壁"],
    "draw_circle": ["draw_circle", "畫圓", "圓形"],
    "draw_square": ["draw_square", "畫方形", "正方形", "方形"],
    "draw_cross": ["draw_cross", "畫十字", "十字"],
    "draw_line": ["draw_line", "畫線", "直線"],
    "color": ["color", "著色", "塗色"],
    "connect_dots": ["connect_dots", "連點"],
    "cut_circle": ["cut_circle", "剪圓", "圓形"],
    "cut_square": ["cut_square", "剪方形", "方形"],
    "cut_paper": ["cut_paper", "剪紙"],
    "cut_line": ["cut_line", "剪線", "直線"],
    "one_fold": ["one_fold", "折一折", "摺一折"],
    "two_fold": ["two_fold", "折兩折", "摺兩折"],
    "collect_raisins": ["collect_raisins", "夾葡萄乾"]
}

def evaluate_response(result, child_name=None):
    """
    Perform heuristic evaluation on the generated response.
    """
    if result.get("status") != "success":
        return {"score": 0, "critique": "Generation failed."}

    advice = result["advice"]
    weaknesses = result["weaknesses"]
    
    def check_weakness(w, text):
        name = w['task_name']
        aliases = CHINESE_MAP.get(name, [name])
        return any(alias in text for alias in aliases)

    mention_weaknesses = all(check_weakness(w, advice) for w in weaknesses)

    metrics = {
        "has_markdown_headers": "###" in advice or "##" in advice,
        "has_lists": "- " in advice or "1. " in advice,
        "mention_weaknesses": mention_weaknesses,
        "activity_count": advice.count("- ") + advice.count("1. ") + advice.count("2. ") + advice.count("3. ") + advice.count("4. "),
        "length": len(advice),
        "mentions_name": (child_name in advice) if child_name else True
    }
    
    score = 0
    if metrics["has_markdown_headers"]: score += 20
    if metrics["has_lists"]: score += 20
    if metrics["mention_weaknesses"]: score += 20
    if metrics["activity_count"] >= 3: score += 20
    if metrics["mentions_name"]: score += 20
    
    critique = "Check if activities are relevant to the tasks."
    if not metrics["mentions_name"]:
        critique += f" Missing child's name ({child_name}) in recommendations."
    if not metrics["mention_weaknesses"]:
        critique += " Missing some assessed weaknesses in recommendations."
        
    return {
        "score": score,
        "metrics": metrics,
        "critique": critique
    }

def run_tests():
    tester = RAGTester()
    
    # Define test cases
    test_cases = [
        {
            "uid": "test_fine_motor_stack",
            "desc": "Child struggles with stacking blocks (Ch1)",
            "age_months": 36,
            "child_name": "小寶",
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
            "child_name": "軒軒",
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
            "child_name": "婷婷",
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
        
        result = tester.generate_advice(case['uid'], age_months=case['age_months'], child_name=case['child_name'])
        if result["status"] == "success":
            eval_data = evaluate_response(result, child_name=case['child_name'])
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
