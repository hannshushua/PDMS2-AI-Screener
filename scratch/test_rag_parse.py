from pathlib import Path
import os
import sys

# Add project root to sys.path
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT / "PDMS2_web"))

def test_parse_pdms2():
    pdms_md = ROOT / "RAG" / "PDMS2.md"
    if not pdms_md.exists():
        print("PDMS2.md not found")
        return
    
    content = pdms_md.read_text(encoding="utf-8")
    lines = content.splitlines()
    headers = []
    items = []
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
                items.append(item_info)
    
    print(f"Parsed {len(items)} items")
    if items:
        print("First item sample:")
        print(items[0])

if __name__ == "__main__":
    test_parse_pdms2()
