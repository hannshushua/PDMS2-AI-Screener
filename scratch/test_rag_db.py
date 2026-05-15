import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT / "PDMS2_web"))

from utils.rag_advisor import advisor

def test_rag_db():
    print("Initializing Advisor (this will download the local embedding model if it's the first time)...")
    advisor.initialize()
    
    if advisor.vector_store:
        print("Success! Vector Database (ChromaDB) initialized.")
        # Test a simple query
        results = advisor.vector_store.similarity_search("疊積木", k=1)
        if results:
            print("Query Result Sample:")
            print(results[0].page_content)
    else:
        print("Failed to initialize Vector Database.")

if __name__ == "__main__":
    test_rag_db()
