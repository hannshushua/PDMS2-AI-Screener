# analyze_main.py
import cv2
import numpy as np
import json
import glob
import os
from pathlib import Path
import socket
import uuid
import sys

try:
    import pymysql
except ImportError:
    pymysql = None

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"

CROP_FOLDER = r"PDMS2_web\ch2-t4\new"
SHOW_SCALE = 0.7
MARGIN = 40


def _read_env_value(key, default):
    """從 .env 讀取值"""
    if not ENV_PATH.exists():
        return default

    try:
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            current_key, value = raw_line.split("=", 1)
            if current_key.strip() == key:
                parsed = float(value.strip())
                return parsed if parsed > 0 else default
    except Exception:
        return default

    return default


def _get_machine_id() -> str:
    """取得或生成本機識別碼"""
    if ENV_PATH.exists():
        try:
            for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line.startswith("MACHINE_ID="):
                    machine_id = line.split("=", 1)[1].strip()
                    if machine_id:
                        return machine_id
        except Exception:
            pass
    hostname = socket.gethostname()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, hostname))


def _read_db_config(key: str, default: float) -> float:
    """優先從資料庫讀取本機配置，失敗時回退到 .env"""
    if pymysql is None:
        return _read_env_value(key, default)
    
    if not ENV_PATH.exists():
        return default
    
    db_config = {}
    try:
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            k, v = raw_line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k in {"DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"}:
                db_config[k] = v
    except Exception:
        return _read_env_value(key, default)
    
    if not all(k in db_config for k in ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]):
        return _read_env_value(key, default)
    
    try:
        machine_id = _get_machine_id()
        conn = pymysql.connect(
            host=db_config["DB_HOST"],
            port=int(db_config["DB_PORT"]),
            user=db_config["DB_USER"],
            password=db_config["DB_PASSWORD"],
            database=db_config["DB_NAME"],
            charset="utf8mb4",
            autocommit=True,
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            sql_map = {"PDMS2_PX2CM": "px2cm"}
            if key not in sql_map:
                conn.close()
                return _read_env_value(key, default)
            col_name = sql_map[key]
            cur.execute(
                f"SELECT {col_name} FROM machine_configs WHERE machine_id=%s LIMIT 1",
                (machine_id,)
            )
            row = cur.fetchone()
            conn.close()
            if row and col_name in row:
                parsed = float(row[col_name])
                return parsed if parsed > 0 else default
    except Exception as e:
        print(f"[DB] 查詢遠端配置失敗: {e}，回退到本機 .env", file=sys.stderr)
    
    return _read_env_value(key, default)


def _read_env_float(key, default):
    """向後相容：改用 _read_db_config"""
    return _read_db_config(key, default)


def show(title, img, scale=SHOW_SCALE):
    h, w = img.shape[:2]
    # cv2.imshow(title, cv2.resize(img, (int(w * scale), int(h * scale))))


def preprocess_blackhat(img_bgr):
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 自適應 kernel（依影像尺寸調整，避免 51x51 在小圖過度平滑）
    H, W = gray.shape[:2]
    k = max(31, (min(H, W) // 20) | 1)  # 黑帽核，約為短邊/20 並取奇數
    kh = max(3, (W // 60) | 1)  # 水平強化的寬（越大越吃長水平線）
    kv = 3  # 水平強化的高

    bh = cv2.morphologyEx(
        gray, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    )

    # Otsu 太嚴苛時退一步
    _, bw = cv2.threshold(bh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if cv2.countNonZero(bw) < 80:
        _, bw = cv2.threshold(bh, 25, 255, cv2.THRESH_BINARY)

    # 消噪與加強水平連續性
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), 1)
    bw = cv2.morphologyEx(
        bw, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (kh, kv)), 1
    )

    # 切掉邊框
    MARGIN = 40
    bw[:MARGIN, :] = 0
    bw[-MARGIN:, :] = 0
    bw[:, :MARGIN] = 0
    bw[:, -MARGIN:] = 0

    horiz = cv2.morphologyEx(
        bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (kh * 2, kv))
    )
    return bw, horiz


def extract_trace_mask(img_bgr):
    # HSV：紅色兩端 + 放寬飽和與亮度
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    lower1 = np.array([0, 20, 20])
    upper1 = np.array([15, 255, 255])
    lower2 = np.array([165, 20, 20])
    upper2 = np.array([180, 255, 255])
    mask_hsv = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)

    # RGB 主導：R 顯著大於 G/B
    b, g, r = cv2.split(img_bgr)
    dom = (
        (r.astype(np.int16) - g.astype(np.int16) > 18)
        & (r.astype(np.int16) - b.astype(np.int16) > 18)
        & (r > 40)
    )
    mask_dom = dom.astype(np.uint8) * 255

    # YCrCb：Cr 偏紅
    ycrcb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2YCrCb)
    Cr = ycrcb[:, :, 1]
    mask_cr = (Cr > 135).astype(np.uint8) * 255

    # Lab：a* 偏紅（對陰影更友善）
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2Lab)
    a = lab[:, :, 1]
    mask_lab = (a > 150).astype(np.uint8) * 255

    trace = mask_hsv | mask_dom | mask_cr | mask_lab

    # 形態學順序：先關再開，略膨脹補洞
    trace = cv2.morphologyEx(trace, cv2.MORPH_CLOSE, np.ones((9, 3), np.uint8), 1)
    trace = cv2.morphologyEx(trace, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), 1)
    trace = cv2.dilate(trace, np.ones((3, 3), np.uint8), 1)
    return trace


def fallback_baseline_from_projection(bw, prefer_band_px=6):
    h, w = bw.shape
    proj = bw.sum(axis=1).astype(np.float32)
    proj = cv2.GaussianBlur(proj.reshape(-1, 1), (1, 9), 0).ravel()
    y0 = int(np.argmax(proj))
    band_px = prefer_band_px
    y1 = max(0, y0 - band_px)
    y2 = min(h - 1, y0 + band_px)

    band = np.zeros_like(bw)
    band[y1 : y2 + 1, :] = 255
    line_pixels = cv2.bitwise_and(bw, band)
    line_pixels = cv2.morphologyEx(
        line_pixels, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), 1
    )

    num, labels, stats, _ = cv2.connectedComponentsWithStats(line_pixels, 8)
    if num <= 1:
        return (0, y0, w - 1, y0)

    areas = stats[1:, cv2.CC_STAT_AREA]
    target = 1 + int(np.argmax(areas)) if len(areas) > 0 else 0
    comp_mask = (labels == target).astype(np.uint8) * 255

    ys, xs = np.where(comp_mask > 0)
    if len(xs) < 2:
        return (0, y0, w - 1, y0)

    pts = np.float32(np.column_stack([xs, ys]))
    vx, vy, cx, cy = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
    vx, vy, cx, cy = float(vx[0]), float(vy[0]), float(cx[0]), float(cy[0])

    t = (xs - cx) * vx + (ys - cy) * vy
    tL, tR = t.min(), t.max()
    xL = int(round(cx + vx * tL))
    yL = int(round(cy + vy * tL))
    xR = int(round(cx + vx * tR))
    yR = int(round(cy + vy * tR))
    xL = np.clip(xL, 0, w - 1)
    xR = np.clip(xR, 0, w - 1)
    yL = np.clip(yL, 0, h - 1)
    yR = np.clip(yR, 0, h - 1)
    return (xL, yL, xR, yR)


def _is_near_horizontal(x1, y1, x2, y2, tol_deg=8):
    # 以「水平」為目標過濾 Hough 結果
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return False
    ang = abs(np.degrees(np.arctan2(dy, dx)))
    ang = min(ang, 180 - ang)  # 0 ~ 90
    return ang <= tol_deg


def _score_line(x1, y1, x2, y2, w, h, near_border_margin=40):
    length = np.hypot(x2 - x1, y2 - y1)
    tilt_pen = abs(y2 - y1) * 4.0  # 傾斜懲罰（越水平越好）
    xmid = 0.5 * (x1 + x2)
    center_pen = abs(xmid - w * 0.5) * 0.6  # 越靠近中央越好
    border_pen = 0
    if (
        min(x1, x2) < near_border_margin
        or max(x1, x2) > w - 1 - near_border_margin
        or min(y1, y2) < near_border_margin
        or max(y1, y2) > h - 1 - near_border_margin
    ):
        border_pen = 120.0  # 避免吃到邊緣線
    return length - tilt_pen - center_pen - border_pen


def find_baseline_and_show_all(img_bgr, pixel_per_cm):
    h, w = img_bgr.shape[:2]
    bw, horiz = preprocess_blackhat(img_bgr)

    # === Hough：先在水平強化圖上抓線，再在 bw 上補抓（雙保險）===
    edges = cv2.Canny(horiz, 30, 150)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=max(50, w // 20),
        minLineLength=max(80, w // 5),
        maxLineGap=max(20, w // 80),
    )
    if lines is None:
        edges2 = cv2.Canny(bw, 30, 150)
        lines = cv2.HoughLinesP(
            edges2,
            1,
            np.pi / 180,
            threshold=max(50, w // 20),
            minLineLength=max(80, w // 5),
            maxLineGap=max(20, w // 80),
        )

    # 視覺疊圖（不開窗時純保留記錄）
    all_on_img = img_bgr.copy()
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            cv2.line(all_on_img, (x1, y1), (x2, y2), (255, 0, 0), 2)

    # === 過濾非水平線，並用自訂打分挑最好那條 ===
    have_line = False
    if lines is not None:
        candidates = []
        for x1, y1, x2, y2 in lines[:, 0]:
            if not _is_near_horizontal(x1, y1, x2, y2, tol_deg=9):
                continue
            s = _score_line(x1, y1, x2, y2, w, h)
            candidates.append((s, (x1, y1, x2, y2)))
        if candidates:
            candidates.sort(key=lambda t: t[0], reverse=True)
            bx1, by1, bx2, by2 = candidates[0][1]
            have_line = True

    # === 若 Hough 失手，用垂直投影 + RANSAC 再撐一下 ===
    if not have_line:
        xL, yL, xR, yR = fallback_baseline_from_projection(bw)
    else:
        # 從帶狀區域抽點，做 fitLine（等價於 RANSAC 的穩定線性擬合）
        A = by1 - by2
        B = bx2 - bx1
        C = bx1 * by2 - bx2 * by1
        den = (A * A + B * B) ** 0.5 + 1e-6
        band_px = max(5, int(round(0.15 * pixel_per_cm)))  # 帶寬依比例縮放

        yy, xx = np.indices((h, w))
        dist = np.abs(A * xx + B * yy + C) / den
        band_mask = (dist <= band_px).astype(np.uint8) * 255

        line_pixels = cv2.bitwise_and(bw, band_mask)
        k_bridge = cv2.getStructuringElement(cv2.MORPH_RECT, (max(31, w // 20), 1))
        line_pixels = cv2.morphologyEx(line_pixels, cv2.MORPH_CLOSE, k_bridge, 1)
        line_pixels = cv2.morphologyEx(
            line_pixels, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), 1
        )

        ys, xs = np.where(line_pixels > 0)
        if len(xs) < 20:
            xL, yL, xR, yR = fallback_baseline_from_projection(bw)
        else:
            pts = np.float32(np.column_stack([xs, ys]))
            vx, vy, cx, cy = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
            vx, vy, cx, cy = float(vx[0]), float(vy[0]), float(cx[0]), float(cy[0])
            t = (xs - cx) * vx + (ys - cy) * vy
            tL, tR = t.min(), t.max()
            xL, yL = int(round(cx + vx * tL)), int(round(cy + vy * tL))
            xR, yR = int(round(cx + vx * tR)), int(round(cy + vy * tR))

    # === 產生「粗」基準線遮罩，後續拿來排除基準線本體 ===
    base_only = np.zeros((h, w), np.uint8)
    cv2.line(base_only, (xL, yL), (xR, yR), 255, 5)
    base_only = cv2.dilate(base_only, np.ones((1, 9), np.uint8), 1)

    # === 抽出手畫曲線（用改良的 extract_trace_mask） ===
    trace = extract_trace_mask(img_bgr)

    # 計算到基準線的距離
    A = yL - yR
    B = xR - xL
    C = xL * yR - xR * yL
    den = (A * A + B * B) ** 0.5 + 1e-6
    yy, xx = np.indices(trace.shape)
    dist_from_line = np.abs(A * xx + B * yy + C) / den

    # 限縮在合理帶寬內，避免遠端髒點
    TH_CM = 1.2
    TH_PX = TH_CM * pixel_per_cm
    band_limit_px = int(max(TH_PX * 3.0, 50))
    trace[dist_from_line > band_limit_px] = 0

    # 從黑白圖補充可能遺漏的曲線像素，但先排除基準線本體
    curve_from_bw = cv2.bitwise_and(
        bw, cv2.bitwise_not(cv2.dilate(base_only, np.ones((1, 19), np.uint8), 1))
    )
    curve_from_bw[dist_from_line > band_limit_px] = 0
    curve_from_bw = cv2.morphologyEx(
        curve_from_bw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), 1
    )
    curve_from_bw = cv2.morphologyEx(
        curve_from_bw,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (13, 3)),
        1,
    )
    trace = cv2.bitwise_or(trace, curve_from_bw)

    # 切掉左右貼邊的殘影
    EDGE_STRIP = 35
    trace[:, :EDGE_STRIP] = 0
    trace[:, -EDGE_STRIP:] = 0

    # 只保留基準線附近的一段（中心 +/-25px）
    num, labels, stats, _ = cv2.connectedComponentsWithStats(trace, 8)
    keep = np.zeros_like(trace)
    x_min = max(0, min(xL, xR) - 25)
    x_max = min(trace.shape[1] - 1, max(xL, xR) + 25)
    for i in range(1, num):
        x, y, w_, h_, area = stats[i]
        touches_border = (
            x == 0
            or y == 0
            or x + w_ >= trace.shape[1] - 1
            or y + h_ >= trace.shape[0] - 1
        )
        if touches_border:
            continue
        cx = x + w_ / 2.0
        if cx < x_min or cx > x_max:
            continue
        keep[labels == i] = 255
    trace = keep

    # === 最大偏差（優先抓 > TH 的；否則抓所有像素中的最大） ===
    ys, xs = np.where(trace > 0)
    if len(xs) > 0:
        dist_all = dist_from_line[ys, xs]
        over_mask = dist_all > TH_PX
        pick = (
            np.flatnonzero(over_mask)[np.argmax(dist_all[over_mask])]
            if np.any(over_mask)
            else int(np.argmax(dist_all))
        )
        far_x, far_y = int(xs[pick]), int(ys[pick])
        far_dev_px = float(dist_all[pick])
        far_dev_cm = far_dev_px / pixel_per_cm
        print(
            f"最遠點: ({far_x}, {far_y}) 偏差 {far_dev_cm:.3f} cm （{far_dev_px:.1f} px）"
        )
    else:
        print("最遠點: 無（未找到 trace 像素）")
        far_dev_cm = 0.0

    # === 偏離區分（強/弱雙門檻 + 基於基準線方向的橋接） ===
    signed = (A * xs + B * ys + C) / den if len(xs) > 0 else np.array([])
    over = np.zeros_like(trace)
    any_dev_mask = np.zeros_like(trace)
    mild_dev_mask = np.zeros_like(trace)

    if len(xs) > 0:
        delta_px = int(max(1, round(0.25 * pixel_per_cm)))  # 遞進帶
        strong_pos = np.zeros_like(trace)
        strong_neg = np.zeros_like(trace)
        weak_pos = np.zeros_like(trace)
        weak_neg = np.zeros_like(trace)
        strong_pos[ys[signed > TH_PX], xs[signed > TH_PX]] = 255
        strong_neg[ys[signed < -TH_PX], xs[signed < -TH_PX]] = 255
        weak_pos[ys[signed > TH_PX - delta_px], xs[signed > TH_PX - delta_px]] = 255
        weak_neg[ys[signed < -TH_PX + delta_px], xs[signed < -TH_PX + delta_px]] = 255

        def hysteresis_keep(weak, strong):
            num, labels, stats, _ = cv2.connectedComponentsWithStats(weak, 8)
            if num <= 1:
                return np.zeros_like(weak)
            out = np.zeros_like(weak)
            for i in range(1, num):
                comp = labels == i
                if (strong[comp] > 0).any():
                    out[comp] = 255
            return out

        over_pos = hysteresis_keep(weak_pos, strong_pos)
        over_neg = hysteresis_keep(weak_neg, strong_neg)

        # 沿著基準線方向作橋接，避免被小間隙切段
        L = np.hypot(xR - xL, yR - yL) + 1e-6
        vx = (xR - xL) / L
        vy = (yR - yL) / L
        cx0 = 0.5 * (xL + xR)
        cy0 = 0.5 * (yL + yR)

        def bridge_along_baseline(mask, cx, cy, vx, vy, gap_px):
            h, w = mask.shape
            ang = np.degrees(np.arctan2(vy, vx))
            M = cv2.getRotationMatrix2D((cx, cy), ang, 1.0)
            rot = cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_NEAREST)
            if gap_px % 2 == 0:
                gap_px += 1
            rot = cv2.morphologyEx(
                rot,
                cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_RECT, (gap_px, 3)),
                1,
            )
            Minv = cv2.getRotationMatrix2D((cx, cy), -ang, 1.0)
            return cv2.warpAffine(rot, Minv, (w, h), flags=cv2.INTER_NEAREST)

        merge_gap_px = int(max(TH_PX * 1.2, pixel_per_cm * 0.45))
        over_pos = bridge_along_baseline(over_pos, cx0, cy0, vx, vy, merge_gap_px)
        over_neg = bridge_along_baseline(over_neg, cx0, cy0, vx, vy, merge_gap_px)
        over = cv2.bitwise_or(over_pos, over_neg)

        # 輕微偏離（≥ ε cm）
        EPS_CM = 0.4
        EPS_PX = int(max(1, round(EPS_CM * pixel_per_cm)))
        any_pos = np.zeros_like(trace)
        any_neg = np.zeros_like(trace)
        any_pos[ys[signed > EPS_PX], xs[signed > EPS_PX]] = 255
        any_neg[ys[signed < -EPS_PX], xs[signed < -EPS_PX]] = 255
        any_pos = bridge_along_baseline(any_pos, cx0, cy0, vx, vy, merge_gap_px)
        any_neg = bridge_along_baseline(any_neg, cx0, cy0, vx, vy, merge_gap_px)
        any_dev_mask = cv2.bitwise_or(any_pos, any_neg)
        mild_dev_mask = cv2.bitwise_and(any_dev_mask, cv2.bitwise_not(over))

    # === 著色輸出 ===
    overlay_dev = img_bgr.copy()
    overlay_dev[trace > 0] = (0, 255, 0)  # 線跡：綠
    overlay_dev[mild_dev_mask > 0] = (0, 255, 255)  # 輕微：黃
    overlay_dev[over > 0] = (0, 0, 255)  # 嚴重：紅
    cv2.line(overlay_dev, (xL, yL), (xR, yR), (255, 0, 0), 3)  # 基準線：藍

    # === 次數計數：避免把小雜點算進去，面積門檻依比例調 ===
    def count_blocks(bin_img, min_area_px):
        num, _, stats, _ = cv2.connectedComponentsWithStats(bin_img, 8)
        areas = stats[1:, cv2.CC_STAT_AREA] if num > 1 else np.array([])
        return int(np.sum(areas >= min_area_px))

    min_len_cm = 0.4
    min_area_px = int(max(25, pixel_per_cm * min_len_cm))  # 比你原本略高，減少碎片

    dev_count = count_blocks(any_dev_mask, min_area_px)
    over_count = count_blocks(over, min_area_px)

    print(f"偏離次數（任何偏離）：{dev_count} 次")
    print(f"嚴重偏離（> {TH_CM:.1f} cm）：{over_count} 次")
    print(f"最大偏差: {far_dev_cm:.3f} cm")

    # === 評分：先看最大偏差，再依「任何偏離」次數 ===
    if far_dev_cm >= 1.2:
        score, reason = 0, "最大偏差 ≥ 1.2 cm"
    else:
        if dev_count <= 2:
            score = 2
        elif dev_count <= 4:
            score = 1
        else:
            score = 0
        reason = f"偏離次數={dev_count}"
    print(f"得分: {score} 分（{reason}）")

    # === [新增] 自動儲存結果圖到 result 資料夾 ===
    result_dir = BASE_DIR / "result"
    os.makedirs(result_dir, exist_ok=True)
    base_name = "result_overlay.jpg"
    out_path = str(result_dir / base_name)
    ok = cv2.imwrite(out_path, overlay_dev)
    if ok:
        print(f"✅ 已輸出結果圖：{out_path}")
    else:
        print(f"⚠️ 無法儲存結果圖：{out_path}")

    # 與 ch2-t5 相容：回傳 (score, result_img)
    return score, overlay_dev


# 取代整個 main()：只跑單張 + 從 .env 讀比例
def main():
    # 1) 讀單一比例 .env
    pixel_per_cm = _read_env_float("PDMS2_PX2CM", 1.0)
    if pixel_per_cm <= 0:
        raise ValueError(".env 內 pixel_per_cm 無效")

    # 2) 只跑一張圖（改這個編號即可）
    img_num = 1
    img_path = os.path.join(CROP_FOLDER, f"new{img_num}.jpg")
    if not os.path.exists(img_path):
        raise FileNotFoundError(f"找不到裁切圖：{os.path.abspath(img_path)}")

    # 3) 讀圖並分析
    img = cv2.imread(img_path)
    if img is None:
        raise ValueError(f"無法讀取影像：{img_path}")

    print(
        f"\n=== 處理 {os.path.basename(img_path)} | pixel_per_cm={pixel_per_cm:.4f} ==="
    )
    find_baseline_and_show_all(img, pixel_per_cm)

    # 4) 視窗控制
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
