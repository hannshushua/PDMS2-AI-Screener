# run_admin.py
# -*- coding: utf-8 -*-
from pathlib import Path
from flask import Flask, send_from_directory, request, jsonify, session, redirect
import threading
from datetime import datetime, date
import os, secrets, queue
import hashlib
import hmac
import webbrowser
from flask_cors import CORS
import traceback
from typing import Optional
from werkzeug.exceptions import HTTPException
import pymysql
from urllib.parse import urlencode, urlparse
import re

from utils.rag_advisor import advisor

print("====== CURRENT ADMIN SERVER IS RUNNING (PORT 8001) ======")

ROOT = Path(__file__).parent.resolve()
ENV_PATH = ROOT / ".env"

def _read_env_file(path: Path = ENV_PATH) -> dict:
    values = {}
    if not path.exists():
        return values
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            key, value = raw_line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        return values
    return values

_env = _read_env_file()
_pdms_data_root_str = _env.get("PDMS_DATA_ROOT", "").strip()
if not _pdms_data_root_str:
    raise ValueError("發生錯誤: .env 檔案中未設定 PDMS_DATA_ROOT，請務必設定資料儲存路徑。")
DATA_ROOT = Path(_pdms_data_root_str).expanduser()

DB = dict(
    host=_env.get("DB_HOST", "127.0.0.1"),
    port=int(_env.get("DB_PORT", 3306)),
    user=_env.get("DB_USER", ""),
    password=_env.get("DB_PASSWORD", ""),
    database=_env.get("DB_NAME", "testPDMS"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=True,
)


def db_exec(sql, params=None, fetch="none"):
    conn = pymysql.connect(**DB)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            return None
    except Exception as e:
        write_to_console(f"[DB] PyMySQL 執行失敗: {sql}\nError: {e}", "ERROR")
        raise
    finally:
        conn.close()


TASK_MAP = {
    "Ch1-t1": "string_blocks",
    "Ch1-t2": "pyramid",
    "Ch1-t3": "stair",
    "Ch1-t4": "build_wall",
    "Ch2-t1": "draw_circle",
    "Ch2-t2": "draw_square",
    "Ch2-t3": "draw_cross",
    "Ch2-t4": "draw_line",
    "Ch2-t5": "color",
    "Ch2-t6": "connect_dots",
    "Ch3-t1": "cut_circle",
    "Ch3-t2": "cut_square",
    "Ch3-t3": "cut_paper",
    "Ch3-t4": "cut_line",
    "Ch4-t1": "one_fold",
    "Ch4-t2": "two_fold",
    "Ch5-t1": "collect_raisins",
}


def task_id_to_table(task_id: str) -> str:
    if task_id in TASK_MAP:
        return TASK_MAP[task_id]
    row = db_exec("SELECT task_name FROM task_list WHERE task_id=%s", (task_id,), fetch="one")
    if row:
        return row["task_name"]
    raise ValueError(f"未知的 task_id: {task_id}")


# 1. 修正 ensure_user 確保包含生日
def ensure_user(uid: str, name: Optional[str] = None, birthday: Optional[str] = None):
    db_exec(
        "INSERT INTO user_list(uid, name, birthday) VALUES (%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE name=COALESCE(VALUES(name),name), birthday=COALESCE(VALUES(birthday),birthday)",
        (uid, name, birthday),
    )


def ensure_task(task_id: str):
    if task_id not in TASK_MAP:
        raise ValueError(f"未知的 task_id：{task_id}")
    task_name = TASK_MAP[task_id]
    db_exec(
        "INSERT INTO task_list(task_id, task_name) VALUES (%s,%s) ON DUPLICATE KEY UPDATE task_name=VALUES(task_name)",
        (task_id, task_name),
    )



os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

PORT = 8001
HOST = "127.0.0.1"
MACWEB_BASE_URL = _env.get("MACWEB_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
IMAGE_SIGN_SECRET = _env.get("IMAGE_SIGN_SECRET", "")

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app, supports_credentials=True)


# ── AI 顧問 API ──────────────────────────────────────────────────────────────
@app.route("/api/ai_advice/<uid>")
def api_get_ai_advice(uid):
    """
    取得該兒童的 AI 專家建議。
    """
    try:
        advice = advisor.generate_advice(uid)
        return jsonify({"ok": True, "advice": advice})
    except Exception as e:
        write_to_console(f"[AI] generate_advice failed: {e}", "ERROR")
        return jsonify({"ok": False, "msg": str(e)}), 500


def current_user() -> dict:
    return session.get("user") or {}


def user_level(user: dict) -> int:
    try:
        return int(user.get("level") or 0)
    except Exception:
        return 0


def user_allowed_uid(user: dict) -> str:
    return str(user.get("target_uid") or user.get("account") or "").strip()


def can_access_uid(uid: str) -> bool:
    user = current_user()
    level = user_level(user)
    if level <= 0:
        return False
    if level == 1:
        return uid == user_allowed_uid(user)
    return True


def sign_image(uid: str, filename: str) -> str:
    payload = f"{uid}/{filename}".encode("utf-8")
    return hmac.new(
        IMAGE_SIGN_SECRET.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()


def _extract_multi_view_base(filename: str, fallback: str = "") -> str:
    """從帶時間戳的多視角檔名中提取基底（去除 -side/-top/-side_result/-top_result 後綴）。

    例：
        'ch1-t3_20260507_233320-side.jpg'        → 'ch1-t3_20260507_233320'
        'ch1-t3_20260507_233320-side_result.jpg' → 'ch1-t3_20260507_233320'
        'Ch1-t3-side_result.jpg'                 → 'Ch1-t3'  (無時間戳也能處理)
    """
    stem = Path(filename).stem  # 去掉副檔名
    base = re.sub(r'-(side|top)(_result)?$', '', stem, flags=re.IGNORECASE)
    # 若 sub 沒有任何替換（沒找到 -side/-top），base == stem，直接回傳 fallback
    return base if base != stem else (fallback or stem)


def _resolve_image_filename(uid: str, filename: str) -> str:
    """優先使用原檔名；若不存在則嘗試小寫檔名。"""
    candidate_path = DATA_ROOT / uid / filename
    if candidate_path.exists():
        return filename

    lower_name = filename.lower()
    if lower_name != filename and (DATA_ROOT / uid / lower_name).exists():
        return lower_name

    return filename


def build_signed_image_url(uid: str, filename: str) -> str:
    filename = _resolve_image_filename(uid, filename)
    sig = sign_image(uid, filename)
    return f"{MACWEB_BASE_URL}/images/{uid}/{filename}?sig={sig}"


def extract_uid_filename(path_or_url: str):
    raw = (path_or_url or "").strip()
    if not raw:
        return None, None
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        clean_path = parsed.path or ""
    else:
        clean_path = raw

    parts = [p for p in clean_path.strip("/").split("/") if p]
    if len(parts) >= 3 and parts[0] in ("kid", "images"):
        return parts[1], parts[2]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None, None



def write_to_console(message, level="INFO"):
    console_path = ROOT / "console.txt"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(console_path, "a", encoding="utf-8") as f:
            f.write(f"{ts} - {level} - {message}\n")
    except Exception:
        pass


@app.errorhandler(Exception)
def _handle_err(e):
    if isinstance(e, HTTPException):
        return jsonify({"success": False, "error": str(e)}), e.code
    write_to_console(
        f"[ERR] {request.method} {request.path}\n{traceback.format_exc()}", "ERROR"
    )
    return jsonify({"success": False, "error": str(e)}), 500


# 靜態檔案路由
@app.route("/")
def root_redirect():
    return redirect("/html/admin_login.html")


@app.route("/admin")
@app.route("/admin.html")
def admin_shortcut():
    return send_from_directory(ROOT / "html", "admin.html")


@app.route("/html/<path:filename>")
def html_files(filename):
    return send_from_directory(ROOT / "html", filename)


@app.route("/css/<path:filename>")
def css_files(filename):
    return send_from_directory(ROOT / "css", filename)


@app.route("/js/<path:filename>")
def js_files(filename):
    return send_from_directory(ROOT / "js", filename)


@app.route("/images/<path:filename>")
def images_files(filename):
    return send_from_directory(ROOT / "images", filename)


@app.route("/view-compare")
def view_compare():
    user = current_user()
    if not user:
        return "Unauthorized", 401

    uid = request.args.get("uid", "")
    task_id = request.args.get("task_id", "")
    img_path = request.args.get("img", "")

    if not uid or not task_id:
        return "Missing uid or task_id", 400
    if not can_access_uid(uid):
        return "Forbidden", 403

    is_multi = task_id in {"Ch1-t2", "Ch1-t3", "Ch1-t4"}

    content_html = ""
    if is_multi:
        # ── 取得帶時間戳的真實基底名稱 ──────────────────────────────────────
        # 優先從 URL 參數 img（scores 列表頁傳來的已簽名 URL）中提取
        view_base = task_id  # fallback
        img_uid, img_filename = extract_uid_filename(img_path)
        if img_uid == uid and img_filename:
            view_base = _extract_multi_view_base(img_filename, task_id)
        else:
            # img_path 沒資訊，改查資料庫取得最新的 result_img_path
            try:
                table = task_id_to_table(task_id)
                row = db_exec(
                    f"SELECT result_img_path FROM `{table}` WHERE uid=%s "
                    f"ORDER BY test_date DESC, time DESC LIMIT 1",
                    (uid,),
                    fetch="one",
                )
                db_path = (row or {}).get("result_img_path") or ""
                _, db_filename = extract_uid_filename(db_path)
                if db_filename:
                    view_base = _extract_multi_view_base(db_filename, task_id)
            except Exception:
                pass
        # ────────────────────────────────────────────────────────────────────

        side_orig = build_signed_image_url(uid, f"{view_base}-side.jpg")
        side_res  = build_signed_image_url(uid, f"{view_base}-side_result.jpg")
        top_orig  = build_signed_image_url(uid, f"{view_base}-top.jpg")
        top_res   = build_signed_image_url(uid, f"{view_base}-top_result.jpg")
        content_html = f"""
        <div class=\"section-title\">側面視角 (Side View)</div>
        <div class=\"row\">
            <div class=\"box\"><h3>原始照片</h3><img src=\"{side_orig}\" onerror=\"this.onerror=null;this.src='/images/no_image.png';\"></div>
            <div class=\"box\"><h3>分析結果</h3><img src=\"{side_res}\" onerror=\"this.onerror=null;this.src='/images/no_image.png';\"></div>
        </div>
        <div class=\"section-title\" style=\"margin-top:40px;border-top:2px dashed #ddd;padding-top:20px;\">頂部視角 (Top View)</div>
        <div class=\"row\">
            <div class=\"box\"><h3>原始照片</h3><img src=\"{top_orig}\" onerror=\"this.onerror=null;this.src='/images/no_image.png';\"></div>
            <div class=\"box\"><h3>分析結果</h3><img src=\"{top_res}\" onerror=\"this.onerror=null;this.src='/images/no_image.png';\"></div>
        </div>
        """
    else:
        img_uid, img_filename = extract_uid_filename(img_path)
        if img_uid == uid and img_filename:
            base_stem, _ = os.path.splitext(img_filename)
            for suffix in ("_detected", "_result"):
                if base_stem.endswith(suffix):
                    base_stem = base_stem[: -len(suffix)]
                    break
        else:
            base_stem = task_id

        original_name = f"{base_stem}.jpg"
        result_name = f"{base_stem}_result.jpg"

        original_src = build_signed_image_url(uid, original_name)
        result_src = build_signed_image_url(uid, result_name)
        content_html = f"""
        <div class=\"row\">
            <div class=\"box\"><h3>原始照片 (Original)</h3><img src=\"{original_src}\" onerror=\"this.onerror=null;this.src='/images/no_image.png';\"></div>
            <div class=\"box\"><h3>分析結果 (Result)</h3><img src=\"{result_src}\" onerror=\"this.onerror=null;this.src='/images/no_image.png';\"></div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang=\"zh-TW\">
    <head>
        <meta charset=\"UTF-8\">
        <title>作答結果比對 - {uid} - {task_id}</title>
        <style>
            body {{ font-family: \"Microsoft JhengHei\", sans-serif; text-align: center; padding: 20px; background: #f0f2f5; }}
            h2 {{ color: #333; margin-bottom: 10px; }}
            .sub-info {{ color: #666; margin-bottom: 30px; font-size: 0.9em; }}
            .row {{ display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; margin-bottom: 20px; }}
            .box {{ background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); width: 45%; min-width: 300px; }}
            .box h3 {{ margin: 0 0 10px 0; color: #555; font-size: 16px; border-bottom: 1px solid #eee; padding-bottom: 8px; }}
            img {{ max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #eee; }}
            .section-title {{ font-size: 18px; font-weight: bold; color: #2c3e50; margin: 10px 0; display: inline-block; background: #e0f2fe; padding: 5px 15px; border-radius: 20px; }}
        </style>
    </head>
    <body>
        <h2>使用者: {uid} / 關卡: {task_id}</h2>
        <div class=\"sub-info\">檢視模式: {"多視角" if is_multi else "單一視角"}</div>
        {content_html}
    </body>
    </html>
    """
    return html


# -------------------------
# 身份驗證 API
# -------------------------
@app.post("/api/auth/login")
def api_login():
    data = request.get_json() or {}
    account, password = (data.get("account") or "").strip(), (
        data.get("password") or ""
    ).strip()
    if not account or not password:
        return jsonify({"ok": False, "msg": "請輸入帳號與密碼"}), 400
    row = db_exec(
        "SELECT account, password, email, level FROM admin_users WHERE account=%s",
        (account,),
        fetch="one",
    )
    stored_pw = (row["password"] or "").replace("-", "") if row else ""
    if (not row) or stored_pw != password:
        return jsonify({"ok": False, "msg": "帳號或密碼錯誤"}), 401
    session["user"] = {
        "account": row["account"],
        "level": int(row.get("level") or 0),
        "name": row.get("email") or row["account"],
    }
    return jsonify({"ok": True, "user": session["user"]})


@app.get("/api/auth/whoami")
def api_whoami():
    user = session.get("user")
    return (
        jsonify({"ok": True, "logged_in": True, "user": user})
        if user
        else jsonify({"ok": True, "logged_in": False})
    )


@app.post("/api/auth/logout")
def api_logout():
    session.pop("user", None)
    return jsonify({"ok": True})


@app.post("/api/auth/update_profile")
def api_update_profile():
    user = session.get("user")
    if not user:
        return jsonify({"ok": False, "msg": "未登入"}), 401

    data = request.get_json() or {}
    old_pwd = data.get("old_password", "").strip()
    new_pwd = data.get("new_password", "").strip()
    account = user["account"]

    if not old_pwd or not new_pwd:
        return jsonify({"ok": False, "msg": "所有欄位不可為空"}), 400

    row = db_exec(
        "SELECT password FROM admin_users WHERE account=%s",
        (account,),
        fetch="one",
    )
    stored_pw = (row["password"] or "").replace("-", "") if row else ""
    if stored_pw != old_pwd:
        return jsonify({"ok": False, "msg": "舊密碼錯誤"}), 403

    try:
        db_exec(
            "UPDATE admin_users SET password=%s WHERE account=%s",
            (new_pwd, account),
        )
        session.pop("user", None)
        return jsonify({"ok": True, "msg": "密碼修改成功，請重新登入"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500


# -------------------------
# 資料操作 API
# -------------------------
@app.get("/api/tasks")
def api_tasks():
    user = session.get("user")
    if not user:
        return jsonify({"ok": False, "msg": "未登入"}), 401
    rows = db_exec("SELECT task_id, task_name FROM task_list ORDER BY task_id", fetch="all") or []
    tasks = [{"task_id": r["task_id"], "task_name": r["task_name"]} for r in rows]
    return jsonify({"ok": True, "tasks": tasks})


@app.get("/scores")
def list_scores():
    try:
        user = session.get("user")
        if not user:
            return jsonify({"success": False, "error": "尚未登入"}), 401
        level, account = int(user.get("level") or 0), user.get("account")
        all_rows_raw = []
        db_tasks = db_exec("SELECT task_id, task_name FROM task_list", fetch="all") or []
        effective_map = {r["task_id"]: r["task_name"] for r in db_tasks} or TASK_MAP
        for task_id, table_name in effective_map.items():
            sql = f"""
                SELECT s.uid, u.name, s.task_id, t.task_name, d.score, d.result_img_path, s.test_date, d.time
                FROM score_list AS s
                JOIN user_list AS u ON u.uid = s.uid
                JOIN task_list AS t ON t.task_id = s.task_id
                LEFT JOIN `{table_name}` AS d ON d.uid = s.uid AND d.test_date = s.test_date
                WHERE s.task_id = %s
            """
            params = [task_id]
            if level == 1:  # 🔐 家長過濾：帳號與 UID 綁定
                sql += " AND s.uid = %s"
                params.append(account)
            rows = db_exec(sql, tuple(params), fetch="all") or []
            all_rows_raw.extend(rows)

        def _date_to_str(rows):
            for r in rows or []:
                r = dict(r)
                td = r.get("test_date")
                if isinstance(td, (date, datetime)):
                    r["test_date"] = td.isoformat()
                t = r.get("time")
                if t is not None and not isinstance(t, str):
                    total = int(t.total_seconds())
                    r["time"] = f"{total//3600:02d}:{(total%3600)//60:02d}:{total%60:02d}"
                yield r

        rows = list(_date_to_str(all_rows_raw))
        for r in rows:
            uid = (r.get("uid") or "").strip()
            task_id = (r.get("task_id") or "").strip()
            r["row_key"] = f"{uid}|{task_id}|{r.get('test_date') or ''}|{r.get('time') or ''}"

            # Level 1 防呆：即使資料層有過濾，也在輸出層再次限制
            if not can_access_uid(uid):
                r["result_img_url"] = None
                r["compare_url"] = None
                continue

            db_path = (r.get("result_img_path") or "").strip()
            img_uid, img_filename = extract_uid_filename(db_path)
            if img_uid and img_uid != uid:
                img_filename = None
            if img_filename:
                signed_img = build_signed_image_url(uid, img_filename)
                r["result_img_url"] = signed_img
                r["compare_url"] = (
                    f"/view-compare?{urlencode({'uid': uid, 'task_id': task_id, 'img': signed_img})}"
                )
            else:
                r["result_img_url"] = None
                r["compare_url"] = None

        rows.sort(
            key=lambda r: (
                r.get("test_date") or "",
                r.get("time") or "",
                r.get("uid") or "",
                r.get("task_id") or "",
            ),
            reverse=True,
        )
        return jsonify(rows)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.get("/users")
def list_users():
    try:
        user = session.get("user")
        if not user:
            return jsonify({"ok": False, "msg": "未登入"}), 401
        level, account = int(user.get("level") or 0), user.get("account")
        if level == 1:
            rows = db_exec(
                "SELECT uid FROM user_list WHERE uid = %s ORDER BY uid",
                (account,),
                fetch="all",
            )
        else:
            rows = db_exec("SELECT uid FROM user_list ORDER BY uid", fetch="all")
        return jsonify({"ok": True, "users": [r["uid"] for r in (rows or [])]})
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500


# 2. 修改 api_add_user：連動建立家長帳號，帳號=UID, 密碼=生日
@app.post("/api/user/add")
def api_add_user():
    try:
        user_level = int(session.get("user", {}).get("level", 0))
        if user_level < 2:
            return jsonify({"ok": False, "msg": "權限不足"}), 403

        data = request.get_json() or {}
        uid = data.get("uid", "").strip()
        name = data.get("name", "").strip()
        birthday = data.get("birthday", "").strip()

        if not uid or not birthday:
            return jsonify({"ok": False, "msg": "UID 與生日不可為空"}), 400

        # A. 寫入受測者基本資料
        ensure_user(uid, name, birthday)

        # B. 同步建立 Level 1 家長登入權限
        # 帳號預設為 uid, 密碼預設為 birthday
        db_exec(
            "INSERT INTO admin_users (account, password, email, level) VALUES (%s, %s, %s, 1) "
            "ON DUPLICATE KEY UPDATE password=COALESCE(password, VALUES(password))",
            (uid, birthday, f"{name}@parent.com"),
        )
        return jsonify({"ok": True, "msg": "受測者與家長帳號已同步建立成功！"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500


# 🔐 Level 3 專用：手動修改紀錄
@app.post("/scores/upsert")
def upsert_score():
    try:
        user_level = int(session.get("user", {}).get("level", 0))
        if user_level < 3:
            return (
                jsonify({"ok": False, "msg": "只有主管(等級3)可以手動新增/修改分數"}),
                403,
            )

        data = request.get_json() or {}
        uid = data.get("uid", "").strip()
        task_id = data.get("task_id", "").strip()
        score = int(data.get("score", 0))
        test_date_str = data.get("test_date", "").strip()

        if not uid or not task_id:
            return jsonify({"ok": False, "msg": "uid/task_id 不可為空"}), 400

        # 轉換日期
        test_date = (
            datetime.strptime(test_date_str, "%Y-%m-%d").date()
            if test_date_str
            else date.today()
        )

        ensure_user(uid)  # 確保 user_list 有這名小朋友
        ensure_task(task_id)

        # 1. 寫入總表：若已存在同人、同天、同關卡的紀錄，則不做任何事 (保持連結)
        db_exec(
            "INSERT INTO score_list (uid, task_id, test_date) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE test_date = VALUES(test_date)",
            (uid, task_id, test_date),
        )

        # 2. 寫入任務表：若已存在同人、同天的紀錄，則直接更新分數 (達成「取最新筆」)
        table = task_id_to_table(task_id)
        db_exec(
            f"INSERT INTO `{table}` (uid, test_date, score) VALUES (%s, %s, %s) "
            f"ON DUPLICATE KEY UPDATE score = VALUES(score)",
            (uid, test_date, score),
        )

        return jsonify({"ok": True, "msg": "紀錄已更新"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500


@app.delete("/scores")
def delete_score():
    try:
        if int(session.get("user", {}).get("level", 0)) < 3:
            return jsonify({"ok": False, "msg": "權限不足"}), 403
        row_key = request.args.get("row_key")
        if not row_key:
            return jsonify({"ok": False, "msg": "遺失 row_key"}), 400
        parts = row_key.split("|", 3)
        uid, task_id, test_date = parts[0], parts[1], parts[2]
        time_val = parts[3] if len(parts) == 4 else ""
        table = task_id_to_table(task_id)
        if time_val:
            db_exec(f"DELETE FROM `{table}` WHERE uid=%s AND test_date=%s AND time=%s", (uid, test_date, time_val))
        else:
            db_exec(f"DELETE FROM `{table}` WHERE uid=%s AND test_date=%s", (uid, test_date))
        remaining = db_exec(f"SELECT COUNT(*) AS cnt FROM `{table}` WHERE uid=%s AND test_date=%s", (uid, test_date), fetch="one")
        if not remaining or remaining.get("cnt", 0) == 0:
            db_exec("DELETE FROM score_list WHERE uid=%s AND task_id=%s AND test_date=%s", (uid, task_id, test_date))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500


# ── SSE 即時推播 ──────────────────────────────────────────────────────────────
_sse_lock = threading.Lock()
_sse_subscribers: set[queue.Queue] = set()


def _broadcast_score_updated():
    with _sse_lock:
        dead = set()
        for q in _sse_subscribers:
            try:
                q.put_nowait("score-updated")
            except queue.Full:
                dead.add(q)
        _sse_subscribers.difference_update(dead)


@app.get("/events")
def sse_events():
    if not session.get("user"):
        return jsonify({"error": "未登入"}), 401

    def stream():
        q: queue.Queue = queue.Queue(maxsize=10)
        with _sse_lock:
            _sse_subscribers.add(q)
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    q.get(timeout=25)
                    yield "event: score-updated\ndata: 1\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with _sse_lock:
                _sse_subscribers.discard(q)

    from flask import Response
    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/internal/score-updated")
def internal_score_updated():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        return jsonify({"ok": False}), 403
    _broadcast_score_updated()
    return jsonify({"ok": True})


# ── 醫療人員帳號管理（Level 3 專用）────────────────────────────────────────────
def _require_superadmin():
    user = session.get("user")
    if not user:
        return jsonify({"ok": False, "msg": "未登入"}), 401
    if int(user.get("level") or 0) < 3:
        return jsonify({"ok": False, "msg": "權限不足，需要主管等級"}), 403
    return None


@app.get("/api/admin/list")
def api_admin_list():
    err = _require_superadmin()
    if err:
        return err
    rows = db_exec(
        "SELECT account, email, level FROM admin_users WHERE level = 2 ORDER BY account",
        fetch="all",
    ) or []
    admins = [{"account": r["account"], "name": r.get("email") or r["account"], "level": r["level"]} for r in rows]
    return jsonify({"ok": True, "admins": admins})


@app.post("/api/admin/add")
def api_admin_add():
    err = _require_superadmin()
    if err:
        return err
    data = request.get_json() or {}
    account = (data.get("account") or "").strip()
    password = (data.get("password") or "123456").strip()
    email = (data.get("email") or "").strip()
    if not account:
        return jsonify({"ok": False, "msg": "帳號不可為空"}), 400
    existing = db_exec("SELECT account FROM admin_users WHERE account=%s", (account,), fetch="one")
    if existing:
        return jsonify({"ok": False, "msg": "帳號已存在"}), 409
    db_exec(
        "INSERT INTO admin_users (account, password, email, level) VALUES (%s, %s, %s, 2)",
        (account, password, email),
    )
    return jsonify({"ok": True, "msg": "醫療人員帳號已建立"})


@app.put("/api/admin/update/<account_id>")
def api_admin_update(account_id):
    err = _require_superadmin()
    if err:
        return err
    data = request.get_json() or {}
    new_account = (data.get("account") or "").strip()
    new_email = (data.get("email") or "").strip()
    new_password = (data.get("password") or "").strip()
    if not new_account:
        return jsonify({"ok": False, "msg": "帳號不可為空"}), 400
    row = db_exec("SELECT account, level FROM admin_users WHERE account=%s", (account_id,), fetch="one")
    if not row:
        return jsonify({"ok": False, "msg": "帳號不存在"}), 404
    if int(row.get("level") or 0) != 2:
        return jsonify({"ok": False, "msg": "只能修改醫療人員帳號"}), 403
    fields, params = [], []
    if new_account != account_id:
        fields.append("account=%s"); params.append(new_account)
    if new_email:
        fields.append("email=%s"); params.append(new_email)
    if new_password:
        fields.append("password=%s"); params.append(new_password)
    if fields:
        params.append(account_id)
        db_exec(f"UPDATE admin_users SET {', '.join(fields)} WHERE account=%s", tuple(params))
    return jsonify({"ok": True, "msg": "帳號已更新"})


@app.delete("/api/admin/delete/<account_id>")
def api_admin_delete(account_id):
    err = _require_superadmin()
    if err:
        return err
    row = db_exec("SELECT account, level FROM admin_users WHERE account=%s", (account_id,), fetch="one")
    if not row:
        return jsonify({"ok": False, "msg": "帳號不存在"}), 404
    if int(row.get("level") or 0) != 2:
        return jsonify({"ok": False, "msg": "只能刪除醫療人員帳號"}), 403
    db_exec("DELETE FROM admin_users WHERE account=%s", (account_id,))
    return jsonify({"ok": True, "msg": "帳號已刪除"})


def _open_browser():
    webbrowser.open(f"http://{HOST}:{PORT}/")


if __name__ == "__main__":
    threading.Timer(0.5, _open_browser).start()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
