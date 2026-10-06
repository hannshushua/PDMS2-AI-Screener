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

# 鈕扣關（Ch5-t2 解鈕扣 / Ch5-t3 扣鈕扣），表名對應 run.py 的 TASK_MAP
TASKS = [("Ch5-t2", "unbutton"), ("Ch5-t3", "button")]

# 結構照抄既有任務明細表（SHOW CREATE TABLE draw_line）。
# 影片上傳後待人工評分時 score 存 NULL，跟分析失敗的 -1 區分。
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS `{table}` (
  `uid` varchar(50) NOT NULL,
  `test_date` date NOT NULL,
  `time` time NOT NULL,
  `score` int(11) DEFAULT NULL,
  `result_img_path` varchar(255) DEFAULT NULL,
  `data1` text DEFAULT NULL,
  PRIMARY KEY (`uid`,`test_date`,`time`),
  CONSTRAINT `{table}_ibfk_1` FOREIGN KEY (`uid`) REFERENCES `user_list` (`uid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
"""


def count_admin_rows(cur):
    """跟 admin.py /scores 一樣：依 task_list 把每張明細表 UNION ALL 起來算筆數。"""
    cur.execute("SELECT task_id, task_name FROM task_list")
    parts = [
        f"SELECT d.uid FROM `{r['task_name']}` AS d JOIN user_list AS u ON u.uid = d.uid"
        for r in cur.fetchall()
    ]
    cur.execute("SELECT COUNT(*) AS c FROM (" + " UNION ALL ".join(parts) + ") AS x")
    return cur.fetchone()["c"]


def main():
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cur:
            print(f"管理端明細表筆數（建表前）：{count_admin_rows(cur)}")

            # 一定要先建表再登記 task_list：admin.py 用 task_list 串 UNION，
            # 登記了卻沒有表，整條查詢會失敗，管理端明細表會全部變空。
            for _, table in TASKS:
                cur.execute(CREATE_SQL.format(table=table))
            conn.commit()

            cur.execute(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME IN (%s, %s)",
                (DB_NAME, TASKS[0][1], TASKS[1][1]),
            )
            existing = {r["TABLE_NAME"] for r in cur.fetchall()}
            if existing != {t for _, t in TASKS}:
                raise RuntimeError(f"建表不完整，停止登記 task_list：{existing}")

            for task_id, table in TASKS:
                cur.execute(
                    "INSERT INTO task_list(task_id, task_name) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE task_name=VALUES(task_name)",
                    (task_id, table),
                )
            conn.commit()

            for _, table in TASKS:
                cur.execute(f"SHOW CREATE TABLE `{table}`")
                print(cur.fetchone()["Create Table"], end="\n\n")
            cur.execute("SELECT task_id, task_name FROM task_list WHERE task_id LIKE 'Ch5%%' ORDER BY task_id")
            print("task_list Ch5：", cur.fetchall())
            print(f"管理端明細表筆數（建表後）：{count_admin_rows(cur)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
