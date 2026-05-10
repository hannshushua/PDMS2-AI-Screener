# run.py (已修正：相機開啟問題 + 資料表名稱錯誤)
# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import uuid
import base64
import secrets
import logging
import traceback
import subprocess
import tempfile
import threading
import webbrowser
import unicodedata
import socket
from pathlib import Path
from datetime import datetime, date
from typing import Optional
from threading import Thread

import cv2
import numpy as np
import pymysql
import requests
from flask import Flask, send_from_directory, request, jsonify, session
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

ROOT = Path(__file__).parent.resolve()
ENV_PATH = ROOT / ".env"
CH3_T4_DIR = ROOT / "ch3-t4"
CH2_T1_DIR = ROOT / "ch2-t1"
for d in [CH3_T4_DIR, CH2_T1_DIR]:
    if d.exists() and str(d) not in sys.path:
        sys.path.insert(0, str(d))

try:
    from paper_contour_model import detect_paper_contour_by_model
except Exception:
    detect_paper_contour_by_model = None

try:
    from px2cm import get_pixel_per_cm_from_image
except Exception:
    get_pixel_per_cm_from_image = None

DEFAULT_TOP_CAMERA_INDEX = 0
DEFAULT_SIDE_CAMERA_INDEX = 1  # Ch5-t1 使用
DEFAULT_PX2CM = 47.4416628993705
DEFAULT_CH3_T4_STANDARD_AREA = 34769
_MACOS_CAMERA_IGNORE_KEYWORDS = (
    "iphone",
    "ipad",
    "ipod",
    "facetime",
    "continuity",
    "手機",
    "內建",
    "built-in",
    "built in",
    "apple",
    "phone",
)


def _default_camera_scan_max_index() -> int:
    # 預設掃描範圍
    return 3


def _should_skip_opencv_roi_gui(force_gui: bool = False) -> bool:
    """判斷目前是否要略過 OpenCV ROI 視窗。"""
    if force_gui:
        return False
    env_flag = os.environ.get("PDMS2_ENABLE_OPENCV_ROI_GUI", "").strip().lower()
    if env_flag in {"1", "true", "yes", "on"}:
        return False
    if env_flag in {"0", "false", "no", "off"}:
        return True
    return sys.platform == "darwin"


def _select_roi_in_subprocess(frame, window_name: str):
    """把 OpenCV ROI 視窗放到子行程，避免 GUI 崩潰直接帶倒主程序。"""
    child_code = r'''
import json
import sys

import cv2


def main():
    image_path = sys.argv[1]
    window_name = sys.argv[2]
    image = cv2.imread(image_path)
    if image is None:
        print(json.dumps({"success": False, "error": "影像讀取失敗"}, ensure_ascii=False))
        return 2

    roi = (0, 0, 0, 0)
    try:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)
        roi = cv2.selectROI(window_name, image, showCrosshair=True, fromCenter=False)
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    finally:
        try:
            cv2.destroyWindow(window_name)
        except Exception:
            pass

    x, y, w, h = [int(v) for v in roi]
    if w > 0 and h > 0:
        print(json.dumps({"success": True, "roi": {"x": x, "y": y, "w": w, "h": h}}, ensure_ascii=False))
        return 0

    print(json.dumps({"success": False, "error": "未選取有效範圍"}, ensure_ascii=False))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
'''

    with tempfile.TemporaryDirectory(prefix="pdms2_roi_") as tmpdir:
        image_path = Path(tmpdir) / "roi_frame.png"
        if not cv2.imwrite(str(image_path), frame):
            return {"success": False, "error": "暫存 ROI 影像失敗", "fallback": "manual"}

        try:
            result = subprocess.run(
                [sys.executable, "-c", child_code, str(image_path), window_name],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except Exception as exc:
            return {
                "success": False,
                "error": f"ROI 子行程啟動失敗: {exc}",
                "fallback": "manual",
            }

        payload = None
        if result.stdout:
            for line in reversed(result.stdout.splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    break
                except Exception:
                    continue

        if result.returncode == 0 and isinstance(payload, dict) and payload.get("success"):
            return payload

        error_message = None
        if isinstance(payload, dict):
            error_message = payload.get("error")

        if not error_message:
            error_message = result.stderr.strip() or f"ROI 子行程失敗，exit code={result.returncode}"

        write_to_console(f"[ROI] 子行程回傳失敗: {error_message}", "WARN")
        return {"success": False, "error": error_message, "fallback": "manual"}


def _is_ignored_macos_camera(name: str, model_id: str = "", unique_id: str = "") -> bool:
    # 正規化名稱 (處理特殊字體 𝓦𝓲𝓵𝓵𝓲𝓪𝓶 -> William)
    norm_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    haystack = f"{name} {norm_name} {model_id} {unique_id}".lower()
    
    # 強制過濾 iPhone 型號
    if "iphone" in model_id.lower() or "iphone" in name.lower():
        return True
        
    return any(keyword in haystack for keyword in _MACOS_CAMERA_IGNORE_KEYWORDS)


def _read_macos_camera_labels() -> list:
    try:
        result = subprocess.run(
            ["system_profiler", "SPCameraDataType"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True,
        )
    except Exception:
        return []

    cameras = []
    current = None

    for raw_line in result.stdout.splitlines():
        stripped = raw_line.strip()

        if not stripped:
            continue

        if raw_line.startswith("    ") and not raw_line.startswith("        ") and stripped.endswith(":"):
            name = stripped[:-1].strip()
            current = {"name": name, "model_id": "", "unique_id": ""}
            cameras.append(current)
            continue

        if current is None:
            continue

        if stripped.startswith("Model ID:"):
            current["model_id"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Unique ID:"):
            current["unique_id"] = stripped.split(":", 1)[1].strip()

    return cameras


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


def _write_env_file(updates: dict) -> None:
    lines = []
    seen_keys = set()

    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    rewritten = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            rewritten.append(raw_line)
            continue

        key, value = raw_line.split("=", 1)
        key = key.strip()
        if key in updates:
            rewritten.append(f"{key}={updates[key]}")
            seen_keys.add(key)
        else:
            rewritten.append(raw_line)

    for key, value in updates.items():
        if key not in seen_keys:
            rewritten.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(rewritten).rstrip("\n") + "\n", encoding="utf-8")


def _env_flag(value, default: bool = False) -> bool:
    if value is None:
        return default

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _remote_config_sync_enabled() -> bool:
    env = _read_env_file()
    return _env_flag(env.get("REMOTE_CONFIG_SYNC"), True)


def _get_machine_id() -> str:
    env = _read_env_file()
    machine_id = str(env.get("MACHINE_ID") or "").strip()

    if machine_id:
        try:
            return str(uuid.UUID(machine_id))
        except Exception:
            pass

    machine_id = str(uuid.uuid4())
    _write_env_file({"MACHINE_ID": machine_id})
    return machine_id


def _get_machine_identity_payload() -> dict:
    hostname = socket.gethostname().strip() or "unknown-host"
    mac_value = uuid.getnode()
    mac_address = ":".join(
        f"{(mac_value >> offset) & 0xFF:02x}" for offset in range(40, -1, -8)
    )
    return {
        "machine_id": _get_machine_id(),
        "hostname": hostname,
        "mac_address": mac_address,
        "location_code": "",
    }


def _settings_to_remote_row(settings: dict) -> dict:
    payload = _get_machine_identity_payload()
    payload.update(
        {
            "machine_name": payload.get("hostname", "machine"),
            "top_camera_index": int(settings.get("top", 0)),
            "side_camera_index": int(settings.get("side", 0)),
            "roi_x": int(settings.get("roi_x", 0)),
            "roi_y": int(settings.get("roi_y", 0)),
            "roi_w": int(settings.get("roi_w", 0)),
            "roi_h": int(settings.get("roi_h", 0)),
            "px2cm": float(settings.get("px2cm", 0) or 0),
            "standard_area": float(settings.get("standard_area", 0) or 0),
        }
    )
    return payload


def _sync_machine_config_to_remote(settings: dict) -> dict:
    if not _remote_config_sync_enabled():
        return {"synced": False, "disabled": True}

    payload = _settings_to_remote_row(settings)

    machine_sql = """
        INSERT INTO machine_configs (
            machine_id,
            machine_name,
            hostname,
            top_camera_index,
            side_camera_index,
            roi_x,
            roi_y,
            roi_w,
            roi_h,
            px2cm,
            standard_area,
            updated_at,
            created_at
        ) VALUES (
            %(machine_id)s,
            %(machine_name)s,
            %(hostname)s,
            %(top_camera_index)s,
            %(side_camera_index)s,
            %(roi_x)s,
            %(roi_y)s,
            %(roi_w)s,
            %(roi_h)s,
            %(px2cm)s,
            %(standard_area)s,
            NOW(),
            NOW()
        )
        ON DUPLICATE KEY UPDATE
            hostname = VALUES(hostname),
            top_camera_index = VALUES(top_camera_index),
            side_camera_index = VALUES(side_camera_index),
            roi_x = VALUES(roi_x),
            roi_y = VALUES(roi_y),
            roi_w = VALUES(roi_w),
            roi_h = VALUES(roi_h),
            px2cm = VALUES(px2cm),
            standard_area = VALUES(standard_area),
            updated_at = NOW()
    """

    identity_sql = """
        INSERT INTO machine_identities (
            machine_id,
            hostname,
            mac_address,
            location_code,
            last_seen_at,
            created_at
        ) VALUES (
            %(machine_id)s,
            %(hostname)s,
            %(mac_address)s,
            %(location_code)s,
            NOW(),
            NOW()
        )
        ON DUPLICATE KEY UPDATE
            hostname = VALUES(hostname),
            mac_address = VALUES(mac_address),
            location_code = VALUES(location_code),
            last_seen_at = NOW()
    """

    conn = None
    try:
        conn = pymysql.connect(**DB)
        with conn.cursor() as cur:
            cur.execute(machine_sql, payload)
            cur.execute(identity_sql, payload)
        conn.commit()
        return {"synced": True, "machine_id": payload["machine_id"]}
    except Exception as exc:
        write_to_console(f"[SYNC] 遠端配置同步失敗: {exc}", "WARN")
        return {"synced": False, "error": str(exc), "machine_id": payload.get("machine_id")}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _camera_index_from_env(value, default):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _float_from_env(value, default):
    try:
        parsed = float(str(value).strip())
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _int_from_env(value, default):
    try:
        parsed = int(float(str(value).strip()))
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _macweb_base_url() -> str:
    env = _read_env_file()
    return str(env.get("MACWEB_BASE_URL") or MACWEB_BASE_URL).strip() or MACWEB_BASE_URL


def _mac_web_api_url() -> str:
    return f"{_macweb_base_url().rstrip('/')}/api/analysis/submit"


def read_app_settings() -> dict:
    env = _read_env_file()
    return {
        "top": _camera_index_from_env(
            env.get("PDMS2_TOP_CAMERA_INDEX"), DEFAULT_TOP_CAMERA_INDEX
        ),
        "side": _camera_index_from_env(
            env.get("PDMS2_SIDE_CAMERA_INDEX"), DEFAULT_SIDE_CAMERA_INDEX
        ),
        "px2cm": _float_from_env(env.get("PDMS2_PX2CM"), DEFAULT_PX2CM),
        "standard_area": _int_from_env(
            env.get("PDMS2_CH3_T4_STANDARD_AREA"), DEFAULT_CH3_T4_STANDARD_AREA
        ),
        "macweb_base_url": (env.get("MACWEB_BASE_URL") or MACWEB_BASE_URL).strip(),
        "roi_x": int(env.get("PDMS2_ROI_X", 0)),
        "roi_y": int(env.get("PDMS2_ROI_Y", 0)),
        "roi_w": int(env.get("PDMS2_ROI_W", 0)),
        "roi_h": int(env.get("PDMS2_ROI_H", 0)),
    }


def read_camera_setting() -> dict:
    settings = read_app_settings()
    return {
        "top": settings["top"],
        "side": settings["side"],
        "roi": {
            "x": settings["roi_x"],
            "y": settings["roi_y"],
            "w": settings["roi_w"],
            "h": settings["roi_h"],
        },
    }


def save_app_settings(
    top_index: Optional[int] = None,
    side_index: Optional[int] = None,
    px2cm: Optional[float] = None,
    standard_area: Optional[int] = None,
    macweb_base_url: Optional[str] = None,
    roi: Optional[dict] = None,
) -> dict:
    global TOP, SIDE, PX2CM, STANDARD_AREA, ROI_X, ROI_Y, ROI_W, ROI_H

    settings = read_app_settings()
    updates = {}

    if top_index is not None:
        settings["top"] = int(top_index)
        updates["PDMS2_TOP_CAMERA_INDEX"] = str(settings["top"])

    if side_index is not None:
        settings["side"] = int(side_index)
        updates["PDMS2_SIDE_CAMERA_INDEX"] = str(settings["side"])

    if px2cm is not None:
        settings["px2cm"] = float(px2cm)
        updates["PDMS2_PX2CM"] = f"{settings['px2cm']:.10f}".rstrip("0").rstrip(".")

    if standard_area is not None:
        settings["standard_area"] = int(standard_area)
        updates["PDMS2_CH3_T4_STANDARD_AREA"] = str(settings["standard_area"])

    if macweb_base_url is not None:
        settings["macweb_base_url"] = str(macweb_base_url).strip()
        updates["MACWEB_BASE_URL"] = settings["macweb_base_url"]

    if roi is not None:
        settings["roi_x"] = int(roi.get("x", 0))
        settings["roi_y"] = int(roi.get("y", 0))
        settings["roi_w"] = int(roi.get("w", 0))
        settings["roi_h"] = int(roi.get("h", 0))
        updates["PDMS2_ROI_X"] = str(settings["roi_x"])
        updates["PDMS2_ROI_Y"] = str(settings["roi_y"])
        updates["PDMS2_ROI_W"] = str(settings["roi_w"])
        updates["PDMS2_ROI_H"] = str(settings["roi_h"])

    if updates:
        _write_env_file(updates)

    remote_sync = _sync_machine_config_to_remote(settings)

    TOP = int(settings["top"])
    SIDE = int(settings["side"])
    PX2CM = float(settings["px2cm"])
    STANDARD_AREA = int(settings["standard_area"])
    ROI_X = int(settings["roi_x"])
    ROI_Y = int(settings["roi_y"])
    ROI_W = int(settings["roi_w"])
    ROI_H = int(settings["roi_h"])
    settings["remote_sync"] = remote_sync
    return settings


def _open_camera_capture(camera_index: int):
    if sys.platform == "win32":
        capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(camera_index)
        return capture

    if sys.platform == "darwin":
        avfoundation = getattr(cv2, "CAP_AVFOUNDATION", None)
        if avfoundation is not None:
            return cv2.VideoCapture(camera_index, avfoundation)

    return cv2.VideoCapture(camera_index)


def scan_camera_devices(max_index: Optional[int] = None) -> list:
    """
    掃描相機清單：
    - macOS: 採取被動模式，提供索引建議，避免掃描時喚醒 iPhone。
    - Windows/其他: 採取主動模式，自動偵測並列出實體存在的相機。
    """
    devices = []

    if sys.platform == "darwin":
        write_to_console("[CAM] macOS 偵測到，切換至安全手動模式 (避免觸發接續互通相機)", "INFO")
        # macOS 採取索引建議方式
        for i in range(7):
            label = f"相機索引 {i}"
            if i == 0:
                label += " (⚠️ 可能觸發 iPhone)"
            elif i >= 1 and i <= 4:
                label += " (⭐ 建議測試 - AVerMedia 可能在此)"
            devices.append({"index": i, "label": label})
        return devices

    # Windows 或其他系統：執行主動掃描
    if max_index is None:
        max_index = 8  # Windows 上可以掃描多一點

    write_to_console(f"[CAM] 非 macOS 系統，開始主動掃描 Index 0~{max_index}...", "INFO")
    for camera_index in range(max_index + 1):
        capture = None
        try:
            # 嘗試開啟相機
            if sys.platform == "win32":
                capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            else:
                capture = cv2.VideoCapture(camera_index)
                
            if capture is not None and capture.isOpened():
                # 取得基本資訊 (如果 Windows 有支援的話)
                label = f"攝影機 {camera_index}"
                devices.append({"index": camera_index, "label": label})
                write_to_console(f"[CAM] 偵測到可用相機：Index {camera_index}", "INFO")
        except Exception:
            pass
        finally:
            if capture is not None:
                capture.release()
                
    if not devices:
        write_to_console("[CAM] 未掃描到任何實體相機，回傳預設索引供手動選擇", "WARN")
        return [{"index": i, "label": f"攝影機 {i}"} for i in range(3)]
        
    return devices


# ====== 相機 / 校正參數 =====
_app_setting = read_app_settings()
TOP = _app_setting["top"]
SIDE = _app_setting["side"]
PX2CM = _app_setting["px2cm"]
STANDARD_AREA = _app_setting["standard_area"]
ROI_X = _app_setting["roi_x"]
ROI_Y = _app_setting["roi_y"]
ROI_W = _app_setting["roi_w"]
ROI_H = _app_setting["roi_h"]
CROP_RATE = 0.8  # 預設裁切比例
current_camera_index = TOP  # 追蹤目前啟動的相機
# ====================

# =========================
# 1) 資料庫設定（從 .env 讀取）
# =========================
_env = _read_env_file()

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

# ====== MAC 上傳設定（從 .env 讀取） ======
MAC_UPLOAD_HOST = _env.get("MAC_UPLOAD_HOST", "127.0.0.1")
MAC_UPLOAD_PORT = int(_env.get("MAC_UPLOAD_PORT", 22))
MAC_UPLOAD_USER = _env.get("MAC_UPLOAD_USER", "")
MAC_UPLOAD_PASSWORD = _env.get("MAC_UPLOAD_PASSWORD", "")
MAC_UPLOAD_KEY_PATH = _env.get("MAC_UPLOAD_KEY_PATH", "")
MAC_UPLOAD_REMOTE_BASE = _env.get("MAC_UPLOAD_REMOTE_BASE", "Desktop/PDMS")
MACWEB_BASE_URL = _env.get("MACWEB_BASE_URL", "http://127.0.0.1:3000")
# =====================================================

DEMO_MODE = _env.get("DEMO_MODE", "false").strip().lower() == "true"


def db_exec(sql, params=None, fetch="none"):
    """簡易 DB 執行器 (PyMySQL)"""
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
    except Exception as e:
        write_to_console(
            f"[DB] PyMySQL 執行失敗: {sql}\nParams: {params}\nError: {e}", "ERROR"
        )
        raise
    finally:
        if conn:
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


# def ensure_user(uid: str, name: Optional[str] = None, birthday: Optional[str] = None):
#     try:
#         db_exec(
#             "INSERT INTO user_list(uid, name, birthday) VALUES (%s,%s,%s) "
#             "ON DUPLICATE KEY UPDATE name=COALESCE(VALUES(name),name), birthday=COALESCE(VALUES(birthday),birthday)",
#             (uid, name, birthday),
#         )
#         write_to_console(f"[DB] ensure_user ok: uid={uid}", "INFO")
#     except Exception as e:
#         raise
def user_exists(uid: str) -> bool:
    """回傳這個 uid 是否存在於 user_list"""
    row = db_exec(
        "SELECT 1 FROM user_list WHERE uid=%s",
        (uid,),
        fetch="one",  # 如果你的 db_exec 寫法不一樣，這裡用你原本查一筆資料的方式
    )
    return row is not None


def task_id_to_table(task_id: str) -> str:
    if task_id in TASK_MAP:
        return TASK_MAP[task_id]
    raise ValueError(f"未知的 task_id: {task_id}")


def insert_task_payload(
    task_id: str,
    uid: str,
    test_date: date,
    score: int,
    result_img_path: str,
    data1: Optional[str] = None,
) -> None:
    table = task_id_to_table(task_id)
    # 獲取當前時間
    current_time = datetime.now().strftime("%H:%M:%S")

    sql = f"""
        INSERT INTO `{table}` (uid, test_date, time, score, result_img_path, data1)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            score           = VALUES(score),
            result_img_path = VALUES(result_img_path),
            data1           = VALUES(data1),
            time            = VALUES(time)
    """
    try:
        db_exec(sql, (uid, test_date, current_time, score, result_img_path, data1))
    except Exception:
        raise


def ensure_task(task_id: str):
    if task_id not in TASK_MAP:
        raise ValueError(f"未知的 task_id：{task_id}")
    task_name = TASK_MAP[task_id]
    try:
        db_exec(
            "INSERT INTO task_list(task_id, task_name) VALUES (%s,%s) "
            "ON DUPLICATE KEY UPDATE task_name=VALUES(task_name)",
            (task_id, task_name),
        )
        write_to_console(f"[DB] ensure_task ok: {task_id} -> {task_name}", "INFO")
    except Exception as e:
        raise


def insert_score(
    uid: str,
    task_id: str,
    test_date: Optional[date] = None,
) -> date:

    if not user_exists(uid):
        write_to_console(f"[DB] insert_score: UID 不存在 -> {uid}", "WARN")
        # 丟一個明確的錯誤，讓呼叫的人去決定要怎麼回應前端
        raise ValueError("USER_NOT_FOUND")

    # task 邏輯照舊（如果你希望只有管理者能新增 task，也可以之後再改 ensure_task）
    ensure_task(task_id)

    if test_date is None:
        test_date = date.today()

    current_time = datetime.now().strftime("%H:%M:%S")

    db_exec(
        """
        INSERT INTO score_list (uid, task_id, test_date, time)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            test_date = VALUES(test_date),
            time = VALUES(time)
        """,
        (uid, task_id, test_date, current_time),
    )
    write_to_console(
        f"[DB] insert_score ok: uid={uid}, task_id={task_id}, date={test_date}, time={current_time}",
        "INFO",
    )
    return test_date


# =========================
# 2) 基礎環境/日誌/靜態路由
# =========================
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"


PORT = 8000
HOST = "127.0.0.1"

app = Flask(
    __name__,
    static_folder=str(ROOT / "static"),
    static_url_path="/static",
)
app.secret_key = secrets.token_hex(16)
CORS(app)


def setup_console_logging():
    console_path = Path(__file__).parent / "console.txt"
    fmt = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh = logging.FileHandler(console_path, mode="a", encoding="utf-8")
    fh.setFormatter(fmt)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    lg = logging.getLogger("app")
    lg.setLevel(logging.INFO)
    lg.addHandler(fh)
    lg.propagate = False
    return lg


def write_to_console(message, level="INFO"):
    console_path = ROOT / "console.txt"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(console_path, "a", encoding="utf-8") as f:
            f.write(f"{ts} - {level} - {message}\n")
    except Exception as e:
        print(f"寫入 console.txt 失敗: {e}")


def clear_console_log():
    console_path = ROOT / "console.txt"
    try:
        with open(console_path, "w", encoding="utf-8") as f:
            f.write("")
    except Exception:
        pass


@app.get("/camera-settings")
def get_camera_settings():
    return jsonify({"success": True, "settings": read_app_settings()})


@app.get("/camera-devices")
def get_camera_devices():
    return jsonify(
        {
            "success": True,
            "devices": scan_camera_devices(),
            "settings": read_camera_setting(),
        }
    )


@app.post("/camera-settings")
def update_camera_settings():
    try:
        data = request.get_json() or {}
        current = read_app_settings()

        top_index = int(data.get("top", current["top"]))
        side_index = int(data.get("side", current["side"]))
        px2cm = data.get("px2cm", current["px2cm"])
        standard_area = data.get("standard_area", data.get("standardArea", current["standard_area"]))

        devices = scan_camera_devices()
        available_indexes = {device["index"] for device in devices}
        if available_indexes and (
            top_index not in available_indexes or side_index not in available_indexes
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "所選攝影機不在目前偵測到的清單中",
                        "devices": devices,
                    }
                ),
                400,
            )

        px2cm_value = float(px2cm)
        standard_area_value = int(float(standard_area))

        if px2cm_value <= 0 or standard_area_value <= 0:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "px2cm 與標準面積必須大於 0",
                    }
                ),
                400,
            )

        if top_index == side_index:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "上方與旁邊攝影機不能設定成同一台",
                    }
                ),
                400,
            )

        settings = save_app_settings(
            top_index=top_index,
            side_index=side_index,
            px2cm=px2cm_value,
            standard_area=standard_area_value,
        )
        write_to_console(
            f"[ENV] 更新設定: top={top_index}, side={side_index}, px2cm={px2cm_value}, standard_area={standard_area_value}",
            "INFO",
        )
        return jsonify(
            {
                "success": True,
                "settings": settings,
                "remote_sync": settings.get("remote_sync", {}),
            }
        )
    except Exception as e:
        write_to_console(f"[ENV] 更新攝影機設定失敗: {e}", "ERROR")
        return jsonify({"success": False, "error": str(e)}), 500


def _measure_standard_area_from_image(image):
    if detect_paper_contour_by_model is None:
        raise RuntimeError("找不到紙張輪廓模型，無法量測標準面積")

    best_cnt, _, mask_area, model_path = detect_paper_contour_by_model(image)
    if mask_area <= 0:
        raise RuntimeError("模型未偵測到有效 paper mask")

    return {
        "area": int(mask_area),
        "model_path": str(model_path) if model_path is not None else None,
        "has_contour": best_cnt is not None,
    }


@app.post("/camera-settings/measure-px2cm")
def measure_px2cm_from_frame():
    try:
        if get_pixel_per_cm_from_image is None:
            return jsonify({"success": False, "error": "找不到比例尺量測邏輯 (px2cm.py)"})

        data = request.get_json() or {}
        image_data = (data.get("image") or "").strip()
        if not image_data:
            return jsonify({"success": False, "error": "缺少影像資料"})

        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        raw_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(raw_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return jsonify({"success": False, "error": "影像解碼失敗"})

        px2cm = get_pixel_per_cm_from_image(image)
        return jsonify({"success": True, "px2cm": px2cm})
    except Exception as e:
        write_to_console(f"[設定] px2cm 量測失敗: {e}", "ERROR")
        return jsonify({"success": False, "error": str(e)}), 500


@app.post("/camera-settings/measure-standard-area")
def measure_standard_area_from_frame():
    try:
        data = request.get_json() or {}
        image_data = (data.get("image") or "").strip()
        if not image_data:
            return jsonify({"success": False, "error": "缺少影像資料"})

        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        raw_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(raw_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            return jsonify({"success": False, "error": "影像解碼失敗"})

        result = _measure_standard_area_from_image(image)
        return jsonify({"success": True, **result})
    except Exception as e:
        import traceback as _tb
        write_to_console(f"[設定] 標準面積量測失敗: {e}\n{_tb.format_exc()}", "ERROR")
        return jsonify({"success": False, "error": str(e)}), 500


clear_console_log()
logger = setup_console_logging()
app.logger.disabled = True
logging.getLogger("flask.app").disabled = True
write_to_console("=== 遠端 PyMySQL 模式 ===", "INFO")
write_to_console("Flask 應用程式啟動", "INFO")
processing_tasks = {}


@app.route("/")
def home():
    return send_from_directory(ROOT / "html", "start.html")


@app.route("/index")
@app.route("/index.html")
def index_shortcut():
    return send_from_directory(ROOT / "html", "index.html")


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


@app.route("/kid/<path:filename>")
def kid_files(filename):
    # 讓網頁可以讀取 kid 資料夾內的照片
    return send_from_directory(ROOT / "kid", filename)


@app.route("/video/<path:filename>")
def video_files(filename):
    return send_from_directory(ROOT / "video", filename)


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/.well-known/appspecific/com.chrome.devtools.json")
def chrome_devtools():
    return ("", 204)


@app.get("/logs/tail")
def logs_tail():
    try:
        n = int(request.args.get("n", 200))
        p = ROOT / "console.txt"
        if not p.exists():
            return jsonify({"ok": False, "msg": "console.txt not found"}), 404
        with open(p, "r", encoding="utf-8") as f:
            lines = f.readlines()[-n:]
        return jsonify({"ok": True, "lines": lines})
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500


@app.before_request
def _log_request():
    if request.path.startswith(
        ("/css/", "/js/", "/images/", "/video/", "/favicon.ico", "/opencv-camera/")
    ):
        return
    try:
        if request.path.startswith(
            ("/run-python", "/create-uid-folder", "/test-score")
        ):
            write_to_console(f"[REQ] {request.method} {request.path}")
    except Exception as e:
        write_to_console(f"[REQ] log failed: {e}", "ERROR")


@app.after_request
def _log_response(resp):
    if request.path.startswith(
        ("/css/", "/js/", "/images/", "/video/", "/favicon.ico", "/opencv-camera/")
    ):
        return resp
    try:
        if resp.status_code >= 400 or request.path.startswith(
            ("/run-python", "/create-uid-folder", "/test-score")
        ):
            write_to_console(
                f"[RESP] {request.method} {request.path} -> {resp.status_code}"
            )
    except Exception as e:
        write_to_console(f"[RESP] log failed: {e}", "ERROR")
    return resp


@app.errorhandler(Exception)
def _handle_err(e):
    if isinstance(e, HTTPException):
        return e
    tb = traceback.format_exc()
    write_to_console(f"[ERR] {request.method} {request.path}\n{tb}", "ERROR")
    return jsonify({"success": False, "error": str(e)}), 500


def _open_browser():
    webbrowser.open(f"http://{HOST}:{PORT}/")


# =========================
# 3) Session：UID
# =========================
@app.post("/session/set-uid")
def set_session_uid():
    try:
        data = request.get_json() or {}
        uid = (data.get("uid") or "").strip()
        if not uid:
            return jsonify({"success": False, "error": "UID 不能為空"}), 400
        if any(c in uid for c in ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]):
            return jsonify({"success": False, "error": "UID 包含無效字符"}), 400

        # ⭐ 新增：只能用資料庫裡已存在的 UID
        if not user_exists(uid):
            write_to_console(f"set_session_uid: UID 不存在 -> {uid}", "WARN")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "此使用者不存在，請請管理者建立帳號",
                        "code": "USER_NOT_FOUND",
                    }
                ),
                404,
            )

        session["uid"] = uid
        write_to_console(f"成功設置 UID：{uid}", "INFO")
        return jsonify({"success": True, "uid": uid})
    except Exception as e:
        write_to_console(f"設置 UID 時發生錯誤：{e}", "ERROR")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/session/get-uid", methods=["GET"])
def get_session_uid():
    uid = session.get("uid")
    return jsonify({"success": True, "uid": uid})


@app.post("/create-uid-folder")
def create_uid_folder():
    write_to_console("[REQ] 進入 create_uid_folder", "INFO")
    data = request.get_json(silent=True) or {}
    uid = (data.get("uid") or "").strip()
    if not uid:
        write_to_console("create_uid_folder: UID 不能為空", "ERROR")
        return jsonify({"success": False, "error": "UID 不能為空"}), 400

    bad = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
    if any(c in uid for c in bad):
        write_to_console(f"create_uid_folder: UID 非法 -> {uid}", "ERROR")
        return jsonify({"success": False, "error": "UID 包含無效字符"}), 400

    # ⭐ 不再自動新增，只允許已存在的 UID
    if not user_exists(uid):
        write_to_console(f"create_uid_folder: UID 不存在 -> {uid}", "WARN")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "此使用者不存在，請請管理者建立帳號",
                    "code": "USER_NOT_FOUND",
                }
            ),
            404,
        )

    kid_dir = ROOT / "kid" / uid
    if not kid_dir.exists():
        kid_dir.mkdir(parents=True, exist_ok=True)
        write_to_console(f"[FS] 建立資料夾：{kid_dir}", "INFO")

    session["uid"] = uid
    return jsonify({"success": True, "uid": uid, "message": "UID 已載入"})


@app.post("/session/clear-uid")
def clear_session_uid():
    if "uid" in session:
        del session["uid"]
    return jsonify({"success": True, "message": "UID 已清除"})


@app.route("/test-score", methods=["POST"])
def test_score():
    try:
        data = request.get_json() or {}
        uid = (data.get("uid") or "").strip()
        task_id = (data.get("task_id") or "").strip()

        if not uid or not task_id:
            return jsonify({"success": False, "error": "uid 與 task_id 不可為空"}), 400

        score = 3  # 你目前先寫死 3 分

        try:
            # 這裡可能會因為 UID 不存在而丟 ValueError("USER_NOT_FOUND")
            test_date = insert_score(uid=uid, task_id=task_id)
        except ValueError as e:
            if str(e) == "USER_NOT_FOUND":
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "此使用者不存在，請管理者建立帳號",
                            "code": "USER_NOT_FOUND",
                        }
                    ),
                    404,
                )
            # 其他 ValueError 再往上丟，交給外層 except
            raise

        insert_task_payload(
            task_id=task_id,
            uid=uid,
            test_date=test_date,
            score=score,
            result_img_path="",
            data1=None,
        )
        _notify_admin_score_updated()
        return jsonify(
            {
                "success": True,
                "uid": uid,
                "task_id": task_id,
                "test_date": test_date.isoformat(),
                "score": score,
            }
        )
    except Exception as e:
        write_to_console(f"/test-score 錯誤: {e}", "ERROR")
        return jsonify({"success": False, "error": str(e)}), 500


# =========================
# 4) 背景執行 main.py
# =========================
def normalize_task_id(task_code_raw: str) -> str:
    if task_code_raw in TASK_MAP:
        return task_code_raw
    parts = task_code_raw.split("-")
    if len(parts) == 2:
        guess = parts[0][:1].upper() + parts[0][1:] + "-" + parts[1]
        if guess in TASK_MAP:
            return guess
    return task_code_raw


def resolve_script_path(task_code: str) -> Optional[Path]:
    guesses = [
        ROOT / task_code / "main.py",
        ROOT / task_code.lower() / "main.py",
        ROOT / normalize_task_id(task_code) / "main.py",
        ROOT / normalize_task_id(task_code).lower() / "main.py",
    ]
    for p in guesses:
        if p.exists():
            return p
    return None


def upload_task_images_to_mac(uid: str, img_id: str) -> bool:
    uploader_path = ROOT / "scripts" / "upload_to_mac_pdms.py"
    if not uploader_path.exists():
        write_to_console(f"[UPLOAD] 找不到上傳腳本: {uploader_path}", "ERROR")
        return False

    if not MAC_UPLOAD_HOST or not MAC_UPLOAD_USER:
        write_to_console(
            "[UPLOAD] 缺少上傳設定：MAC_UPLOAD_HOST 或 MAC_UPLOAD_USER", "ERROR"
        )
        return False

    cmd = [
        sys.executable,
        str(uploader_path),
        "--uid",
        uid,
        "--img-id",
        img_id,
        "--root",
        str(ROOT),
        "--host",
        MAC_UPLOAD_HOST,
        "--port",
        str(MAC_UPLOAD_PORT),
        "--user",
        MAC_UPLOAD_USER,
        "--remote-base",
        MAC_UPLOAD_REMOTE_BASE,
    ]

    if MAC_UPLOAD_PASSWORD:
        cmd.extend(["--password", MAC_UPLOAD_PASSWORD])
    if MAC_UPLOAD_KEY_PATH:
        cmd.extend(["--key-path", MAC_UPLOAD_KEY_PATH])

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW

    result = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creation_flags,
    )

    if result.stdout:
        write_to_console(f"[UPLOAD][stdout]\n{result.stdout}", "INFO")
    if result.stderr:
        write_to_console(f"[UPLOAD][stderr]\n{result.stderr}", "ERROR")

    if result.returncode == 0:
        write_to_console(f"[UPLOAD] 上傳成功: uid={uid}, img_id={img_id}", "INFO")
        return True

    write_to_console(
        f"[UPLOAD] 上傳失敗(returncode={result.returncode}): uid={uid}, img_id={img_id}",
        "ERROR",
    )
    return False


def _find_task_image(uid: str, img_id: str) -> Optional[Path]:
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        candidate = ROOT / "kid" / uid / f"{img_id}{ext}"
        if candidate.exists():
            return candidate
    return None


def submit_remote_analysis(uid: str, img_id: str) -> dict:
    mac_web_api_url = _mac_web_api_url()
    write_to_console(f"發送請求至遠端 API: {mac_web_api_url}", "INFO")

    files_to_send = []
    opened_files = []

    try:
        # 檢查是否為多圖關卡
        side_path = _find_task_image(uid, f"{img_id}-side")
        top_path = _find_task_image(uid, f"{img_id}-top")
        main_path = _find_task_image(uid, img_id)

        if side_path and top_path:
            f_side = open(side_path, "rb")
            f_top = open(top_path, "rb")
            opened_files.extend([f_side, f_top])
            files_to_send.append(("images", (side_path.name, f_side, "image/jpeg")))
            files_to_send.append(("images", (top_path.name, f_top, "image/jpeg")))
        elif main_path:
            f_main = open(main_path, "rb")
            opened_files.append(f_main)
            files_to_send.append(("images", (main_path.name, f_main, "image/jpeg")))
        else:
            raise FileNotFoundError(f"找不到照片檔案: uid={uid}, task={img_id}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response = requests.post(
            mac_web_api_url,
            data={"uid": uid, "img_id": img_id, "timestamp": timestamp},
            files=files_to_send,
            timeout=180,
        )
    finally:
        for f in opened_files:
            f.close()

    if response.status_code != 200:
        raise Exception(f"遠端 API 請求失敗 (HTTP {response.status_code}): {response.text}")

    payload = response.json()
    if not payload.get("ok"):
        raise Exception(f"遠端 API 回傳錯誤: {payload.get('msg')}")

    return payload


def _notify_admin_score_updated():
    def _post():
        try:
            requests.post("http://127.0.0.1:8001/internal/score-updated", timeout=2)
        except Exception:
            pass
    Thread(target=_post, daemon=True).start()


def run_analysis_in_background(
    task_id, uid, img_id, script_path, stair_type=None, cam_index_input=None
):
    try:
        processing_tasks[task_id] = {
            "status": "running",
            "uid": uid,
            "img_id": img_id,
            "start_time": datetime.now().isoformat(),
            "progress": 0,
        }
        write_to_console(f"開始分析任務 {task_id}: uid={uid}, task={img_id}", "INFO")

        task_id_std = normalize_task_id(img_id)

        # ★ Ch5-t1 特殊處理：本機執行 main.py（非遠端）
        if img_id.lower() in ["ch5-t1", "ch5-t1"]:
            write_to_console(f"[Ch5-t1] 執行本機遊戲程式", "INFO")
            
            # 取得 side camera index
            cam_idx = cam_index_input if cam_index_input is not None else SIDE
            
            # 執行本機 main.py
            ch5_main_path = ROOT / "ch5-t1" / "main.py"
            if not ch5_main_path.exists():
                raise FileNotFoundError(f"找不到 ch5-t1/main.py: {ch5_main_path}")
            
            cmd = [sys.executable, str(ch5_main_path), uid, str(cam_idx)]
            write_to_console(f"[Ch5-t1] 執行命令: {' '.join(cmd)}", "INFO")
            
            result = subprocess.run(
                cmd,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
            )
            
            if result.stdout:
                write_to_console(f"[Ch5-t1][stdout] {result.stdout}", "INFO")
            if result.stderr:
                write_to_console(f"[Ch5-t1][stderr] {result.stderr}", "WARN")
            
            score = result.returncode if result.returncode in (0, 1, 2) else 0
            write_to_console(f"[Ch5-t1] 遊戲完成，分數: {score}", "INFO")
            
            # 從狀態 JSON 讀取確認分數
            state_file = ROOT / "kid" / uid / "Ch5-t1_state.json"
            final_score = score
            if state_file.exists():
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        state = json.load(f)
                        if state.get("score", -1) >= 0:
                            final_score = state["score"]
                            write_to_console(f"[Ch5-t1] 從狀態檔讀取分數: {final_score}", "INFO")
                except Exception as e:
                    write_to_console(f"[Ch5-t1] 讀取狀態檔失敗: {e}", "WARN")
            
            # 寫入 DB
            try:
                ensure_task(task_id_std)
                test_date = insert_score(uid, task_id_std)
                result_img_path = f"kid/{uid}/Ch5-t1_result.mp4"
                insert_task_payload(
                    task_id=task_id_std,
                    uid=uid,
                    test_date=test_date,
                    score=final_score,
                    result_img_path=result_img_path,
                    data1=None,
                )
                write_to_console(f"[Ch5-t1] 分數已寫入 DB: {final_score}", "INFO")
            except Exception as e:
                write_to_console(f"[Ch5-t1] 寫入 DB 失敗: {e}", "ERROR")
                raise
            
            processing_tasks[task_id] = {
                "status": "completed",
                "uid": uid,
                "img_id": img_id,
                "end_time": datetime.now().isoformat(),
                "progress": 100,
                "result": {
                    "success": True,
                    "task_id": task_id_std,
                    "score": final_score,
                },
            }
            return

        # 其他任務：走遠端 API
        remote_response = submit_remote_analysis(uid, img_id)

        processing_tasks[task_id] = {
            "status": "completed",
            "uid": uid,
            "img_id": img_id,
            "end_time": datetime.now().isoformat(),
            "progress": 100,
            "result": {
                "success": True,
                "task_id": task_id_std,
                "remote_response": remote_response,
            },
        }
        score = remote_response.get("score")
        score_str = f"，分數 = {score}" if score is not None else ""
        write_to_console(f"任務 {task_id} 遠端分析完成：task={img_id}{score_str}", "INFO")
        _notify_admin_score_updated()

    except Exception as e:
        tb = traceback.format_exc()
        processing_tasks[task_id] = {"status": "error", "error": str(e)}
        write_to_console(f"背景任務 {task_id} 錯誤：{e}\n{tb}", "ERROR")


@app.post("/run-python")
def run_python_script():
    try:
        data = request.get_json() or {}
        img_id = (data.get("id") or "").strip()
        uid = (data.get("uid") or "").strip() or session.get("uid")
        cam_index_input = data.get("cam_index")

        if not img_id or not uid:
            return jsonify({"success": False, "error": "缺少參數"}), 400

        task_id = str(uuid.uuid4())
        stair_type = session.get("stair_type")
        processing_tasks[task_id] = {"status": "pending", "uid": uid}

        t = Thread(
            target=run_analysis_in_background,
            args=(task_id, uid, img_id, None, stair_type, cam_index_input),
        )
        t.daemon = True
        t.start()

        return jsonify({"success": True, "task_id": task_id})
    except Exception as e:
        write_to_console(f"/run-python 錯誤: {e}", "ERROR")
        return jsonify({"success": False, "error": str(e)}), 500


@app.get("/check-task/<task_id>")
def check_task_status(task_id):
    if task_id not in processing_tasks:
        return jsonify({"success": False, "error": "任務不存在"}), 404
    return jsonify({"success": True, **processing_tasks[task_id], "task_id": task_id})


@app.post("/save-stair-type")
def save_stair_type():
    try:
        data = request.get_json() or {}
        stair_type = data.get("stair_type", "").strip()
        if stair_type not in ["L", "R"]:
            return jsonify({"success": False, "error": "stair_type 只能是 L 或 R"}), 400
        session["stair_type"] = stair_type
        return jsonify({"success": True, "stair_type": stair_type})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =========================
# 5) 便利檢查 API
# =========================
@app.get("/db/ping")
def db_ping():
    try:
        v = db_exec("SELECT VERSION() AS v", fetch="one")
        return jsonify({"ok": True, "version": v["v"] if v else "?"})
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500


# ★★★★★★★ 新增：搜尋成績 API (修復 admin.js 初始化失敗) ★★★★★★★
@app.post("/api/search-scores")
def search_scores_api():
    try:
        data = request.get_json() or {}
        uid = data.get("uid", "").strip()
        task_id = data.get("task_id", "").strip()
        rows = []

        # 情況 1: 指定關卡 -> 查該關卡的資料表
        if task_id:
            try:
                table = task_id_to_table(task_id)
                sql = f"SELECT uid, '{task_id}' as task_id, score, test_date, time, result_img_path FROM `{table}` WHERE uid=%s ORDER BY test_date DESC, time DESC"
                rows = db_exec(sql, (uid,), fetch="all")
            except Exception as e:
                write_to_console(f"查詢子表失敗 {task_id}: {e}", "WARN")
                rows = []

        # 情況 2: 沒指定關卡 -> 查總表 score_list，並從各任務子表查詢結果圖片路徑
        if not rows and not task_id:
            sql = "SELECT uid, task_id, test_date, time FROM score_list WHERE uid=%s ORDER BY test_date DESC, time DESC"
            base_rows = db_exec(sql, (uid,), fetch="all")
            if base_rows:
                for r in base_rows:
                    r["score"] = "-" 
                    r["result_img_path"] = ""
                    
                    # 從該任務的子表查詢真實的 result_img_path
                    try:
                        task_table = task_id_to_table(r["task_id"])
                        sub_sql = f"SELECT result_img_path FROM `{task_table}` WHERE uid=%s AND test_date=%s ORDER BY time DESC LIMIT 1"
                        sub_rows = db_exec(sub_sql, (uid, r["test_date"]), fetch="all")
                        if sub_rows and sub_rows[0].get("result_img_path"):
                            r["result_img_path"] = sub_rows[0]["result_img_path"]
                    except Exception:
                        pass  # 若查詢失敗，result_img_path 保持空
                    
                    rows.append(r)

        # 格式化日期
        for r in rows:
            if isinstance(r.get("test_date"), (date, datetime)):
                r["test_date"] = r["test_date"].isoformat()
            if r.get("time") and not isinstance(r.get("time"), str):
                r["time"] = str(r["time"])

        return jsonify({"success": True, "data": rows})
    except Exception as e:
        write_to_console(f"搜尋失敗: {e}", "ERROR")
        return jsonify({"success": False, "error": str(e)}), 500


# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

# =========================
# 6) OpenCV 相機
# =========================
camera = None
camera_active = False
current_task_id = ""
camera_lock = threading.RLock()

LIVE_CAMERA_WIDTH = 1280
LIVE_CAMERA_HEIGHT = 720


def release_camera():
    global camera, camera_active
    with camera_lock:
        if camera is not None:
            try:
                camera.release()
                write_to_console("[相機] 相機已釋放", "INFO")
            except Exception as e:
                write_to_console(f"[相機] 釋放失敗: {e}", "WARN")
            camera = None
        camera_active = False
    time.sleep(0.3)


# ★★★★★ 修正 2：相機初始化改用 DSHOW + 自動切換 ★★★★★
def init_camera(camera_index=TOP):
    global camera, camera_active
    try:
        with camera_lock:
            release_camera()

            print(f"[相機] 嘗試開啟相機 Index: {camera_index}...")
            camera = _open_camera_capture(camera_index)

            # 如果還是打不開，且原本不是 0，嘗試強制切回 0 (預設)
            if not camera.isOpened() and camera_index != 0:
                print("[相機] 指定鏡頭失敗，嘗試切換回預設鏡頭 (Index 0)...")
                camera = _open_camera_capture(0)

            if not camera.isOpened():
                raise Exception(f"無法開啟任何相機 (Index: {camera_index})")

            camera.set(cv2.CAP_PROP_FRAME_WIDTH, LIVE_CAMERA_WIDTH)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, LIVE_CAMERA_HEIGHT)
            camera.set(cv2.CAP_PROP_FPS, 30)

            # 讀取測試
            ret, frame = camera.read()
            if not ret:
                # 有時候剛開啟第一幀會是黑的，再試一次
                time.sleep(0.5)
                ret, frame = camera.read()
                if not ret:
                    raise Exception("相機已開啟但無法讀取畫面")

            h, w = frame.shape[:2]
            crop_w = int(w * CROP_RATE)
            crop_h = int(h * CROP_RATE)
            write_to_console(
                f"相機開啟成功，來源: {camera_index}，原始尺寸: {w}x{h}，裁切後: {crop_w}x{crop_h}",
                "INFO",
            )
            camera_active = True
            return True

    except Exception as e:
        write_to_console(f"相機初始化失敗: {e}", "ERROR")
        release_camera()
        return False


@app.post("/camera-settings/select-roi")
def select_camera_roi():
    """開啟本地 OpenCV 視窗供使用者框選 ROI"""
    try:
        data = request.get_json() or {}
        camera_index = int(data.get("camera_index", TOP))
        force_gui = bool(data.get("force_gui", False))
        
        write_to_console(f"[ROI] 準備開啟相機 Index {camera_index} 進行 ROI 選取", "INFO")
        
        # 暫時停止目前可能正在運行的相機預覽
        release_camera()
        time.sleep(0.5)

        cap = _open_camera_capture(camera_index)
        if not cap or not cap.isOpened():
            return jsonify({
                "success": False,
                "error": f"無法開啟相機 Index {camera_index}",
                "fallback": "manual",
            })

        # 設定與實際預覽一致的解析度，避免框選座標與最後顯示不一致
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, LIVE_CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, LIVE_CAMERA_HEIGHT)
        
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return jsonify({
                "success": False,
                "error": "讀取影像失敗",
                "fallback": "manual",
            })

        if _should_skip_opencv_roi_gui(force_gui):
            write_to_console("[ROI] 目前環境略過 OpenCV 視窗，改用手動 ROI", "WARN")
            return jsonify(
                {
                    "success": False,
                    "error": "目前環境不支援 OpenCV ROI 視窗，已切換為手動輸入模式。",
                    "fallback": "manual",
                }
            )

        # 彈出 ROI 選取視窗 (這是本地視窗)
        window_name = "Select ROI (ENTER/SPACE to confirm, ESC to cancel)"
        roi_result = _select_roi_in_subprocess(frame, window_name)
        if roi_result.get("success"):
            new_roi = roi_result["roi"]
            save_app_settings(roi=new_roi)
            write_to_console(f"[ROI] 已更新座標：{new_roi}", "INFO")
            return jsonify({"success": True, "roi": new_roi})

        write_to_console(f"[ROI] 使用子行程框選失敗: {roi_result.get('error', 'unknown')}", "WARN")
        return jsonify(roi_result)

    except Exception as e:
        write_to_console(f"[ROI] 發生錯誤: {e}", "ERROR")
        return jsonify({"success": False, "error": str(e)}), 500


@app.post("/camera-settings/roi")
def update_camera_roi():
    try:
        data = request.get_json() or {}
        roi_data = data.get("roi") if isinstance(data.get("roi"), dict) else data

        x = int(roi_data.get("x", 0))
        y = int(roi_data.get("y", 0))
        w = int(roi_data.get("w", 0))
        h = int(roi_data.get("h", 0))

        if x < 0 or y < 0 or w <= 0 or h <= 0:
            return jsonify({"success": False, "error": "ROI 座標必須為非負整數，且寬高需大於 0"})

        new_roi = {"x": x, "y": y, "w": w, "h": h}
        save_app_settings(roi=new_roi)
        write_to_console(f"[ROI] 已手動更新座標：{new_roi}", "INFO")
        return jsonify({"success": True, "roi": new_roi})
    except Exception as e:
        write_to_console(f"[ROI] 手動更新失敗: {e}", "ERROR")
        return jsonify({"success": False, "error": str(e)}), 500


def crop_center(frame, _dummy=None):
    """
    裁切影像：優先使用 .env 中的 ROI 固定座標。
    """
    h, w = frame.shape[:2]
    
    # 檢查是否有自定義 ROI
    if ROI_W > 0 and ROI_H > 0:
        x1, y1 = max(0, ROI_X), max(0, ROI_Y)
        x2, y2 = min(w, ROI_X + ROI_W), min(h, ROI_Y + ROI_H)
        
        if x2 > x1 and y2 > y1:
            return frame[y1:y2, x1:x2]

    # 退回到預設固定座標 (原本程式碼的 fallback)
    x, y, target_w, target_h = 164, 95, 1166, 909
    return frame[y : y + target_h, x : x + target_w]


NO_CROP_TASKS = {"ch1-t2", "ch1-t3", "ch1-t4"}

def get_frame():
    global camera, camera_active, current_task_id, current_camera_index
    try:
        with camera_lock:
            if not camera_active or camera is None:
                return None
            ret, frame = camera.read()
            if not ret:
                return None

            if current_task_id not in NO_CROP_TASKS and current_camera_index != SIDE:
                frame = crop_center(frame, CROP_RATE)

            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return buffer.tobytes()
    except Exception:
        return None


@app.post("/opencv-camera/stop")
def stop_opencv_camera():
    release_camera()
    return jsonify({"success": True})


@app.post("/opencv-camera/start")
def start_opencv_camera():
    try:
        data = request.get_json() or {}
        cam_index = data.get("camera_index", TOP)
        global current_task_id, camera_active, current_camera_index
        current_task_id = (data.get("task_id") or "").strip()
        current_camera_index = int(cam_index)

        if DEMO_MODE:
            write_to_console(f"[DEMO] 啟動示範模式，關卡: {current_task_id}", "INFO")
            camera_active = True
            return jsonify({"success": True})

        if init_camera(cam_index):
            return jsonify({"success": True})
        return jsonify({"success": False}), 500
    except Exception:
        return jsonify({"success": False}), 500


@app.get("/opencv-camera/frame")
def get_opencv_frame():
    if not camera_active:
        return jsonify({"success": False}), 400

    if DEMO_MODE:
        uid = session.get("uid", "default")
        global current_task_id
        # 示範模式：讀取預放的圖片
        img_path = ROOT / "kid" / uid / f"{current_task_id}.jpg"
        if not img_path.exists():
            # 嘗試讀取 lowercase 版本
            img_path = ROOT / "kid" / uid / f"{current_task_id.lower()}.jpg"
        
        if img_path.exists():
            with open(img_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
                return jsonify({"success": True, "image": img_b64})
        return jsonify({"success": False, "error": f"找不到測試圖片: {img_path.name}"}), 404

    frame_data = get_frame()
    if frame_data is None:
        return jsonify({"success": False}), 500
    img_b64 = base64.b64encode(frame_data).decode("utf-8")
    return jsonify({"success": True, "image": img_b64})


@app.post("/opencv-camera/capture")
def capture_opencv_photo():
    try:
        data = request.get_json() or {}
        task_id_input = (data.get("task_id") or "").strip()
        uid = (data.get("uid") or "").strip() or session.get("uid", "default")

        if not task_id_input:
            return jsonify({"success": False}), 400

        if DEMO_MODE:
            # 示範模式：確認圖片存在即可，不需實際寫入
            img_path = ROOT / "kid" / uid / f"{task_id_input}.jpg"
            if not img_path.exists():
                img_path = ROOT / "kid" / uid / f"{task_id_input.lower()}.jpg"
            
            if img_path.exists():
                write_to_console(f"[DEMO] 模擬拍照成功: {img_path.name}", "INFO")
                return jsonify({
                    "success": True,
                    "uid": uid,
                    "task_id": task_id_input,
                    "filename": img_path.name,
                    "analysis_started": False,
                })
            return jsonify({"success": False, "error": "找不到預放的測試圖片"}), 404

        frame_data = get_frame()
        if frame_data is None:
            return jsonify({"success": False}), 500

        target_dir = ROOT / "kid" / uid
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{task_id_input}.jpg"
        file_path = target_dir / filename

        nparr = np.frombuffer(frame_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        cv2.imwrite(str(file_path), img)
        write_to_console(f"圖像存儲成功: {file_path}", "INFO")

        # 修正：不自動啟動分析，交由前端呼叫 /run-python
        return jsonify(
            {
                "success": True,
                "uid": uid,
                "task_id": task_id_input,
                "filename": filename,
                "analysis_started": False,
            }
        )
    except Exception:
        return jsonify({"success": False}), 500


@app.get("/game-state/<uid>")
def get_game_state(uid):
    try:
        state_file = ROOT / "kid" / uid / "Ch5-t1_state.json"
        if not state_file.exists():
            return jsonify({"success": False, "error": "狀態檔案不存在"}), 404
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        return jsonify({"success": True, "state": state})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.post("/clear-game-state")
def clear_game_state():
    try:
        data = request.get_json() or {}
        uid = (data.get("uid") or "").strip()
        if not uid:
            return jsonify({"success": False}), 400

        state_file = ROOT / "kid" / uid / "Ch5-t1_state.json"
        initial_state = {
            "running": False,
            "bean_count": 0,
            "remaining_time": 60,
            "target_bean_count": 10,
            "warning": False,
            "game_over": False,
            "score": -1,
        }
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(initial_state, f, ensure_ascii=False, indent=2)
        write_to_console(f"[Ch5-t1] 遊戲狀態已清空: {uid}", "INFO")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    try:
        write_to_console(f"準備啟動 Flask 應用程式，HOST={HOST}, PORT={PORT}", "INFO")
        threading.Timer(0.5, _open_browser).start()
        write_to_console("已設定瀏覽器自動開啟", "INFO")
    except Exception as e:
        write_to_console(f"設定瀏覽器自動開啟時發生錯誤：{str(e)}", "ERROR")

    try:
        write_to_console("Flask 應用程式開始運行", "INFO")
        cli = sys.modules["flask.cli"]
        cli.show_server_banner = lambda *x: None
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        write_to_console("接收到中斷信號，正在關閉應用程式", "INFO")
    except Exception as e:
        write_to_console(f"應用程式運行時發生錯誤：{str(e)}", "ERROR")
    finally:
        write_to_console("Flask 應用程式已關閉", "INFO")
