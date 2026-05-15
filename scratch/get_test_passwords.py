import pymysql

DB = dict(
    host="100.117.109.112",
    port=3306,
    user="yplab",
    password="brain0918",
    database="testPDMS",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

def get_passwords():
    try:
        conn = pymysql.connect(**DB)
        with conn.cursor() as cur:
            uids = ["test1", "test2", "test3", "test4", "test5"]
            
            print("--- admin_users (Parent Accounts) ---")
            sql = "SELECT account, password FROM admin_users WHERE account IN %s"
            cur.execute(sql, (uids,))
            rows = cur.fetchall()
            for row in rows:
                print(f"Account: {row['account']}, Password: {row['password']}")
            
            print("\n--- user_list (Kid Profiles) ---")
            sql = "SELECT uid, birthday FROM user_list WHERE uid IN %s"
            cur.execute(sql, (uids,))
            rows = cur.fetchall()
            for row in rows:
                print(f"UID: {row['uid']}, Birthday: {row['birthday']}")
                
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_passwords()
