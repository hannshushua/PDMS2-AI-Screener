import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.append(str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from utils.rag_advisor import PDMS2Advisor

uids = ["test1", "test2", "test3", "test4", "test5"]
advisor = PDMS2Advisor()
advisor.initialize()

for uid in uids:
    print(f"Generating for {uid}...", end=" ", flush=True)
    result = advisor.generate_advice(uid, force=True)
    out_path = Path(__file__).parent / f"{uid}.md"
    out_path.write_text(f"# AI 發展建議報告 - UID: {uid}\n\n{result}", encoding="utf-8")
    print("done")

print("All done.")
