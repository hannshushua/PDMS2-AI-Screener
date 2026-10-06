# run_admin.py
# -*- coding: utf-8 -*-
from pathlib import Path
from flask import Flask, send_from_directory, request, jsonify, session, redirect, make_response
import threading
from datetime import datetime, date
import os, queue
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
import json
from html import escape

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
    connect_timeout=30,
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
HOST = "0.0.0.0"
MACWEB_BASE_URL = _env.get("MACWEB_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
IMAGE_SIGN_SECRET = _env.get("IMAGE_SIGN_SECRET", "")

app = Flask(__name__)
app.secret_key = os.environ.get("WEB_SECRET_KEY") or _env.get("WEB_SECRET_KEY", "dev-only-secret-change-me")
CORS(app, supports_credentials=True)


# ── AI 顧問 API ──────────────────────────────────────────────────────────────
@app.route("/api/ai_advice/<uid>")
def api_get_ai_advice(uid):
    user = current_user()
    if not user:
        return jsonify({"ok": False, "msg": "未登入"}), 401
    if not can_access_uid(uid):
        return jsonify({"ok": False, "msg": "無存取權限"}), 403

    check_only = request.args.get("check_only") == "1"
    force = request.args.get("force") == "1"

    try:
        if check_only:
            write_to_console(f"[AI] Status check for UID: {uid}", "INFO")
            status = advisor.check_advice_status(uid)
            return jsonify({"ok": True, **status})

        write_to_console(f"[AI] Generate request for UID: {uid}, force={force}", "INFO")
        advice = advisor.generate_advice(uid, force=force)
        write_to_console(f"[AI] Completed for UID: {uid}", "INFO")
        return jsonify({"ok": True, "advice": advice})
    except Exception as e:
        write_to_console(f"[AI] Failed for {uid}: {e}", "ERROR")
        traceback.print_exc()
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
    # 永遠取最後兩段當 uid/檔名：MACWEB_BASE_URL 可能帶路徑前綴（如 Funnel 的 /images），
    # 網址會變成 /images/images/<uid>/<file>，取開頭幾段會把 uid 拆成 "images"
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return None, None



def write_to_console(message, level="INFO"):
    console_path = ROOT / "admin_console.txt"
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


# 人工評分面板的前端腳本（純字串，不做任何插值）
MANUAL_PANEL_JS = """
<script>
(function () {
  const panel = document.querySelector('.manual-panel');
  if (!panel) return;
  const state = document.getElementById('manual-state');
  panel.querySelectorAll('.m-btn').forEach(b => b.addEventListener('click', async () => {
    state.textContent = '儲存中...';
    try {
      const res = await fetch('/scores/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ row_key: panel.dataset.rk, score: Number(b.dataset.score) })
      });
      const js = await res.json();
      if (js.ok) {
        panel.querySelectorAll('.m-btn').forEach(x => x.classList.remove('on'));
        b.classList.add('on');
        state.textContent = '已儲存：' + js.manual_score + ' 分（評分者 ' + js.manual_rater + '）';
      } else {
        state.textContent = '儲存失敗：' + (js.msg || '未知錯誤');
      }
    } catch (e) {
      state.textContent = '儲存失敗：連線異常';
    }
  }));
})();
</script>
"""


@app.route("/manual-score")
def manual_score_page():
    """人工評分頁：只顯示原始照片，刻意不顯示 AI 判讀圖與 AI 分數，避免影響評分者判斷。"""
    user = current_user()
    if not user:
        return "Unauthorized", 401
    if user_level(user) < 2:
        return "Forbidden", 403

    row_key = request.args.get("rk", "")
    parts = row_key.split("|", 3)
    if len(parts) != 4 or not all(parts):
        return "Missing rk", 400
    uid, task_id, test_date, time_val = parts
    if not can_access_uid(uid):
        return "Forbidden", 403

    table = task_id_to_table(task_id)
    row = db_exec(
        f"SELECT result_img_path FROM `{table}` WHERE uid=%s AND test_date=%s AND `time`=%s",
        (uid, test_date, time_val),
        fetch="one",
    )
    db_path = (row or {}).get("result_img_path") or ""
    img_uid, filename = extract_uid_filename(db_path)
    if img_uid and img_uid != uid:
        filename = None

    is_multi = task_id in {"Ch1-t2", "Ch1-t3", "Ch1-t4"}
    if is_multi:
        base = _extract_multi_view_base(filename, task_id) if filename else task_id
        photos = [
            ("側面視角", build_signed_image_url(uid, f"{base}-side.jpg")),
            ("頂部視角", build_signed_image_url(uid, f"{base}-top.jpg")),
        ]
    else:
        if filename:
            stem, _ = os.path.splitext(filename)
            for suffix in ("_detected", "_result"):
                if stem.endswith(suffix):
                    stem = stem[: -len(suffix)]
                    break
        else:
            stem = task_id
        photos = [("原始照片", build_signed_image_url(uid, f"{stem}.jpg"))]

    is_video = bool(filename) and filename.lower().endswith(".mp4")
    if is_video:
        photos_html = (
            f'<div class="box" style="width:80%;"><h3>錄影</h3>'
            f'<video src="{build_signed_image_url(uid, filename)}" controls preload="metadata" style="max-width:100%;"></video></div>'
        )
    else:
        photos_html = "".join(
            f'<div class="box"><h3>{cap}</h3>'
            f'<img src="{url}" onerror="this.onerror=null;this.src=&quot;/images/no_image.png&quot;;"></div>'
            for cap, url in photos
        )

    cur_row = db_exec(
        "SELECT score, rater FROM manual_score "
        "WHERE uid=%s AND task_id=%s AND test_date=%s AND `time`=%s",
        (uid, task_id, test_date, time_val),
        fetch="one",
    )
    cur_score = cur_row["score"] if cur_row else None
    cur_rater = (cur_row or {}).get("rater") or ""
    buttons = "".join(
        f'<button class="m-btn m-{n}{" on" if cur_score == n else ""}" data-score="{n}">{n}</button>'
        for n in (0, 1, 2)
    )
    state_text = (
        f"目前：{cur_score} 分（評分者 {cur_rater}）" if cur_score is not None else "尚未評分"
    )

    # 評完之後才給的入口，讓評分者自己決定要不要看 AI 判讀
    compare_html = ""
    if filename:
        signed = build_signed_image_url(uid, filename)
        compare_url = f"/view-compare?{urlencode({'uid': uid, 'task_id': task_id, 'img': signed, 'rk': row_key})}"
        compare_html = f'<a class="compare-link" href="{compare_url}">評分完成後，檢視 AI 判讀結果對照 →</a>'

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>人工評分 - {uid} - {task_id}</title>
        <style>
            body {{ font-family: "Microsoft JhengHei", sans-serif; text-align: center; padding: 20px; background: #f0f2f5; }}
            h2 {{ color: #333; margin-bottom: 10px; }}
            .sub-info {{ color: #666; margin-bottom: 24px; font-size: 0.95em; }}
            .row {{ display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; margin-bottom: 20px; }}
            .box {{ background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); width: 45%; min-width: 300px; }}
            .box h3 {{ margin: 0 0 10px 0; color: #555; font-size: 16px; border-bottom: 1px solid #eee; padding-bottom: 8px; }}
            img {{ max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #eee; }}
            .back-link {{ position: fixed; top: 18px; left: 18px; display: inline-flex; align-items: center; gap: 10px; padding: 14px 30px; border-radius: 9999px; background: #00B4D8; color: #fff; text-decoration: none; font-size: 19px; font-weight: 700; box-shadow: 0 4px 0 #0096B7; }}
            .back-link:active {{ transform: translateY(2px); box-shadow: 0 2px 0 #0096B7; }}
            .manual-panel {{ max-width: 1200px; margin: 30px auto 20px; padding: 30px 40px 36px; background: #fff; border-radius: 24px; box-shadow: 0 4px 18px rgba(0,0,0,0.14); }}
            .manual-title {{ font-size: 28px; font-weight: bold; color: #2c3e50; }}
            .manual-legend {{ font-size: 18px; color: #777; margin: 8px 0 26px; }}
            .manual-btns {{ display: flex; gap: 32px; justify-content: center; }}
            .m-btn {{ flex: 1 1 0; min-width: 0; height: 220px; border-radius: 9999px; border: 8px solid transparent; color: #fff; font-family: inherit; font-size: 130px; font-weight: 900; line-height: 1; cursor: pointer; transition: transform 0.1s ease, box-shadow 0.1s ease; box-shadow: 0 6px 0 rgba(0,0,0,0.18); }}
            .m-btn:hover {{ transform: translateY(-4px); }}
            .m-btn:active {{ transform: translateY(3px); box-shadow: 0 2px 0 rgba(0,0,0,0.18); }}
            .m-0 {{ background: #E8445F; }}
            .m-1 {{ background: #EFA310; }}
            .m-2 {{ background: #12B394; }}
            .m-btn.on {{ border-color: #2c3e50; transform: scale(1.04); }}
            .manual-state {{ margin-top: 24px; font-size: 18px; font-weight: 700; color: #2c3e50; }}
            .compare-link {{ display: inline-block; margin-bottom: 30px; color: #0096B7; font-size: 17px; font-weight: 700; }}
            @media (max-width: 768px) {{
                body {{ padding: 12px; }}
                h2 {{ font-size: 20px; }}
                .back-link {{ position: static; padding: 10px 20px; font-size: 16px; margin-bottom: 12px; }}
                .box {{ width: 100% !important; min-width: 0; box-sizing: border-box; }}
                .manual-panel {{ margin: 20px auto; padding: 20px 16px 24px; }}
                .manual-title {{ font-size: 22px; }}
                .manual-legend {{ font-size: 15px; margin-bottom: 18px; }}
                .manual-btns {{ gap: 12px; }}
                .m-btn {{ height: 96px; font-size: 56px; border-width: 5px; }}
                .manual-state {{ font-size: 16px; }}
            }}
        </style>
    </head>
    <body>
        <a class="back-link" href="/html/admin.html">← 回到測驗紀錄總覽</a>
        <h2>人工評分：{uid} / 關卡 {task_id}</h2>
        <div class="sub-info">測驗時間 {test_date} {time_val}　｜　本頁不顯示 AI 判讀結果，請依 PDMS-2 量表自行評分</div>
        <div class="row">{photos_html}</div>
        <div class="manual-panel" data-rk="{row_key}">
            <div class="manual-title">人工評分（PDMS-2）</div>
            <div class="manual-legend">0 未達標準　｜　1 部分達標　｜　2 完全達標</div>
            <div class="manual-btns">{buttons}</div>
            <div class="manual-state" id="manual-state">{state_text}</div>
        </div>
        {compare_html}
        {MANUAL_PANEL_JS}
    </body>
    </html>
    """
    resp = make_response(html)
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp


_CH5_T1_TICK = re.compile(r"剩餘:\s*(\d+)s\s*\|\s*重量:\s*([\d.]+)g\s*\|\s*進度:\s*(\d+)/(\d+)")

_CH5_T1_CHART_JS = """
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
(function () {
  const D = __DATA__;
  new Chart(document.getElementById('bean-chart'), {
    type: 'line',
    data: {
      labels: D.sec,
      datasets: [
        { label: '顆數', data: D.count, stepped: true, borderColor: '#FF9F43', backgroundColor: '#FF9F43', yAxisID: 'y', pointRadius: 0, borderWidth: 3 },
        { label: '重量 (g)', data: D.weight, borderColor: '#48CAE4', backgroundColor: '#48CAE4', yAxisID: 'y1', pointRadius: 0, borderWidth: 2 }
      ]
    },
    options: {
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { title: { display: true, text: '第幾秒' } },
        y: { min: 0, max: D.target, ticks: { stepSize: 1 }, title: { display: true, text: '顆數' } },
        y1: { position: 'right', min: 0, grid: { drawOnChartArea: false }, title: { display: true, text: '重量 (g)' } }
      }
    }
  });
})();
</script>
"""


def _render_ch5_t1_result(data1: Optional[str]) -> str:
    """撿豆子（Ch5-t1）結果：從 data1 的紀錄 JSON 解析摘要、每秒進度與每顆豆子的放入時間。"""
    try:
        record = json.loads(data1) if data1 else None
    except ValueError:
        record = None
    if not isinstance(record, dict):
        return '<div class="row"><div class="box" style="width:80%;"><h3>撿豆子結果</h3><p>這筆是舊紀錄，沒有詳細數據。</p></div></div>'

    def _secs(t: str) -> int:
        h, m, s = (int(x) for x in t.split(":"))
        return h * 3600 + m * 60 + s

    ticks = []  # (第幾秒, 重量, 顆數)，Arduino 每秒印一行
    go_t = end_t = None
    for line in record.get("log") or []:
        text = line.get("text", "")
        if "[GO!]" in text:
            go_t = line.get("t")
        elif "遊戲結束原因" in text:
            end_t = line.get("t")
        m = _CH5_T1_TICK.search(text)
        if m:
            ticks.append((60 - int(m.group(1)), float(m.group(2)), int(m.group(3))))

    duration = (_secs(end_t) - _secs(go_t)) % 86400 if go_t and end_t else None
    score = record.get("score")
    target = record.get("target_bean_count") or 10
    end_reason = record.get("end_reason") or ""
    violation = "違規" in end_reason
    n = record.get("bean_count")
    if not isinstance(n, int):
        n = ticks[-1][2] if ticks else 0
    if "達成目標" in end_reason:
        # 放滿時遊戲立刻結束，最後一行進度與 bean_count 都停在 target-1
        n = target

    # 每顆豆子的放入時間：顆數變多的那一秒
    beans, last_count, last_sec = [], 0, 0
    for sec, _, count in ticks:
        if count > last_count:
            beans.append((count, sec, sec - last_sec if beans else None))
            last_count, last_sec = count, sec
    # 放滿最後一顆時遊戲立刻結束，Arduino 不會再印那一秒，用結束時間補上
    if not violation and duration is not None and n > last_count:
        beans.append((n, duration, duration - last_sec if beans else None))

    used = f"用時 {duration} 秒" if duration is not None else "用時不明"
    if violation:
        criteria = f"違規：一次放入超過一顆，違規前已放入 {n} 顆（依目前設定判 0 分）"
    elif not ticks:
        criteria = f"log 不完整，無法對照標準（紀錄分數 {score}）"
    elif score == 2:
        criteria = f"放入 {n} 顆，{used}：符合「30 秒內完成放進 10 顆」，2 分"
    elif score == 1:
        criteria = f"放入 {n} 顆，{used}：符合「31-60 秒內放入 5-10 顆」，1 分"
    elif score == 0:
        criteria = f"放入 {n} 顆，{used}：符合「超過 60 秒才放完，或只放入 4 顆以下」，0 分"
    else:
        criteria = "沒有有效分數"

    reason_color = "#D04060" if violation else "#2c3e50"
    cards = (
        f'<div class="bean-card"><div class="bean-label">分數</div><div class="bean-value">{escape(str(score))}</div></div>'
        f'<div class="bean-card"><div class="bean-label">放入顆數</div><div class="bean-value">{n} / {target}</div></div>'
        f'<div class="bean-card"><div class="bean-label">用時</div><div class="bean-value">{duration if duration is not None else "—"} 秒</div></div>'
        f'<div class="bean-card"><div class="bean-label">結束原因</div><div class="bean-value" style="font-size:18px;color:{reason_color};">{escape(end_reason) or "—"}</div></div>'
    )
    bean_rows = "".join(
        f"<tr><td>第 {c} 顆</td><td>第 {s} 秒</td><td>{'—' if gap is None else f'{gap} 秒'}</td></tr>"
        for c, s, gap in beans
    ) or '<tr><td colspan="3">沒有放入任何豆子</td></tr>'
    chart_data = json.dumps({
        "sec": [t[0] for t in ticks],
        "count": [t[2] for t in ticks],
        "weight": [t[1] for t in ticks],
        "target": target,
    })

    return f"""
    <style>
      .bean-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 14px; }}
      .bean-card {{ background: #FFFAF5; border: 2px solid #F0E6D2; border-radius: 12px; padding: 12px; }}
      .bean-label {{ color: #9E8F8F; font-size: 14px; font-weight: 700; }}
      .bean-value {{ color: #2c3e50; font-size: 26px; font-weight: 800; margin-top: 4px; }}
      .bean-criteria {{ font-size: 17px; font-weight: 700; padding: 12px; border-radius: 10px; background: {"#FFEEF2" if violation else "#E7F8F4"}; color: {"#D04060" if violation else "#0D7A66"}; }}
      .bean-chart-wrap {{ position: relative; height: 320px; }}
      .bean-table {{ width: 100%; border-collapse: collapse; font-size: 16px; }}
      .bean-table th, .bean-table td {{ padding: 8px; border-bottom: 1px solid #eee; }}
      .bean-table th {{ background: #FFFAF5; color: #B5651D; }}
    </style>
    <div class="row"><div class="box" style="width:80%;">
      <h3>摘要</h3>
      <div class="bean-cards">{cards}</div>
      <div class="bean-criteria">{escape(criteria)}</div>
    </div></div>
    <div class="row"><div class="box" style="width:80%;">
      <h3>進度曲線</h3>
      <div class="bean-chart-wrap"><canvas id="bean-chart"></canvas></div>
    </div></div>
    <div class="row"><div class="box" style="width:80%;">
      <h3>每顆豆子放入時間</h3>
      <table class="bean-table"><thead><tr><th>顆數</th><th>放入時間</th><th>距上一顆</th></tr></thead><tbody>{bean_rows}</tbody></table>
    </div></div>
    """ + _CH5_T1_CHART_JS.replace("__DATA__", chart_data)


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
    video_uid, video_file = extract_uid_filename(img_path)
    is_video = video_uid == uid and bool(video_file) and video_file.lower().endswith(".mp4")


    content_html = ""
    if task_id == "Ch5-t1":
        # 撿豆子沒有圖片：用 rk 找到這一筆，結果在 data1
        rk_parts = request.args.get("rk", "").split("|", 3)
        data1 = None
        if len(rk_parts) == 4 and rk_parts[0] == uid:
            row = db_exec(
                f"SELECT data1 FROM `{task_id_to_table(task_id)}` WHERE uid=%s AND test_date=%s AND `time`=%s",
                (uid, rk_parts[2], rk_parts[3]),
                fetch="one",
            )
            data1 = (row or {}).get("data1")
        content_html = _render_ch5_t1_result(data1)
    elif is_video:
        # 鈕扣關錄影：沒有 AI 判讀圖，直接播放影片
        content_html = f"""
        <div class=\"row\">
            <div class=\"box\" style=\"width:80%;\"><h3>錄影</h3><video src=\"{build_signed_image_url(uid, video_file)}\" controls preload=\"metadata\" style=\"max-width:100%;\"></video></div>
        </div>
        """
    elif is_multi:
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
        <meta name="viewport" content="width=device-width, initial-scale=1">
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
            .back-link {{ position: fixed; top: 18px; left: 18px; display: inline-flex; align-items: center; gap: 10px; padding: 14px 30px; border-radius: 9999px; background: #00B4D8; color: #fff; text-decoration: none; font-size: 19px; font-weight: 700; box-shadow: 0 4px 0 #0096B7; }}
            .back-link:active {{ transform: translateY(2px); box-shadow: 0 2px 0 #0096B7; }}
            @media (max-width: 768px) {{
                body {{ padding: 12px; }}
                h2 {{ font-size: 20px; }}
                .back-link {{ position: static; padding: 10px 20px; font-size: 16px; margin-bottom: 12px; }}
                .box {{ width: 100% !important; min-width: 0; box-sizing: border-box; }}
                .section-title {{ font-size: 16px; }}
            }}
        </style>
    </head>
    <body>
        <a class="back-link" href="/html/admin.html">← 回到測驗紀錄總覽</a>
        <h2>使用者: {uid} / 關卡: {task_id}</h2>
        <div class=\"sub-info\">檢視模式: {"撿豆子紀錄" if task_id == "Ch5-t1" else "多視角" if is_multi else "單一視角"}</div>
        {content_html}
    </body>
    </html>
    """
    resp = make_response(html)
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp


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
        # 17 張明細表併成一條 UNION ALL 一次撈完：跨機器查 DB 時往返次數才是瓶頸
        sql_parts, params = [], []
        for task_id, table_name in effective_map.items():
            # 以任務明細表為主表：每次測驗都是獨立一筆，time 與 score 同源
            part = f"""
                SELECT d.uid, u.name, %s AS task_id, t.task_name, d.score, d.result_img_path, d.test_date, d.time,
                       ms.score AS manual_score, ms.rater AS manual_rater
                FROM `{table_name}` AS d
                JOIN user_list AS u ON u.uid = d.uid
                JOIN task_list AS t ON t.task_id = %s
                LEFT JOIN manual_score AS ms
                       ON ms.uid = d.uid AND ms.task_id = %s
                      AND ms.test_date = d.test_date AND ms.time = d.time
                WHERE 1 = 1
            """
            params += [task_id, task_id, task_id]
            if level == 1:  # 🔐 家長過濾：帳號與 UID 綁定
                part += " AND d.uid = %s"
                params.append(account)
            sql_parts.append(part)
        if sql_parts:
            all_rows_raw = db_exec(" UNION ALL ".join(sql_parts), tuple(params), fetch="all") or []

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

            if task_id == "Ch5-t1":
                # 撿豆子沒有圖片，結果存在 data1：一律給檢視按鈕，由對照頁讀 DB
                r["result_img_url"] = None
                r["compare_url"] = f"/view-compare?{urlencode({'uid': uid, 'task_id': task_id, 'rk': r['row_key']})}"
                continue

            db_path = (r.get("result_img_path") or "").strip()
            img_uid, img_filename = extract_uid_filename(db_path)
            if img_uid and img_uid != uid:
                img_filename = None
            if img_filename:
                signed_img = build_signed_image_url(uid, img_filename)
                r["result_img_url"] = signed_img
                r["compare_url"] = (
                    f"/view-compare?{urlencode({'uid': uid, 'task_id': task_id, 'img': signed_img, 'rk': r['row_key']})}"
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
        write_to_console(f"[ERR] GET /scores\n{traceback.format_exc()}", "ERROR")
        return jsonify({"success": False, "error": str(e)}), 500


@app.get("/scores/version")
def scores_version():
    """輕量版本戳記：只做 COUNT/MAX/SUM，供前端輪詢判斷要不要重抓 /scores。"""
    try:
        user = session.get("user")
        if not user:
            return jsonify({"ok": False, "msg": "尚未登入"}), 401
        level, account = int(user.get("level") or 0), user.get("account")
        db_tasks = db_exec("SELECT task_id, task_name FROM task_list", fetch="all") or []
        effective_map = {r["task_id"]: r["task_name"] for r in db_tasks} or TASK_MAP
        # 17 張明細表併成一次 UNION ALL，避免每張表各一次連線往返
        parts, params = [], []
        for table_name in effective_map.values():
            part = (
                "SELECT COUNT(*) AS c, MAX(CONCAT(d.test_date, ' ', d.time)) AS m, "
                f"COALESCE(SUM(d.score), 0) AS s FROM `{table_name}` AS d WHERE 1 = 1"
            )
            if level == 1:
                part += " AND d.uid = %s"
                params.append(account)
            parts.append(part)
        # 人工評分也要進版本戳記，否則同事剛評的分數在別台不會自動出現
        manual_part = (
            "SELECT COUNT(*) AS c, MAX(updated_at) AS m, COALESCE(SUM(score), 0) AS s "
            "FROM manual_score WHERE 1 = 1"
        )
        if level == 1:
            manual_part += " AND uid = %s"
            params.append(account)
        parts.append(manual_part)
        rows = db_exec(" UNION ALL ".join(parts), tuple(params), fetch="all") or []
        total, latest, score_sum = 0, "", 0
        for row in rows:
            total += int(row.get("c") or 0)
            score_sum += float(row.get("s") or 0)
            m = row.get("m")
            if m and str(m) > latest:
                latest = str(m)
        return jsonify({"ok": True, "version": f"{total}|{latest}|{score_sum}"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500


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

        # A. 先取舊生日，判斷這次有沒有改動（決定是否一併同步家長密碼）
        old = db_exec("SELECT birthday FROM user_list WHERE uid=%s", (uid,), fetch="one")
        old_birthday = old["birthday"].isoformat() if old and old.get("birthday") else None
        birthday_changed = old_birthday != birthday

        # B. 寫入受測者基本資料
        ensure_user(uid, name, birthday)

        # C. 同步建立 Level 1 家長登入權限
        # 帳號為 uid、密碼為生日；生日有異動才覆蓋密碼，避免洗掉家長自行改過的密碼
        parent_email = f"{name}@parent.com" if name else f"{uid}@parent.com"
        pwd_clause = "password=VALUES(password), " if birthday_changed else ""
        db_exec(
            "INSERT INTO admin_users (account, password, email, level) VALUES (%s, %s, %s, 1) "
            f"ON DUPLICATE KEY UPDATE {pwd_clause}email=VALUES(email)",
            (uid, birthday, parent_email),
        )
        msg = "受測者與家長帳號已同步建立成功！"
        if birthday_changed and old_birthday:
            msg = "受測者資料已更新，家長登入密碼已同步為新的出生日期。"
        return jsonify({"ok": True, "msg": msg})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500


# 送出前確認用：讓前端先知道這個 uid 是新增還是覆蓋既有受測者
@app.get("/api/user/lookup")
def api_user_lookup():
    try:
        if int(session.get("user", {}).get("level", 0)) < 2:
            return jsonify({"ok": False, "msg": "權限不足"}), 403
        uid = request.args.get("uid", "").strip()
        if not uid:
            return jsonify({"ok": False, "msg": "UID 不可為空"}), 400
        row = db_exec(
            "SELECT name, birthday FROM user_list WHERE uid=%s", (uid,), fetch="one"
        )
        if not row:
            return jsonify({"ok": True, "exists": False})
        bd = row.get("birthday")
        return jsonify(
            {
                "ok": True,
                "exists": True,
                "name": row.get("name") or "",
                "birthday": bd.isoformat() if isinstance(bd, (date, datetime)) else (bd or ""),
            }
        )
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


@app.post("/scores/manual")
def upsert_manual_score():
    """醫療人員對某一次測驗的人工評分（0/1/2），與 AI 分數分開存，互不覆蓋。"""
    try:
        user = current_user()
        if user_level(user) < 2:
            return jsonify({"ok": False, "msg": "只有醫療人員(等級2)以上可以人工評分"}), 403

        data = request.get_json() or {}
        row_key = (data.get("row_key") or "").strip()
        parts = row_key.split("|", 3)
        if len(parts) != 4 or not all(parts):
            return jsonify({"ok": False, "msg": "row_key 格式錯誤"}), 400
        uid, task_id, test_date, time_val = parts

        try:
            score = int(data.get("score"))
        except (TypeError, ValueError):
            score = -1
        if score not in (0, 1, 2):
            return jsonify({"ok": False, "msg": "分數只能是 0 / 1 / 2"}), 400

        if not can_access_uid(uid):
            return jsonify({"ok": False, "msg": "權限不足"}), 403
        task_id_to_table(task_id)  # 驗證 task_id 存在，未知會丟 ValueError

        rater = str(user.get("account") or "").strip()
        db_exec(
            "INSERT INTO manual_score (uid, task_id, test_date, `time`, rater, score) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE score = VALUES(score), rater = VALUES(rater)",
            (uid, task_id, test_date, time_val, rater, score),
        )
        _broadcast_score_updated()
        return jsonify({"ok": True, "manual_score": score, "manual_rater": rater})
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
    webbrowser.open(f"http://127.0.0.1:{PORT}/")


if __name__ == "__main__":
    threading.Timer(0.5, _open_browser).start()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
