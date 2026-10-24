import os
import sys

# 沒接住的例外（例如 import torch 失敗）結束碼是 1，會被 web.py 當成 1 分，所以一律改成 -1 回報分析失敗
def _exit_on_crash(*exc_info):
    sys.__excepthook__(*exc_info)
    sys.stdout.flush()
    os._exit(-1)
sys.excepthook = _exit_on_crash

import cv2
import numpy as np
import torch

_original_torch_load = torch.load
def safe_load(*args, **kwargs):
    # 如果呼叫時沒有特別指定 weights_only，就強制設為 False
    kwargs.setdefault('weights_only', False)
    return _original_torch_load(*args, **kwargs)
torch.load = safe_load

from ultralytics import YOLO, SAM
import json
import sys
import os
from pathlib import Path

# ================== 核心設定 ==================
# 分析流程：
#   1. cube_top.pt 找積木 -> SAM2 切積木遮罩；line.pt 找繩子 -> SAM2 切繩子遮罩 (扣掉積木 = 看得到的繩子)
#   2. 繩子遮罩 -> 1 像素寬的中心線，量長度
#   3. 每顆積木有沒有穿上 (門檻自動算):
#        繩子穿過正方形積木中心時，中心到積木外面看得到的繩子 = 半弦長
#        (正放 = 邊長/2，繩子走對角線 = 邊長 x 0.71，依積木角度 + 附近繩子方向算)
#        門檻 = 半弦長 + 繩寬 + 0.1 邊長；兩顆貼在一起 (間距 <= 2 倍繩寬) 的改量到「繩子 + 已穿上積木」
#   4. 長度法: (校正時的繩長 L0 - 現在看得到的繩長) / 每顆擋掉的長度 = 繩上積木數 (只印出來對照，不計分)
# 校正值 (繩長、繩寬、積木邊長...) 由 plan_ch1_t1.py 產生:
#   設定頁校正 -> 分析伺服器存成 plans/<machine_id>.json (MacWeb 分析時帶 PDMS2_MACHINE_ID，讀那台現場機自己的)
#   直接跑 plan_ch1_t1.py -> plan_ch1_t1.json (找不到 plans/<machine_id>.json 時用這個)
CONF = 0.85              # 積木 YOLO 信心值
LINE_CONF = 0.5         # 繩子 YOLO 信心值
BASE_DIR = Path(__file__).resolve().parent
PLAN_PATH = BASE_DIR / "plan_ch1_t1.json"
PLAN_DIR = BASE_DIR / "plans"
ENV_PATH = BASE_DIR.parent / ".env"

# ================== 初始化模型 ==================
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[DEBUG] 目前使用設備: {device}", flush=True)

# 1. YOLO 模型 (俯視圖，僅用於提供 Box)
MODEL_PATH = BASE_DIR.parent / "models" / "cube_top.pt"
try:
    print(f"[DEBUG] 開始加載 YOLO 模型: {MODEL_PATH}", flush=True)
    yolo_model = YOLO(str(MODEL_PATH))
    print("[DEBUG] YOLO 模型加載完成", flush=True)
except Exception as e:
    print(f"[ERROR] YOLO 模型加載失敗：{e}", flush=True)
    sys.exit(-1)

# 2. 繩子 seg 模型 (提供繩子 Box 給 SAM2)
LINE_MODEL_PATH = BASE_DIR.parent / "models" / "line.pt"
try:
    print(f"[DEBUG] 開始加載繩子模型: {LINE_MODEL_PATH}", flush=True)
    line_model = YOLO(str(LINE_MODEL_PATH))
    print("[DEBUG] 繩子模型加載完成", flush=True)
except Exception as e:
    print(f"[ERROR] 繩子模型加載失敗：{e}", flush=True)
    sys.exit(-1)

# 3. SAM2 模型 (ultralytics，用於精細分割)
SAM_CHECKPOINT = BASE_DIR.parent / "models" / "sam2_b.pt"
try:
    print(f"[DEBUG] 開始加載 SAM2 模型: {SAM_CHECKPOINT}", flush=True)
    sam_model = SAM(str(SAM_CHECKPOINT))
    print("[DEBUG] SAM2 模型加載完成", flush=True)
except Exception as e:
    print(f"[ERROR] SAM2 模型加載失敗：{e}", flush=True)
    sys.exit(-1)

def return_score(score):
    sys.exit(int(score))

# ================== 校正檔 ==================

def _machine_id():
    """遠端分析時 MacWeb 會帶入現場機的 ID；本機執行就讀 .env 的 MACHINE_ID"""
    machine_id = os.environ.get("PDMS2_MACHINE_ID", "").strip()
    if machine_id:
        return machine_id
    try:
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("MACHINE_ID="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""

def plan_path():
    """優先用這台現場機在設定頁做的校正 plans/<machine_id>.json，沒有才用 plan_ch1_t1.json"""
    machine_id = _machine_id()
    if machine_id and all(ch.isalnum() or ch == "-" for ch in machine_id):
        path = PLAN_DIR / f"{machine_id}.json"
        if path.exists():
            return path
    return PLAN_PATH

def load_plan(path=None):
    """讀校正檔；沒有就回傳 {} (改用當張照片的繩寬，長度法跳過)"""
    path = path or plan_path()
    print(f"[DEBUG] 校正檔: {path}", flush=True)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[WARN] 找不到校正檔 {path}，請先在設定頁做 ch1-t1 校正；繩寬改用這張照片量的，長度法跳過", flush=True)
    except json.JSONDecodeError as e:
        print(f"[WARN] 校正檔格式錯誤 {path}: {e}", flush=True)
    return {}

# ================== 偵測 ==================

def get_sam_masks(frame, boxes):
    """ 根據 YOLO 的 boxes 使用 SAM2 生成高品質 Mask，回傳 list[bool HxW] """
    if len(boxes) == 0: return []
    bboxes = np.asarray(boxes, dtype=float)
    results = sam_model.predict(source=frame, bboxes=bboxes, device=device, verbose=False)
    sam_masks = []
    if len(results) > 0 and results[0].masks is not None:
        h, w = frame.shape[:2]
        for m in results[0].masks.data.cpu().numpy():
            mask = m > 0.5
            if mask.shape[:2] != (h, w):
                mask = cv2.resize(mask.astype(np.uint8), (w, h),
                                  interpolation=cv2.INTER_NEAREST).astype(bool)
            sam_masks.append(mask)
    return sam_masks

def detect_boxes(model, frame, conf):
    results = model.predict(source=frame, conf=conf, device=device, verbose=False)
    boxes = []
    for r in results:
        if r.boxes is None: continue
        for box in r.boxes:
            if int(box.cls[0]) == 0:
                boxes.append(box.xyxy[0].cpu().numpy())
    return boxes

def analyze(frame, conf=CONF, line_conf=LINE_CONF):
    """回傳 (積木 boxes, 積木 masks, 看得到的繩子 mask)"""
    cube_boxes = detect_boxes(yolo_model, frame, conf)
    cube_masks = get_sam_masks(frame, cube_boxes)

    # 繩子常被積木切成好幾段，每段的 box 丟給 SAM2，全部合成一張遮罩
    rope = np.zeros(frame.shape[:2], bool)
    for m in get_sam_masks(frame, detect_boxes(line_model, frame, line_conf)):
        rope |= m
    # 看得到的繩子 = 繩子遮罩扣掉積木遮罩 (避免 SAM 把積木也切進繩子)
    for m in cube_masks:
        rope &= ~m
    return cube_boxes, cube_masks, rope

# ================== 繩子中心線 (mask -> 線) ==================

def clean_rope(rope, min_px=20):
    """去掉毛邊和小雜點，中心線才不會長出一堆小分支"""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    m = cv2.morphologyEx(rope.astype(np.uint8), cv2.MORPH_CLOSE, k)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_px
    return keep[lab]

def thin(mask):
    """Zhang-Suen 細線化 (只用 numpy，不需要 scikit-image)"""
    img = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            p2, p3, p4 = img[:-2, 1:-1], img[:-2, 2:], img[1:-1, 2:]
            p5, p6, p7 = img[2:, 2:], img[2:, 1:-1], img[2:, :-2]
            p8, p9 = img[1:-1, :-2], img[:-2, :-2]
            nbrs = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            b = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9                                # 鄰居數
            a =sum(((nbrs[i] == 0) & (nbrs[i + 1] == 1)).astype(np.uint8) for i in range(8))
            if step == 0:
                c = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                c = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            rm = (img[1:-1, 1:-1] == 1) & (b >= 2) & (b <= 6) & (a == 1) & c
            if rm.any():
                img[1:-1, 1:-1][rm] = 0
                changed = True
        if not changed:
            return img[1:-1, 1:-1].astype(bool)

_NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

def prune_spurs(skel, max_spur):
    """剪掉中心線上 <= max_spur 像素的小分支 (端點一路走到分岔點的那段)"""
    sk = skel.copy()
    h, w = sk.shape
    nb = cv2.filter2D(sk.astype(np.uint8), -1, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT) - sk
    for y, x in zip(*np.where(sk & (nb == 1))):
        path, prev, cur = [(y, x)], None, (y, x)
        while len(path) <= max_spur:
            nxt = [(cur[0] + dy, cur[1] + dx) for dy, dx in _NB
                   if 0 <= cur[0] + dy < h and 0 <= cur[1] + dx < w
                   and sk[cur[0] + dy, cur[1] + dx] and (cur[0] + dy, cur[1] + dx) != prev
                   and (cur[0] + dy, cur[1] + dx) not in path]
            if len(nxt) != 1 or nb[nxt[0]] >= 3:
                # 走到分岔點 -> 這段是小分支，剪掉；走到底 (沒鄰居) -> 是一整段繩子，保留
                if nxt and (len(nxt) > 1 or nb[nxt[0]] >= 3):
                    for py, px in path:
                        sk[py, px] = False
                break
            prev, cur = cur, nxt[0]
            path.append(cur)
    return sk

def centerline(rope):
    """繩子 mask -> 1 像素寬的中心線"""
    m = clean_rope(rope)
    if not m.any():
        return m
    skel = thin(m)
    width = m.sum() / max(skel.sum(), 1)
    return prune_spurs(skel, max_spur=int(round(width * 1.5)) + 2)

def line_length(skel):
    """中心線長度 (像素)：外輪廓繞線一圈 = 線長 x 2，斜線也算得準"""
    if not skel.any():
        return 0.0
    cnts, _ = cv2.findContours(skel.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return sum(cv2.arcLength(c, True) for c in cnts) / 2

def rope_measure(rope):
    """回傳 dict(area, length, width, segs, skel)"""
    skel = centerline(rope)
    area = int(rope.sum())
    length = line_length(skel)
    segs = cv2.connectedComponents(skel.astype(np.uint8), connectivity=8)[0] - 1
    return {"area": area, "length": length, "width": area / length if length else 0.0,
            "segs": segs, "skel": skel}

def block_side(cube_masks):
    return float(np.median([np.sqrt(m.sum()) for m in cube_masks])) if cube_masks else 0.0

# ================== 每顆積木有沒有穿上 (門檻自動算) ==================

def dist_map(target):
    if target.any():
        return cv2.distanceTransform((~target).astype(np.uint8), cv2.DIST_L2, 5)
    return np.full(target.shape, np.inf, np.float32)

def block_geom(mask):
    """回傳 (中心 (y, x), 邊長, 旋轉角度 deg)；遮罩是空的回傳 None"""
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    angle = cv2.minAreaRect(max(cnts, key=cv2.contourArea))[2]
    return (int(round(ys.mean())), int(round(xs.mean()))), float(np.sqrt(len(xs))), angle

def rope_direction(skel_pts, center, radius):
    """積木附近 (半徑 radius 內) 繩子中心線的方向 (dy, dx)；附近沒有繩子回傳 None"""
    if len(skel_pts) == 0:
        return None
    d2 = ((skel_pts - np.array(center)) ** 2).sum(1)
    near = skel_pts[d2 <= radius * radius].astype(np.float32)
    if len(near) < 5:
        return None
    _, _, vt = np.linalg.svd(near - near.mean(0), full_matrices=False)
    return vt[0]

def half_chord(side, angle_deg, direction):
    """繩子沿 direction 穿過正方形中心時，中心到積木邊緣的距離。垂直邊 = side/2，對角線 = side*0.71"""
    if direction is None:
        return side * 0.6
    theta = np.arctan2(direction[0], direction[1]) - np.radians(angle_deg)
    return side / 2 / max(abs(np.cos(theta)), abs(np.sin(theta)), 1e-6)

def judge_strung(cube_masks, rope, skel, rope_width, chain=True):
    """
    每顆積木: 中心到看得到的繩子距離 <= 半弦長 + 繩寬 + 0.1 邊長 就算穿上。
    chain: 跟已穿上積木貼在一起 (間距 <= 2 倍繩寬) 的積木，改量到「繩子 + 已穿上積木」，
           方向用「旁邊那顆的中心 -> 這顆的中心」，一路傳到沒有新的為止。
    回傳 (is_correct list, 每顆的 (中心 (x, y), 距離, 門檻, 判定方式 "rope"/"chain"/""))
    """
    n = len(cube_masks)
    slack = lambda side: max(rope_width, 3.0) + 0.1 * side   # 遮罩誤差的寬鬆量
    touch_px = 2 * rope_width + 2
    skel_pts = np.argwhere(skel)
    dist = dist_map(rope)
    geoms = [block_geom(m) for m in cube_masks]
    is_correct, infos = [], []
    for g in geoms:
        if g is None:
            is_correct.append(False)
            infos.append(((0, 0), np.inf, 0.0, ""))
            continue
        c, side, ang = g
        thr = half_chord(side, ang, rope_direction(skel_pts, c, side)) + slack(side)
        d = float(dist[c])
        ok = d <= thr
        is_correct.append(ok)
        infos.append(((c[1], c[0]), d, thr, "rope" if ok else ""))

    while chain:
        done = [j for j in range(n) if is_correct[j]]
        if not done:
            break
        strung = np.zeros(rope.shape, bool)
        for j in done:
            strung |= cube_masks[j]
        dist_rs = dist_map(rope | strung)
        changed = False
        for i in range(n):
            if is_correct[i] or geoms[i] is None:
                continue
            # 找貼最近的已穿上積木
            gap, j = min((float(dist_map(cube_masks[j])[cube_masks[i]].min()), j) for j in done)
            if gap > touch_px:
                continue
            c, side, ang = geoms[i]
            cj = geoms[j][0]
            direction = np.array([c[0] - cj[0], c[1] - cj[1]], np.float32)
            direction /= max(np.linalg.norm(direction), 1e-6)
            thr = half_chord(side, ang, direction) + slack(side)
            d = float(dist_rs[c])
            if d <= thr:
                is_correct[i] = True
                infos[i] = ((c[1], c[0]), d, thr, "chain")
                changed = True
        if not changed:
            break
    return is_correct, infos

# ================== 長度法 (對照用) ==================

def length_count(plan, m, cube_masks):
    """(L0 - L) / l，回傳 (估計顆數 float, 顯示文字)；沒校正回傳 (None, "")"""
    if not plan.get("rope_len"):
        return None, ""
    l = plan.get("per_block_len") or ((plan.get("block_side") or block_side(cube_masks)) + plan.get("rope_width", 0.0))
    if not l:
        return None, ""
    k = max(plan["rope_len"] - m["length"], 0.0) / l
    tol = float(np.clip(plan.get("len_spread", 0.0) / l + 0.15, 0.25, 0.45))
    if k < tol:
        txt = "0"
    elif abs(k - round(k)) <= tol:
        txt = str(int(round(k)))
    else:
        txt = f"{int(np.floor(k))}~{int(np.floor(k)) + 1}?"
    return k, txt

# ================== 畫圖 ==================

GREEN, YELLOW, RED = (0, 255, 0), (0, 255, 255), (0, 0, 255)

def draw_block_markers(frame, cube_masks, is_correct, infos, skel):
    vis = frame.copy()
    overlay = vis.copy()
    for m, ok in zip(cube_masks, is_correct):
        overlay[m] = GREEN if ok else YELLOW   # 穿在繩上綠色，沒穿黃色
    vis = cv2.addWeighted(overlay, 0.45, vis, 0.55, 0)

    line = cv2.dilate(skel.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    vis[line] = RED                            # 繩子畫成紅色中心線

    for ok, (center, d, thr, how) in zip(is_correct, infos):
        c = tuple(int(v) for v in center)
        color = GREEN if ok else YELLOW
        cv2.circle(vis, c, 5, color, -1)
        txt = "inf" if np.isinf(d) else f"{d:.0f}/{thr:.0f}"   # 距離 / 門檻 (像素)
        if how == "chain":
            txt += " chain"
        cv2.putText(vis, txt, (c[0] + 8, c[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
        cv2.putText(vis, txt, (c[0] + 8, c[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    return vis

# ================== 主評分邏輯 ==================
def score_from_image(img_path, conf=CONF):
    img = cv2.imread(img_path)
    if img is None: raise ValueError(f"讀取圖片失敗：{img_path}")

    plan = load_plan()
    if plan.get("image_size") and list(plan["image_size"]) != [img.shape[1], img.shape[0]]:
        print(f"[WARN] 照片大小 {img.shape[1]}x{img.shape[0]} 跟校正時 {plan['image_size']} 不一樣，"
              f"ROI 或解析度可能改過，請在設定頁重新做 ch1-t1 校正", flush=True)

    cube_boxes, masks, rope = analyze(img, conf=conf)
    m = rope_measure(rope)
    rope_width = plan.get("rope_width") or m["width"]
    is_correct, infos = judge_strung(masks, rope, m["skel"], rope_width)
    correct_num = sum(is_correct)

    k, k_txt = length_count(plan, m, masks)
    if k is not None:
        print(f"[DEBUG] 長度法 (對照): L0={plan['rope_len']:.0f} L={m['length']:.0f} -> 約 {k:.2f} 顆 ({k_txt})", flush=True)
    if plan.get("n_blocks") and len(masks) != plan["n_blocks"]:
        print(f"[WARN] 偵測到 {len(masks)} 顆積木，校正時是 {plan['n_blocks']} 顆", flush=True)
    print(f"[DEBUG] 積木 {len(masks)} 顆，穿在繩上 {correct_num} 顆", flush=True)

    result_img = draw_block_markers(img, masks, is_correct, infos, m["skel"])

    # 計分邏輯：2個是基礎，多1個加1分
    correct_num_for_score = correct_num
    if correct_num_for_score >= 2:
        correct_num_for_score -= 2

    if correct_num_for_score == 4:
        score = 2
    elif correct_num_for_score == 3:
        score = 1
    else:
        score = 0

    return score, correct_num, result_img

# ================== Main ==================
# ================== 測試模式輔助 ==================
def _show_result(title, img, save_path=None):
    """把結果圖顯示出來（太大就自動縮小），順便存一份檔案。"""
    if img is None:
        print(f"[TEST] {title}：沒有結果圖", flush=True)
        return
    if save_path:
        cv2.imwrite(save_path, img)
        print(f"[TEST] 結果已存到：{save_path}", flush=True)
    h, w = img.shape[:2]
    scale = min(1.0, 1280 / max(w, 1), 720 / max(h, 1))
    view = cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1.0 else img
    try:
        cv2.imshow(title, view)
        print("[TEST] 按任意鍵繼續／關閉視窗...", flush=True)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except cv2.error as e:
        print(f"[TEST] 這個環境無法開視窗（{e}），請直接看存檔。", flush=True)


def _result_path(src_path):
    base, ext = os.path.splitext(src_path)
    return f"{base}_result{ext or '.jpg'}"


if __name__ == "__main__":
    print("[DEBUG] ch1-t1 main.py 開始執行", flush=True)
    # ===== 測試模式：python main.py --test <圖片路徑> =====
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "-t"):
        if len(sys.argv) < 3:
            print("用法：python main.py --test <圖片路徑>", flush=True)
            sys.exit(-1)
        test_path = sys.argv[2]
        print(f"[TEST] 分析圖片：{test_path}", flush=True)
        score, num, result_img = score_from_image(test_path)
        print(f"[TEST] score={score}, num={num}", flush=True)
        _show_result(f"ch1-t1  score={score}  num={num}", result_img, _result_path(test_path))
        sys.exit(0)


    if len(sys.argv) > 2:
        uid, img_id = sys.argv[1], sys.argv[2]
        image_path = os.path.join("kid", uid, f"{img_id}.jpg")
        save_path = os.path.join("kid", uid, f"{img_id}_result.jpg")
        print(f"[DEBUG] 圖片路徑：{image_path}", flush=True)
    else:
        print("請提供 uid 和 img_id 參數", flush=True)
        sys.exit(-1)

    try:
        print("[DEBUG] 開始分析圖片...", flush=True)
        score, num, result_img = score_from_image(image_path)
        print(f"[DEBUG] 分析完成，score={score}, num={num}", flush=True)

        cv2.imwrite(save_path, result_img)
        print(f"[DEBUG] 儲存結果成功: {save_path}", flush=True)

        print("score =", score)
        print("num =", num)
        return_score(score)
    except Exception as e:
        print(f"[ERROR] 執行過程中出錯：{e}", flush=True)
        return_score(-1)
