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

# 欄位型別與既有任務明細表一致（uid varchar(50) / test_date date / time time），
# 否則 /scores 的 LEFT JOIN 會因 collation 或型別不符而對不上。
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS `manual_score` (
  `uid`        varchar(50) NOT NULL,
  `task_id`    varchar(50) NOT NULL,
  `test_date`  date        NOT NULL,
  `time`       time        NOT NULL,
  `rater`      varchar(64) NOT NULL COMMENT '評分者帳號',
  `score`      tinyint(4)  NOT NULL COMMENT '人工評分 0/1/2',
  `updated_at` datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`uid`,`task_id`,`test_date`,`time`),
  CONSTRAINT `manual_score_ibfk_1` FOREIGN KEY (`uid`) REFERENCES `user_list` (`uid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
"""


def main():
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_SQL)
            conn.commit()
            cur.execute("SHOW CREATE TABLE `manual_score`")
            print(cur.fetchone()["Create Table"])
            cur.execute("SELECT COUNT(*) AS c FROM `manual_score`")
            print(f"現有人工評分筆數：{cur.fetchone()['c']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
