"""
ch1-t1 拍照偵測：開鏡頭預覽，按 c 拍照分析，cube_top.pt 找積木、line.pt 找繩子，一律用 SAM2 精細分割。
綠色=穿在繩上的積木  黃色=沒穿在繩上的積木  紅色線=繩子中心線。

[每顆積木有沒有穿上] 門檻全部自動算，不用調:
    繩子穿過正方形積木中心時，中心到「積木外面看得到的繩子」= 半條弦長，
    積木正放 (繩子垂直邊) 是 邊長/2，斜 45 度 (繩子走對角線) 是 邊長 x 0.71。
    所以每顆積木依它自己的 邊長、旋轉角度、附近繩子的方向 算半弦長，
    門檻 = 半弦長 + 繩寬 + 0.1 邊長 (遮罩誤差的寬鬆量)，中心到繩子距離 <= 門檻 就算穿上。
    兩顆貼在一起 (間距 <= 2 倍繩寬) 時中間的繩子被蓋住，
    貼著已穿上積木的那顆改量到「繩子 + 已穿上積木」(標 chain)，可以一路傳下去。

[長度法] 繩子 mask 先變成 1 像素寬的中心線，用「被擋掉的長度」推算有幾顆積木穿在繩上:
    在繩上積木數 ≈ (繩子原始長度 L0 - 現在看得到的長度 L) / 每顆積木擋掉的長度 l
    1. b: 一開始先放「完整的繩子 + 6 顆積木 (放旁邊、不要穿、不要壓到繩子)」按 b，自動算:
          繩子原始長度 L0 / 面積 A0 / 繩寬、積木邊長、積木數、長度抖動 (連拍幾張取中位數)
          每顆擋掉的長度先估 l = 積木邊長 + 繩寬
    2. k: (選做) 把幾顆積木穿在繩上、旁邊不要放其他積木，按 k，用實際量到的 l 取代估計值
    3. c: 之後每次拍照都會算出長度法 / 面積法的積木數
    寬鬆值依 b 量到的長度抖動自動決定 (0.25~0.45 顆): 估計 2.8 顆 -> 3；卡在中間 -> "2~3?"
    校正值存在 capture/rope_calib.json ("sam" 那一組)。鏡頭高度、解析度、繩子換了都要重新按 b。

用法:
    python fix_ch1_1.py                # 預設鏡頭 0
    python fix_ch1_1.py --cam 1        # 鏡頭 1

按鍵:  c: 拍照分析   b: 校正 (完整繩子 + 6 顆積木)   k: 校正每顆積木擋住的長度 (選做)
       r: 設定ROI   x: 清除ROI   q/ESC: 離開
ROI 與 take.py / main_11.py 共用 capture/roi.json，有設 ROI 就只分析 ROI 裡面。
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch

_original_torch_load = torch.load
def safe_load(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _original_torch_load(*args, **kwargs)
torch.load = safe_load

from ultralytics import YOLO, SAM
from skimage.morphology import skeletonize

from take import select_roi, load_roi, save_roi

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR.parent / "PDMS2_web" / "models"
CUBE_MODEL = MODEL_DIR / "cube_top.pt"
LINE_MODEL = MODEL_DIR / "line.pt"
SAM_MODEL = MODEL_DIR / "sam2_b.pt"

device = "cuda" if torch.cuda.is_available() else "cpu"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--cam", type=int, default=0, help="鏡頭編號")
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--conf", type=float, default=0.8, help="積木信心值")
    p.add_argument("--line-conf", type=float, default=0.5, help="繩子信心值")
    p.add_argument("--blocks", type=int, default=6, help="按 b 校正時桌上應該有幾顆積木")
    p.add_argument("--no-chain", action="store_true", help="關掉「貼在一起」的判定，只看繩子")
    p.add_argument("--save-dir", default=str(BASE_DIR / "captures"))
    p.add_argument("--roi-file", default=str(BASE_DIR / "capture" / "roi.json"), help="ROI 設定檔")
    p.add_argument("--calib-file", default=str(BASE_DIR / "capture" / "rope_calib.json"), help="校正檔")
    p.add_argument("--calib-frames", type=int, default=3, help="按 b 時連拍幾張取中位數")
    return p.parse_args()


def load_models():
    for p in (CUBE_MODEL, LINE_MODEL, SAM_MODEL):
        if not p.exists():
            sys.exit(f"[ERROR] 找不到模型: {p}")
    print(f"[INFO] 設備: {device}")
    print(f"[INFO] 載入 {CUBE_MODEL.name} / {LINE_MODEL.name} / {SAM_MODEL.name} ...")
    return YOLO(str(CUBE_MODEL)), YOLO(str(LINE_MODEL)), SAM(str(SAM_MODEL))


def open_camera(idx, w, h):
    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
    cap = cv2.VideoCapture(idx, backend)
    if not cap.isOpened():
        cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        sys.exit(f"[ERROR] 無法開啟攝影機 {idx}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    return cap


def crop(frame, roi):
    if roi:
        x, y, w, h = roi
        return frame[y:y + h, x:x + w]
    return frame


# ================== 偵測 ==================

def to_full_mask(m, h, w):
    mask = m > 0.5
    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST).astype(bool)
    return mask


def yolo_detect(model, frame, conf):
    """回傳 (boxes list[xyxy], masks list[bool HxW] 或 None)"""
    r = model.predict(source=frame, conf=conf, device=device, verbose=False)[0]
    if r.boxes is None or len(r.boxes) == 0:
        return [], None
    keep = (r.boxes.cls.cpu().numpy().astype(int) == 0)
    boxes = r.boxes.xyxy.cpu().numpy()[keep]
    masks = None
    if r.masks is not None:
        h, w = frame.shape[:2]
        masks = [to_full_mask(m, h, w) for m in r.masks.data.cpu().numpy()[keep]]
    return list(boxes), masks


def sam_masks(sam_model, frame, boxes):
    if len(boxes) == 0:
        return []
    r = sam_model.predict(source=frame, bboxes=np.asarray(boxes, float), device=device, verbose=False)
    if not r or r[0].masks is None:
        return []
    h, w = frame.shape[:2]
    return [to_full_mask(m, h, w) for m in r[0].masks.data.cpu().numpy()]


def box_mask(box, h, w):
    m = np.zeros((h, w), bool)
    x1, y1, x2, y2 = [int(round(v)) for v in box]
    m[max(y1, 0):y2, max(x1, 0):x2] = True
    return m


def analyze(frame, models, conf, line_conf, use_sam):
    cube_model, line_model, sam_model = models
    h, w = frame.shape[:2]

    # 積木
    cube_boxes, cube_seg = yolo_detect(cube_model, frame, conf)
    if use_sam:
        cube_masks = sam_masks(sam_model, frame, cube_boxes)
    elif cube_seg is not None:
        cube_masks = cube_seg
    else:
        cube_masks = [box_mask(b, h, w) for b in cube_boxes]

    # 繩子 (常被積木切成好幾段，全部合成一張遮罩)
    line_boxes, line_seg = yolo_detect(line_model, frame, line_conf)
    if use_sam:
        parts = sam_masks(sam_model, frame, line_boxes)
    elif line_seg is not None:
        parts = line_seg
    else:
        parts = [box_mask(b, h, w) for b in line_boxes]
    rope = np.zeros((h, w), bool)
    for m in parts:
        rope |= m

    # 看得到的繩子 = 繩子遮罩扣掉積木遮罩 (避免 SAM 把積木也切進繩子，長度 / 面積才準)
    for m in cube_masks:
        rope &= ~m

    return cube_boxes, cube_masks, line_boxes, rope


def rope_info(rope):
    """繩子位置: 外框 + 兩端點 (沿主軸方向最遠的兩點)"""
    ys, xs = np.where(rope)
    if len(xs) == 0:
        return None
    pts = np.stack([xs, ys], 1).astype(np.float32)
    mean = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - mean, full_matrices=False)
    proj = (pts - mean) @ vt[0]
    p1 = tuple(int(v) for v in pts[proj.argmin()])
    p2 = tuple(int(v) for v in pts[proj.argmax()])
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    return {"bbox": bbox, "ends": (p1, p2), "center": tuple(int(v) for v in mean)}


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
    """
    繩子沿 direction 穿過正方形中心時，中心到積木邊緣的距離 (半弦長)。
    繩子垂直邊 = side/2，走對角線 = side * 0.71。不知道方向就取中間值。
    """
    if direction is None:
        return side * 0.6
    theta = np.arctan2(direction[0], direction[1]) - np.radians(angle_deg)
    return side / 2 / max(abs(np.cos(theta)), abs(np.sin(theta)), 1e-6)


def judge_strung(cube_masks, rope, skel, rope_width, chain=True):
    """
    每顆積木: 中心到看得到的繩子距離 <= 半弦長 + 繩寬 + 0.1 邊長 就算穿上 (半弦長依積木大小、角度、繩子方向)。
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
            gaps = [(float(dist_map(cube_masks[j])[cube_masks[i]].min()), j) for j in done]
            gap, j = min(gaps)
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


# ================== 繩子中心線 (mask -> 線) ==================

def clean_rope(rope, min_px=20):
    """去掉毛邊和小雜點，骨架才不會長出一堆小分支"""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    m = cv2.morphologyEx(rope.astype(np.uint8), cv2.MORPH_CLOSE, k)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_px
    return keep[lab]


_NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def prune_spurs(skel, max_spur):
    """剪掉骨架上 <= max_spur 像素的小分支 (端點一路走到分岔點的那段)"""
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
    skel = skeletonize(m)
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


# ================== 長度法 / 面積法 ==================
# 在繩上積木數 ≈ (原始長度 L0 - 看得到的長度 L) / 每顆擋掉的長度 l
# 每顆擋掉的長度: 按 k 校正，沒校正就估 積木邊長 + 繩寬 (中心線在每段斷口會各縮半個繩寬)

def mode_key(use_sam):
    return "sam" if use_sam else "yolo"


def load_calib(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_calib(path, calib):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(calib, f, indent=2, ensure_ascii=False)


def block_side(cube_masks):
    return float(np.median([np.sqrt(m.sum()) for m in cube_masks])) if cube_masks else 0.0


def per_block(c, cube_masks):
    """回傳 (每顆擋掉的長度, 每顆擋掉的面積, 來源)"""
    if c.get("per_block_len"):
        return c["per_block_len"], c.get("per_block_area"), "calib"
    side = c.get("block_side") or block_side(cube_masks)
    w = c.get("rope_width", 0.0)
    if side and w:
        return side + w, side * w, "est"
    return None, None, None


def auto_tol(c, l):
    """寬鬆值: b 量到的長度抖動換算成幾顆，再多留 0.15，限制在 0.25~0.45"""
    jitter = c.get("len_spread", 0.0) / l if l else 0.0
    return float(np.clip(jitter + 0.15, 0.25, 0.45))


def count_on_rope(c, m, cube_masks):
    """回傳 dict(len_k, area_k, hidden_len, hidden_area, l, a, src, tol)；沒校正回傳 None"""
    if not c.get("rope_len"):
        return None
    l, a, src = per_block(c, cube_masks)
    if not l:
        return None
    hidden_len = max(c["rope_len"] - m["length"], 0.0)
    hidden_area = max(c["rope_area"] - m["area"], 0.0)
    return {"len_k": hidden_len / l, "area_k": hidden_area / a if a else None,
            "hidden_len": hidden_len, "hidden_area": hidden_area, "l": l, "a": a, "src": src,
            "tol": auto_tol(c, l)}


def tol_count(k, tol):
    """
    寬鬆判斷: k 顆 (小數) -> (顆數, 是否確定, 顯示文字)
      離最近整數 <= tol      -> 確定，例 2.8 -> 3
      卡在兩個整數中間       -> 不確定，例 2.5 -> "2~3"，顆數先取四捨五入
      k < tol (含負的雜訊)   -> 0
    """
    if k < tol:
        return 0, True, "0"
    n = int(round(k))
    if abs(k - n) <= tol:
        return n, True, str(n)
    lo = int(np.floor(k))
    return n, False, f"{lo}~{lo + 1}?"


def calibrate_baseline(cap, roi, models, args, use_sam, calib, calib_path):
    """b: 完整繩子 + N 顆積木 (放旁邊不要穿)，連拍幾張取中位數，自動算所有參數"""
    areas, lengths, sides, counts = [], [], [], []
    for i in range(args.calib_frames):
        ok, frame = cap.read()
        if not ok:
            break
        cube_boxes, cube_masks, _, rope = analyze(crop(frame, roi), models, args.conf, args.line_conf, use_sam)
        m = rope_measure(rope)
        on_rope, _ = judge_strung(cube_masks, rope, m["skel"], m["width"], chain=False)
        if any(on_rope):
            print(f"[WARN] 有 {sum(on_rope)} 顆積木壓在繩子上 / 靠太近，繩子長度會被低估，請把積木移開一點")
        print(f"  [{i + 1}/{args.calib_frames}] 積木={len(cube_boxes)}  邊長={block_side(cube_masks):.1f}  "
              f"繩長={m['length']:.0f}  面積={m['area']}  段數={m['segs']}  繩寬={m['width']:.1f}")
        counts.append(len(cube_boxes))
        if cube_masks:
            sides.append(block_side(cube_masks))
        if m["length"]:
            areas.append(m["area"])
            lengths.append(m["length"])
    if not lengths:
        print("[ERROR] 沒偵測到繩子，校正失敗")
        return
    if not sides:
        print("[ERROR] 沒偵測到積木，校正失敗 (請放完整繩子 + 積木)")
        return
    n_blocks = int(np.median(counts))
    if n_blocks != args.blocks:
        print(f"[WARN] 偵測到 {n_blocks} 顆積木，預期 {args.blocks} 顆 (--blocks)")
    L0, A0, side = float(np.median(lengths)), float(np.median(areas)), float(np.median(sides))
    width = A0 / L0
    calib[mode_key(use_sam)] = {
        "rope_len": L0,
        "rope_area": A0,
        "rope_width": width,
        "block_side": side,
        "n_blocks": n_blocks,
        "len_spread": float(max(lengths) - min(lengths)),   # 幾張之間長度抖多少，用來決定寬鬆值
        "per_block_len": None,                  # 原始值變了，k 校正要重做
        "per_block_area": None,
        "frame_size": [int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))],
        "roi": list(roi) if roi else None,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_calib(calib_path, calib)
    c = calib[mode_key(use_sam)]
    l, a, _ = per_block(c, [])
    print(f"[CALIB] SAM2={'ON' if use_sam else 'OFF'}  完成:")
    print(f"        繩子 原始長度 L0={L0:.0f}px (幾張差 {c['len_spread'] / L0 * 100:.1f}%)  "
          f"面積 A0={A0:.0f}  繩寬={width:.1f}px")
    print(f"        積木 {n_blocks} 顆  邊長={side:.1f}px")
    print(f"        每顆擋掉 l≈{l:.0f}px (邊長+繩寬)  a≈{a:.0f}px  寬鬆值={auto_tol(c, l):.2f} 顆")
    print(f"        穿上判斷門檻: 正放 {side * 0.6 + width:.0f}px ~ 斜放 {side * 0.81 + width:.0f}px  "
          f"(半弦長 + 繩寬 + 0.1 邊長)，貼在一起 = 間距 <= {2 * width + 2:.0f}px")


def calibrate_per_block(shot, models, args, use_sam, calib, calib_path):
    """k: 只放穿在繩上的積木，l = (L0 - L) / 積木數，a = (A0 - A) / 積木數"""
    c = calib.get(mode_key(use_sam), {})
    if not c.get("rope_len"):
        print("[ERROR] 請先按 b 校正")
        return
    cube_boxes, cube_masks, _, rope = analyze(shot, models, args.conf, args.line_conf, use_sam)
    n = len(cube_boxes)
    if n == 0:
        print("[ERROR] 沒偵測到積木")
        return
    m = rope_measure(rope)
    hidden_len = c["rope_len"] - m["length"]
    hidden_area = c["rope_area"] - m["area"]
    if hidden_len <= 0:
        print(f"[ERROR] 看得到的繩子長度 ({m['length']:.0f}) 沒有比原始長度 ({c['rope_len']:.0f}) 短，無法校正")
        return
    est_l, est_a, _ = per_block(c, cube_masks)
    c["per_block_len"] = hidden_len / n
    c["per_block_area"] = hidden_area / n if hidden_area > 0 else None
    save_calib(calib_path, calib)
    print(f"[CALIB] {n} 顆積木擋掉 長度 {hidden_len:.0f} / 面積 {hidden_area:.0f} -> "
          f"每顆 l={c['per_block_len']:.0f} (估計 {est_l:.0f})  a={c['per_block_area'] or 0:.0f} (估計 {est_a:.0f})  "
          f"寬鬆值={auto_tol(c, c['per_block_len']):.2f} 顆")


# ================== 畫圖 ==================

GREEN, YELLOW, RED = (0, 255, 0), (0, 255, 255), (0, 0, 255)


def draw(frame, cube_boxes, cube_masks, is_correct, judge_infos, skel, info):
    vis = frame.copy()
    overlay = vis.copy()
    for m, ok in zip(cube_masks, is_correct):
        overlay[m] = GREEN if ok else YELLOW   # 穿在繩上綠色，沒穿黃色
    vis = cv2.addWeighted(overlay, 0.45, vis, 0.55, 0)

    # 繩子畫成紅色中心線
    line = cv2.dilate(skel.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    vis[line] = RED

    # SAM 可能少切幾顆，遮罩和框數量不一定一樣，框只在對得上時跟著上色
    same = len(cube_masks) == len(cube_boxes)
    for i, b in enumerate(cube_boxes):
        color = (GREEN if is_correct[i] else YELLOW) if same else (255, 255, 255)
        x1, y1, x2, y2 = [int(v) for v in b]
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        cv2.putText(vis, str(i + 1), (x1 + 4, y1 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
        cv2.putText(vis, str(i + 1), (x1 + 4, y1 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # 每顆積木中心: 距離/門檻 (像素)
    for ok, (center, d, thr, how) in zip(is_correct, judge_infos):
        c = tuple(int(v) for v in center)
        color = GREEN if ok else YELLOW
        cv2.circle(vis, c, 5, color, -1)
        txt = "inf" if np.isinf(d) else f"{d:.0f}/{thr:.0f}"
        if how == "chain":
            txt += " chain"                    # 靠旁邊穿上的積木判定
        cv2.putText(vis, txt, (c[0] + 8, c[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
        cv2.putText(vis, txt, (c[0] + 8, c[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    if info:
        p1, p2 = info["ends"]
        for p, name in ((p1, "A"), (p2, "B")):
            cv2.circle(vis, p, 9, RED, -1)
            cv2.circle(vis, p, 9, (255, 255, 255), 2)
            cv2.putText(vis, name, (p[0] + 12, p[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
            cv2.putText(vis, name, (p[0] + 12, p[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return vis


def put_status(img, lines):
    for i, txt in enumerate(lines):
        y = 30 + i * 30
        cv2.putText(img, txt, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
        cv2.putText(img, txt, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


def fit(img, max_w=1280):
    s = min(1.0, max_w / img.shape[1])
    return cv2.resize(img, None, fx=s, fy=s) if s < 1.0 else img.copy()


def capture_and_analyze(shot, models, args, use_sam, save_dir, calib):
    """拍一張 -> 分析 -> 存原圖 + 結果圖 -> 開結果視窗"""
    t0 = time.perf_counter()
    try:
        cube_boxes, cube_masks, line_boxes, rope = analyze(shot, models, args.conf, args.line_conf, use_sam)
    except Exception as e:
        print(f"[ERROR] 分析失敗: {e}", flush=True)
        return
    c = calib.get(mode_key(use_sam), {})
    m = rope_measure(rope)
    info = rope_info(m["skel"])   # 座標是 ROI 裡面的座標
    rope_width = c.get("rope_width") or m["width"]
    is_correct, judge_infos = judge_strung(cube_masks, rope, m["skel"], rope_width, chain=not args.no_chain)
    vis = draw(shot, cube_boxes, cube_masks, is_correct, judge_infos, m["skel"], info)
    dt = time.perf_counter() - t0

    n = len(cube_boxes)
    n_ok = int(sum(is_correct))
    total_txt = ""
    if c.get("n_blocks"):
        total_txt = f" / {c['n_blocks']}"
        if n != c["n_blocks"]:
            print(f"[WARN] 偵測到 {n} 顆積木，校正時是 {c['n_blocks']} 顆 (可能有積木沒被偵測到)")

    res = count_on_rope(c, m, cube_masks)
    if res:
        _, _, len_txt = tol_count(res["len_k"], res["tol"])
        area_part = ""
        if res["area_k"] is not None:
            area_part = f"   area={tol_count(res['area_k'], res['tol'])[2]} ({res['area_k']:.2f})"
        count_txt = f"on rope (length) = {len_txt} ({res['len_k']:.2f}  tol={res['tol']:.2f}){area_part}"
        detail_txt = (f"L0={c['rope_len']:.0f} L={m['length']:.0f} hidden={res['hidden_len']:.0f} "
                      f"l={res['l']:.0f}[{res['src']}]  segs={m['segs']}")
    else:
        count_txt = f"rope L={m['length']:.0f} A={m['area']}  (press b to calibrate)"
        detail_txt = f"segs={m['segs']}  width={m['width']:.1f}px"

    print(f"積木 {n} 個 | 穿在繩上 (距離) {n_ok}{total_txt} 個、沒穿 {len(is_correct) - n_ok} 個 | "
          f"{count_txt} | {detail_txt} | SAM2={'ON' if use_sam else 'OFF'} | {dt:.2f}s", flush=True)

    save_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cv2.imwrite(str(save_dir / f"ch1-t1_{stamp}.jpg"), shot)
    cv2.imwrite(str(save_dir / f"ch1-t1_{stamp}_result.jpg"), vis)
    print(f"[INFO] 已存圖: {save_dir / f'ch1-t1_{stamp}_result.jpg'}")

    disp = fit(vis)
    put_status(disp, [
        f"blocks={n}{total_txt}   on rope (dist) = {n_ok}   off = {len(is_correct) - n_ok}   "
        f"SAM2={'ON' if use_sam else 'OFF'}   {dt:.2f}s",
        count_txt,
        detail_txt,
        "green=on rope  yellow=not on rope  red=rope line",
    ])
    cv2.imshow("result", disp)


# ================== 主程式 ==================

def main():
    args = parse_args()
    models = load_models()
    cap = open_camera(args.cam, args.width, args.height)
    print(f"[INFO] 攝影機解析度: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print(f"c: 拍照分析   b: 校正 (完整繩子 + {args.blocks} 顆積木放旁邊)   k: 校正每顆擋住的長度 (選做)   "
          "r: 設定ROI   x: 清除ROI   q/ESC: 離開")

    roi_path = Path(args.roi_file)
    roi = load_roi(roi_path)
    if roi:
        print(f"[INFO] 載入 ROI: x={roi[0]} y={roi[1]} w={roi[2]} h={roi[3]}")

    calib_path = Path(args.calib_file)
    calib = load_calib(calib_path)
    for k, c in calib.items():
        print(f"[INFO] 載入校正 [{k}] L0={c.get('rope_len')}  繩寬={c.get('rope_width')}  "
              f"邊長={c.get('block_side')}  積木={c.get('n_blocks')}  l={c.get('per_block_len')}  ({c.get('time')})")

    save_dir = Path(args.save_dir)
    use_sam = True   # 一律開 SAM2
    if not calib.get(mode_key(use_sam), {}).get("block_side"):
        print(f"[INFO] 還沒校正: 請先放「完整的繩子 + {args.blocks} 顆積木 (放旁邊、不要穿)」，按 b")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("[ERROR] 讀取影像失敗")
            break
        shot = crop(frame, roi)

        # 預覽: 只顯示鏡頭畫面 (有 ROI 就畫框)，不做分析
        preview = frame.copy()
        if roi:
            x, y, w, h = roi
            cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 255), 3)
        c = calib.get(mode_key(use_sam), {})
        if c.get("block_side"):
            calib_txt = f"L0={c['rope_len']:.0f} side={c['block_side']:.0f} blocks={c['n_blocks']}"
        else:
            calib_txt = "NOT CALIBRATED: rope + blocks, press b"
        disp = fit(preview)
        put_status(disp, [
            f"SAM2=ON   ROI={'ON' if roi else 'OFF'}   {calib_txt}",
            "[c] capture [b] calibrate [k] strung blocks [r] ROI [x] clear [q] quit",
        ])
        cv2.imshow("fix_ch1_1", disp)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("c"):
            capture_and_analyze(shot.copy(), models, args, use_sam, save_dir, calib)
        elif key == ord("b"):
            calibrate_baseline(cap, roi, models, args, use_sam, calib, calib_path)
        elif key == ord("k"):
            calibrate_per_block(shot.copy(), models, args, use_sam, calib, calib_path)
        elif key == ord("r"):
            new_roi = select_roi(frame.copy(), 1280)
            if new_roi:
                roi = new_roi
                roi_path.parent.mkdir(parents=True, exist_ok=True)
                save_roi(roi_path, roi)
                print(f"[INFO] 設定 ROI: x={roi[0]} y={roi[1]} w={roi[2]} h={roi[3]}")
            else:
                print("[INFO] 取消設定 ROI")
        elif key == ord("x"):
            roi = None
            if roi_path.exists():
                roi_path.unlink()
            print("[INFO] 已清除 ROI")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
