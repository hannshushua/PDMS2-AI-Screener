from __future__ import annotations

import logging
import os
import re
import hmac
import hashlib
import shutil
import subprocess
import sys

from pathlib import Path
from datetime import date, datetime

import pymysql
from flask import Flask, jsonify, request, send_file, session


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / "PDMS2_web" / ".env"

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "web.log"


def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("MacWeb")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


logger = _setup_logging()

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

def _resolve_data_root() -> Path:
    env_root = os.environ.get("PDMS_DATA_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()

    default_root = (BASE_DIR / "PDMS2").resolve()
    if default_root.exists():
        return default_root

    fallback_root = Path.home() / "Desktop" / "PDMS"
    if fallback_root.exists():
        return fallback_root.resolve()

    return default_root


DATA_ROOT = _resolve_data_root()
ANALYSIS_ROOT = (BASE_DIR.parent / "PDMS2_web").resolve()
ANALYSIS_KID_ROOT = ANALYSIS_ROOT / "kid"
UID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
FILE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Pattern to detect / strip embedded timestamps like _20260507_233320
_TS_PATTERN = re.compile(r"_\d{8}_\d{6}")


def _strip_ts(stem: str) -> str:
    """Remove _YYYYMMDD_HHMMSS from a filename stem."""
    return _TS_PATTERN.sub("", stem)


IMAGE_SIGN_SECRET = _env.get("IMAGE_SIGN_SECRET", "")

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

app = Flask(__name__, static_folder="public", static_url_path="")
app.secret_key = os.environ.get("WEB_SECRET_KEY", "dev-only-secret-change-me")

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


def db_exec(sql: str, params=None, fetch: str = "none"):
    conn = None
    try:
        conn = pymysql.connect(**DB)
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            return None
    finally:
        if conn:
            conn.close()


def task_id_to_table(task_id: str) -> str:
    if task_id in TASK_MAP:
        return TASK_MAP[task_id]
    raise ValueError(f"未知的 task_id: {task_id}")


def table_columns(table_name: str) -> set[str]:
    try:
        rows = db_exec(f"SHOW COLUMNS FROM `{table_name}`", fetch="all") or []
    except Exception:
        return set()
    columns = set()
    for row in rows:
        field_name = row.get("Field") if isinstance(row, dict) else None
        if field_name:
            columns.add(str(field_name))
    return columns


def upsert_row(table_name: str, values: dict, update_columns: list[str] | None = None) -> None:
    columns = list(values.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(f"`{column}`" for column in columns)
    sql = f"INSERT INTO `{table_name}` ({column_sql}) VALUES ({placeholders})"

    if update_columns:
        update_sql = ", ".join(
            f"`{column}` = VALUES(`{column}`)" for column in update_columns if column in values
        )
        if update_sql:
            sql += f" ON DUPLICATE KEY UPDATE {update_sql}"

    db_exec(sql, tuple(values[column] for column in columns))


def write_remote_results(uid: str, img_id: str, score: int, cwd_root: Path, timestamp: str = None) -> None:
    today = date.today()
    now_time = datetime.now().strftime("%H:%M:%S")
    # Normalize to capital-C format for DB (e.g. ch1-t1 → Ch1-t1)
    normalized_id = img_id[0].upper() + img_id[1:] if img_id else img_id

    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 搜尋所有與該任務相關的影像（原圖與結果圖）
    # 例如：Ch1-t1.jpg, Ch1-t1_result.jpg
    analysis_uid_dir = cwd_root / "kid" / uid
    dest_dir = DATA_ROOT / uid
    dest_dir.mkdir(parents=True, exist_ok=True)

    result_img_path = ""
    
    # 找出所有與該任務相關的影像（case-insensitive，比對開頭）
    pattern = re.compile(re.escape(img_id), re.IGNORECASE)
    # 檢測 timestamp 格式 _YYYYMMDD_HHMMSS，若檔名已含此格式則代表已被處理過，應跳過
    ts_pattern = re.compile(r"_\d{8}_\d{6}")
    
    for file_path in safe_list_dir(analysis_uid_dir) or []:
        if not file_path.is_file():
            continue

        # 只處理影像副檔名
        if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        # 如果檔名已包含任何 timestamp 格式，跳過（代表已被處理過）
        if ts_pattern.search(file_path.stem):
            continue

        ext = file_path.suffix
        stem = file_path.stem

        if not pattern.search(stem):
            continue

        # 用不區分大小寫的方式，在第一次匹配處插入 timestamp，保留原始匹配的大小寫
        def _insert_ts(m):
            return f"{m.group(0)}_{timestamp}"

        new_stem = pattern.sub(_insert_ts, stem, count=1)
        new_name = f"{new_stem}{ext}"
        new_path = file_path.with_name(new_name)

        try:
            shutil.move(file_path, new_path)
        except Exception:
            # 若移動失敗，嘗試以拷貝方式建立目標檔，再刪除原檔
            try:
                shutil.copyfile(file_path, new_path)
                file_path.unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("[Analysis] 無法重命名或複製影像: %s", exc)
                continue

        dest_path = dest_dir / new_name

        # 檢查 DATA_ROOT 目標檔案是否已存在（case-insensitive），若存在則跳過複製以避免重複
        existing = None
        try:
            for p in dest_dir.iterdir():
                if p.is_file() and p.name.lower() == new_name.lower():
                    existing = p
                    break
        except Exception:
            existing = None

        if existing:
            logger.info("[Analysis] Destination already exists; skipping copy: %s", existing)
            used_name = existing.name
        else:
            try:
                shutil.copyfile(new_path, dest_path)
                logger.info("[Analysis] Saved unique image to %s", dest_path)
                used_name = new_name
            except Exception as exc:
                logger.warning("[Analysis] 無法複製 unique 影像到 DATA_ROOT: %s", exc)
                continue

        lname = used_name.lower()
        if "result" in lname or "detected" in lname:
            if not result_img_path or "-side" not in result_img_path:
                result_img_path = f"kid/{uid}/{used_name}"
        elif not result_img_path:
            result_img_path = f"kid/{uid}/{used_name}"

    summary_columns = table_columns("score_list")
    summary_values = {"uid": uid, "task_id": normalized_id, "test_date": today}
    if "score" in summary_columns:
        summary_values["score"] = int(score)
    if "time" in summary_columns:
        summary_values["time"] = now_time
    summary_updates = [column for column in summary_values.keys() if column != "uid" and column != "task_id"]
    upsert_row("score_list", summary_values, update_columns=summary_updates)

    try:
        task_table = task_id_to_table(normalized_id)
    except Exception as exc:
        print(f"[Analysis] 跳過任務子表寫入: {exc}")
        return

    task_columns = table_columns(task_table)
    if not task_columns:
        print(f"[Analysis] 找不到任務子表欄位: {task_table}")
        return

    task_values = {}
    if "uid" in task_columns:
        task_values["uid"] = uid
    if "test_date" in task_columns:
        task_values["test_date"] = today
    if "time" in task_columns:
        task_values["time"] = now_time
    if "score" in task_columns:
        task_values["score"] = int(score)
    if "result_img_path" in task_columns:
        task_values["result_img_path"] = result_img_path
    if "data1" in task_columns:
        task_values["data1"] = None

    if not task_values:
        print(f"[Analysis] 任務子表 {task_table} 沒有可寫入欄位")
        return

    update_columns = [column for column in task_values.keys() if column not in {"uid", "test_date", "time"}]
    upsert_row(task_table, task_values, update_columns=update_columns)


def is_valid_uid(uid: str) -> bool:
    return bool(UID_PATTERN.fullmatch(uid))


def is_valid_filename(filename: str) -> bool:
    return bool(FILE_PATTERN.fullmatch(filename))


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def safe_list_dir(target: Path) -> list[Path] | None:
    if not target.exists() or not target.is_dir():
        return None
    return list(target.iterdir())


def is_under_data_root(file_path: Path) -> bool:
    root = DATA_ROOT.resolve()
    candidate = file_path.resolve()
    return root == candidate or root in candidate.parents


def resolve_image_path(uid: str, filename: str) -> Path | None:
    req_stem = Path(filename).stem
    req_ext = Path(filename).suffix.lower()
    # The stem requested by admin may lack a timestamp (e.g. "Ch1-t3-side_result").
    # Normalise it so we can compare against stripped actual stems.
    req_stem_stripped = _strip_ts(req_stem).lower()

    def _fuzzy_match(directory: Path, check_data_root: bool = False) -> Path | None:
        """Return the best (most-recently-timestamped) file whose stripped-stem matches."""
        if not directory.exists() or not directory.is_dir():
            return None
        candidates: list[tuple[str, Path]] = []
        for p in directory.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() != req_ext:
                continue
            if check_data_root and not is_under_data_root(p.resolve()):
                continue
            actual_stripped = _strip_ts(p.stem).lower()
            if actual_stripped == req_stem_stripped:
                # Extract the raw timestamp string (if any) for sorting
                ts_match = _TS_PATTERN.search(p.stem)
                ts_key = ts_match.group(0) if ts_match else ""
                candidates.append((ts_key, p))
        if not candidates:
            return None
        # Return the file with the latest timestamp
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1].resolve()

    # 1. 先嘗試在 DATA_ROOT 中精確尋找
    uid_dir = DATA_ROOT / uid
    if uid_dir.exists() and uid_dir.is_dir() and is_under_data_root(uid_dir):
        direct = (uid_dir / filename).resolve()
        if is_under_data_root(direct) and direct.exists() and direct.is_file():
            return direct

        # 2. 大小寫不敏感精確比對
        lower_name = filename.lower()
        for p in uid_dir.iterdir():
            if p.is_file() and p.name.lower() == lower_name:
                if is_under_data_root(p.resolve()):
                    return p.resolve()

        # 3. 模糊比對：忽略檔名中嵌入的 timestamp（如 _20260507_233320）
        fuzzy = _fuzzy_match(uid_dir, check_data_root=True)
        if fuzzy:
            return fuzzy

    # 4. 如果在 DATA_ROOT 找不到，fallback 到 ANALYSIS_KID_ROOT/{uid}
    analysis_uid_dir = ANALYSIS_KID_ROOT / uid
    if analysis_uid_dir.exists() and analysis_uid_dir.is_dir():
        lower_name = filename.lower()
        for p in analysis_uid_dir.iterdir():
            if p.is_file() and p.name.lower() == lower_name:
                return p.resolve()

        # 5. ANALYSIS_KID_ROOT 中也做模糊比對
        fuzzy = _fuzzy_match(analysis_uid_dir)
        if fuzzy:
            return fuzzy

    return None


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


def is_valid_signature(uid: str, filename: str, sig: str) -> bool:
    if not sig:
        return False
    expected = sign_image(uid, filename)
    return hmac.compare_digest(expected, sig)


def require_login() -> tuple[bool, object | None]:
    if not current_user():
        return False, (jsonify({"message": "Unauthorized"}), 401)
    return True, None


@app.post("/api/auth/login")
def api_login() -> object:
    data = request.get_json() or {}
    account = (data.get("account") or "").strip()
    password = (data.get("password") or "").strip()
    if not account or not password:
        return jsonify({"ok": False, "msg": "請輸入帳號與密碼"}), 400

    row = db_exec(
        "SELECT account, password, email, level FROM admin_users WHERE account=%s AND password=%s",
        (account, password),
        fetch="one",
    )
    if row:
        session["user"] = {
            "account": row["account"],
            "level": int(row.get("level") or 2),
            "name": row.get("email"),
            "target_uid": None,
        }
        return jsonify({"ok": True, "user": session["user"]})

    user_row = db_exec(
        "SELECT uid, name, birthday FROM user_list WHERE uid=%s",
        (account,),
        fetch="one",
    )
    if user_row:
        db_birth = user_row["birthday"]
        db_birth_str = (
            db_birth.isoformat()
            if isinstance(db_birth, (date, datetime))
            else str(db_birth or "")
        )
        if db_birth_str == password:
            session["user"] = {
                "account": user_row["uid"],
                "level": 1,
                "name": user_row["name"] or user_row["uid"],
                "target_uid": user_row["uid"],
            }
            return jsonify({"ok": True, "user": session["user"]})

    return jsonify({"ok": False, "msg": "帳號或密碼錯誤"}), 401


@app.get("/api/auth/whoami")
def api_whoami() -> object:
    user = current_user()
    if not user:
        return jsonify({"ok": True, "logged_in": False})
    return jsonify({"ok": True, "logged_in": True, "user": user})


@app.post("/api/auth/logout")
def api_logout() -> object:
    session.pop("user", None)
    return jsonify({"ok": True})


@app.get("/")
def index() -> object:
    return app.send_static_file("index.html")


@app.get("/api/uids")
def get_uids() -> object:
    ok, resp = require_login()
    if not ok:
        return resp

    user = current_user()
    if user_level(user) == 1:
        own_uid = user_allowed_uid(user)
        if not own_uid:
            return jsonify({"uids": []})
        return jsonify({"uids": [own_uid]})

    items = safe_list_dir(DATA_ROOT)
    if items is None:
        return jsonify({"message": "PDMS2 folder not found."}), 404

    uids = sorted(
        [item.name for item in items if item.is_dir() and is_valid_uid(item.name)]
    )
    return jsonify({"uids": uids})


@app.get("/api/images")
def get_images() -> object:
    ok, resp = require_login()
    if not ok:
        return resp

    uid = str(request.args.get("uid", "")).strip()
    if not is_valid_uid(uid):
        return jsonify({"message": "Invalid uid."}), 400
    if not can_access_uid(uid):
        return jsonify({"message": "Forbidden"}), 403

    uid_dir = DATA_ROOT / uid
    items = safe_list_dir(uid_dir)
    if items is None:
        return jsonify({"message": "uid folder not found."}), 404

    files = sorted(
        [
            item.name
            for item in items
            if item.is_file() and get_extension(item.name) in ALLOWED_EXTENSIONS
        ]
    )
    return jsonify({"uid": uid, "files": files})


@app.get("/images/<uid>/<filename>")
def get_image(uid: str, filename: str) -> object:
    if not is_valid_uid(uid) or not is_valid_filename(filename):
        return "Bad request.", 400

    if get_extension(filename) not in ALLOWED_EXTENSIONS:
        return "Only image files are allowed.", 400

    absolute_path = resolve_image_path(uid, filename)
    if absolute_path is None:
        return "Image not found.", 404

    signed_ok = is_valid_signature(
        uid, filename, str(request.args.get("sig", "")).strip()
    )
    session_ok = bool(current_user()) and can_access_uid(uid)
    if not signed_ok and not session_ok:
        if current_user():
            return "Forbidden", 403
        return "Unauthorized", 401

    return send_file(absolute_path)


def run_remote_analysis(uid: str, img_id: str, script_path: Path) -> int:
    """執行分析腳本，回傳分數 (0/1/2)"""
    cmd = [sys.executable, str(script_path), uid, img_id]
    logger.info("[Analysis] Running: %s", " ".join(cmd))

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    result = subprocess.Popen(
        cmd,
        cwd=ANALYSIS_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    assert result.stdout is not None
    for raw_line in iter(result.stdout.readline, ""):
        line = raw_line.rstrip("\n")
        if line:
            logger.info("[Analysis][stdout] %s", line)

    result.stdout.close()
    return_code = result.wait()

    score = return_code if return_code in (0, 1, 2) else 0
    logger.info("[Analysis] Done: uid=%s, img_id=%s, score=%s", uid, img_id, score)
    return score


@app.post("/api/analysis/submit")
def api_submit_analysis():
    """接收圖片並啟動遠端分析"""
    uid = request.form.get("uid")
    img_id = request.form.get("img_id")  # 例如 ch1-t1
    timestamp = request.form.get("timestamp")
    files = request.files.getlist("images")

    if not uid or not img_id or not files:
        return jsonify({"ok": False, "msg": "缺少參數"}), 400

    if not is_valid_uid(uid):
        return jsonify({"ok": False, "msg": "無效的 UID"}), 400

    # 1. 儲存圖片
    uid_dir = DATA_ROOT / uid
    uid_dir.mkdir(parents=True, exist_ok=True)
    ANALYSIS_KID_ROOT.mkdir(parents=True, exist_ok=True)
    analysis_uid_dir = ANALYSIS_KID_ROOT / uid
    analysis_uid_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        if not file.filename:
            continue
        save_path = uid_dir / file.filename
        file.save(save_path)
        logger.info("[Submit] Saved image to %s", save_path)

        analysis_save_path = analysis_uid_dir / file.filename
        try:
            shutil.copyfile(save_path, analysis_save_path)
        except Exception as exc:
            logger.error("[Submit] 複製圖片失敗: %s", exc)

    # 2. 尋找腳本
    project_root = BASE_DIR.parent
    possible_paths = [
        project_root / "PDMS2_web" / img_id / "main.py",
        project_root / "PDMS2_web" / img_id.lower() / "main.py",
    ]
    script_path = None
    for p in possible_paths:
        if p.exists():
            script_path = p
            break

    if not script_path:
        return jsonify({"ok": False, "msg": f"找不到分析腳本: {img_id}"}), 404

    # 3. 同步執行分析
    try:
        score = run_remote_analysis(uid, img_id, script_path)
        # 4. 將成績寫回遠端 DB
        write_remote_results(uid, img_id, score, ANALYSIS_ROOT, timestamp)
        return jsonify({"ok": True, "msg": "分析完成", "score": score})
    except Exception as e:
        logger.exception("[Submit] Analysis error: %s", e)
        return jsonify({"ok": False, "msg": f"分析失敗: {e}"}), 500


if __name__ == "__main__":
    logger.info("[MacWeb] DATA_ROOT = %s", DATA_ROOT)
    app.run(host="0.0.0.0", port=3000, debug=True)
