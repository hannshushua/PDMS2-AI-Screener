import os
import pymysql
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
ROOT = Path(__file__).parent.parent.resolve()
load_dotenv(ROOT / ".env")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "testPDMS")

TASK_TABLES = [
    "string_blocks", "pyramid", "stair", "build_wall",
    "draw_circle", "draw_square", "draw_cross", "draw_line",
    "color", "connect_dots", "cut_circle", "cut_square",
    "cut_paper", "cut_line", "one_fold", "two_fold", "collect_raisins"
]

def check_users():
    try:
        conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor
        )
        with conn.cursor() as cur:
            # 1. 取得所有使用者
            cur.execute("SELECT uid, name, birthday FROM user_list")
            users = cur.fetchall()
            
            print(f"{'UID':<15} | {'姓名':<10} | {'生日':<12} | {'施測項目數':<10}")
            print("-" * 55)
            
            found_count = 0
            for user in users:
                uid = user['uid']
                score_count = 0
                for table in TASK_TABLES:
                    try:
                        cur.execute(f"SELECT COUNT(*) as cnt FROM `{table}` WHERE uid=%s", (uid,))
                        row = cur.fetchone()
                        if row['cnt'] > 0:
                            score_count += 1
                    except:
                        continue
                
                if score_count > 0:
                    found_count += 1
                    print(f"{uid:<15} | {str(user['name']):<10} | {str(user['birthday']):<12} | {score_count:<10}")
            
            if found_count == 0:
                print("目前資料庫中沒有任何小朋友具備施測分數。")
            else:
                print(f"\n共找到 {found_count} 位小朋友適合產生建議。")

    except Exception as e:
        print(f"資料庫連接失敗: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_users()
