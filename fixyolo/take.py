"""
take.py - 用攝影機拍照 + YOLO 即時偵測，可設定固定 ROI 範圍

操作方式 (預覽視窗):
    r         : 設定 ROI (用滑鼠框選，ENTER / SPACE 確認，c 取消)
    x         : 清除 ROI (之後拍全畫面)
    d         : 開 / 關圖形偵測 + 形狀分類 (shape 框切下來 -> 黑底白線 binary -> shape_cls.pt)
    y         : 開 / 關 --model 即時偵測
    SPACE     : 拍照 (有 ROI 就只存 ROI 範圍，沒有就存全畫面；存的是原圖，不含偵測框)
    q / ESC   : 離開

即時偵測:
    有 ROI 就只對 ROI 範圍做推論 (跟訓練資料一樣是裁切後的圖)，沒有就對全畫面。
    模型是 detect 畫框、segment 畫遮罩，自動依模型判斷。
    --model 預設 runs/detect/button_tape_cloth_det/weights/best.pt，找不到模型就只拍照。

輸出 (全部在 --out，預設 capture/):
    capture/<prefix>_<時間>.jpg    拍下的照片
    capture/roi.json               目前的 ROI 設定，下次啟動會自動載入

範例:
    python take.py
    python take.py --conf 0.5
    python take.py --model runs/segment/line_dataset_seg/weights/best.pt
    python take.py --no-detect                    # 純拍照
    python take.py --cam 1 --width 1920 --height 1080

看圖模式 (--images，不開攝影機):
    逐張讀資料夾裡的圖，用 segment 模型推論並以遮罩顯示 (預設 ../check_ch2 + paper_seg.pt)
    s: 下一張   a: 上一張   m: 切換 YOLO / SAM2 遮罩 (要加 --sam)   q / ESC: 離開
    d: 開關圖形框 (runs/detect/shape_det/weights/best.pt)，找到圖形就順便分類形狀
       (圖形框切正方形 -> 黑底白線 binary -> ../PDMS2_web/models/shape_cls.pt)
    --sam: 用 YOLO 框當提示丟給 SAM2 (sam2_11b.pt) 重新切遮罩
    python take.py --images
    python take.py --images --sam
    python take.py --images ../check_ch2 --conf 0.3
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = BASE_DIR / "runs" / "detect" / "button_tape_cloth_det" / "weights" / "best.pt"
DEFAULT_IMAGES = BASE_DIR.parent / "check_ch2"
PAPER_SEG_MODEL = BASE_DIR.parent / "PDMS2_web" / "models" / "paper_seg.pt"
SHAPE_MODEL = BASE_DIR / "runs" / "detect" / "shape_det" / "weights" / "best.pt"
SHAPE_PAD = 10  # 圖形框上下左右外擴的 px
SAM_MODEL = BASE_DIR.parent / "PDMS2_web" / "models" / "sam2_b.pt"
CLS_MODEL = BASE_DIR / "runs" / "classify" / "shape_cls_qd" / "weights" / "best.pt"  # Quick, Draw! 預訓練 + 微調 (train_all.py)
OLD_CLS_MODEL = BASE_DIR.parent / "PDMS2_web" / "models" / "shape_cls.pt"  # 舊的，比較用: --cls-model 指定
CLS_PAD = 30 - SHAPE_PAD  # 跟 PDMS2_web/prepare.py 一樣，原始圖形框外擴 30 px 再切正方形
CLS_SIZE = 224
# 小孩畫的圓常凹凸有角，模型會判成 square；凸包圓度 (4πA/P²，正圓 1.0、正方形 0.785) 超過這個值就改判 circle
# check_ch2 + shape_result/square 885 張真的方形都在 0.94 以下
ROUND_THR = 0.94
# 依關卡調整：畫圓那關 (ch2-t1) 以圓為主，門檻放寬；畫方那關 (ch2-t2) 以方為主，不改判
TASK_ROUND_THR = {"ch2-t1": 0.85, "ch2-t2": 0.0}
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def parse_args():
    p = argparse.ArgumentParser(description="拍照 + 固定 ROI + YOLO 即時偵測")
    p.add_argument("--cam", type=int, default=0, help="攝影機編號")
    p.add_argument("--out", default="capture", help="輸出資料夾")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--prefix", default="img", help="檔名前綴")
    p.add_argument("--max-view", type=int, default=1280, help="顯示視窗最大寬度 (不影響存檔解析度)")
    p.add_argument("--model", default=None,
                   help="YOLO 權重 (detect 或 segment)，預設攝影機模式用 button_tape_cloth_det，看圖模式用 paper_seg.pt")
    p.add_argument("--conf", type=float, default=0.5, help="信心門檻")
    p.add_argument("--imgsz", type=int, default=640, help="推論尺寸 (跟訓練一樣)")
    p.add_argument("--device", default=None, help="例: 0 / cpu (預設自動)")
    p.add_argument("--no-detect", action="store_true", help="啟動時不開偵測")
    p.add_argument("--images", nargs="?", const=str(DEFAULT_IMAGES), default=None,
                   help="看圖模式: 逐張推論資料夾裡的圖 (不給路徑就用 ../check_ch2)")
    p.add_argument("--sam", action="store_true", help="看圖模式: 用 YOLO 框當提示跑 SAM2 遮罩")
    p.add_argument("--sam-model", default=str(SAM_MODEL), help="SAM2 權重")
    p.add_argument("--shape-model", default=str(SHAPE_MODEL), help="看圖模式: 圖形偵測權重 (按 d 顯示)")
    p.add_argument("--shape-conf", type=float, default=0.25, help="圖形偵測信心門檻")
    p.add_argument("--cls-model", default=str(CLS_MODEL), help="看圖模式: 形狀分類權重 (按 d 找到圖形後分類)")
    p.add_argument("--round-thr", type=float, default=ROUND_THR,
                   help="判成 square 但圓度超過這個值就改判 circle (0 = 關掉)；ch2-t1 / ch2-t2 另有門檻 (TASK_ROUND_THR)")
    p.add_argument("--task", default="auto",
                   help="關卡 (例 ch2-t1)，決定圓度門檻；auto = 從檔名抓 (攝影機模式抓不到就用 --round-thr)")
    args = p.parse_args()
    if args.model is None:
        args.model = str(PAPER_SEG_MODEL if args.images else DEFAULT_MODEL)
    return args


def open_camera(idx, w, h):
    # Windows 上 DSHOW 開啟較快
    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
    cap = cv2.VideoCapture(idx, backend)
    if not cap.isOpened():
        cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        sys.exit(f"無法開啟攝影機 {idx}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    return cap


def load_model(path):
    if not os.path.exists(path):
        print(f"[WARN] 找不到模型 {path}，只能拍照")
        return None
    from ultralytics import YOLO

    model = YOLO(path)
    print(f"載入模型: {path} (task={model.task}, classes={list(model.names.values())})")
    return model


def detect(model, img, args):
    """對 img 推論，回傳 (畫好結果的 img, 各類別數量 Counter)"""
    r = model.predict(img, conf=args.conf, imgsz=args.imgsz, device=args.device, verbose=False)[0]
    counts = Counter(r.names[int(c)] for c in r.boxes.cls) if r.boxes is not None else Counter()
    return r.plot(line_width=2), counts


def draw_masks(img, polys, labels, color=(0, 255, 0), alpha=0.45):
    """把遮罩多邊形用半透明 + 輪廓畫在 img 上"""
    if not polys:
        return img.copy()
    overlay = img.copy()
    for poly in polys:  # 一次丟多個多邊形，重疊的地方會被挖空，所以逐個畫
        cv2.fillPoly(overlay, [poly], color)
    out = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)
    cv2.polylines(out, polys, True, color, 2)
    for poly, label in zip(polys, labels):
        x, y = poly.min(axis=0)
        cv2.putText(out, label, (int(x), max(int(y) - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    return out


def mask_polys(r):
    if r is None or r.masks is None:
        return []
    return [p.astype(np.int32) for p in r.masks.xy if len(p) >= 3]


def shape_preds(shape_model, img, scale, args):
    """把 img 縮小 scale 倍貼在黑底中央再偵測 (畫太大的圖形縮小後才不會被切成兩半)，
    回傳換回原圖座標的 [(x1, y1, x2, y2, conf), ...]"""
    H, W = img.shape[:2]
    if scale < 1.0:
        sw, sh = int(W * scale), int(H * scale)
        ox, oy = (W - sw) // 2, (H - sh) // 2
        src = np.zeros_like(img)
        src[oy:oy + sh, ox:ox + sw] = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)
    else:
        ox = oy = 0
        src = img
    r = shape_model.predict(src, conf=args.shape_conf, imgsz=args.imgsz, device=args.device, verbose=False)[0]
    out = []
    for (x1, y1, x2, y2), cf in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist()):
        x1, x2 = ((v - ox) / scale for v in (x1, x2))
        y1, y2 = ((v - oy) / scale for v in (y1, y2))
        out.append((int(x1), int(y1), int(x2), int(y2), cf))
    return out


def find_shapes(shape_model, img, paper_polys, args):
    """多尺度找圖形，只留大部分在紙上、信心夠高的框，合併重複的框，回傳全部 (面積大到小)。
    先用原尺寸 + 縮 0.6 倍，都沒有再試 0.4 倍 (太小的圖形縮到 0.4 會不見，所以只當備案)。
    每個框四周各外擴 SHAPE_PAD px。回傳 [(x1, y1, x2, y2, conf), ...]，沒有就是 []"""
    H, W = img.shape[:2]
    paper = np.zeros((H, W), np.uint8)
    for poly in paper_polys:
        cv2.fillPoly(paper, [poly], 1)

    def on_paper(b):
        # 框至少 80% 在紙上 (壓在紙邊的手會超出紙外)；沒找到紙就不過濾
        if not paper_polys:
            return True
        x1, y1, x2, y2 = b[:4]
        area = max(1, (x2 - x1) * (y2 - y1))
        return paper[max(0, y1):min(H, y2), max(0, x1):min(W, x2)].sum() >= 0.8 * area

    def area(b):
        return max(0, b[2] - b[0]) * max(0, b[3] - b[1])

    def overlap(a, b):
        # 交集 / 較小框面積：不同尺度框到同一個圖形、或大框裡的半個框都會接近 1
        iw = min(a[2], b[2]) - max(a[0], b[0])
        ih = min(a[3], b[3]) - max(a[1], b[1])
        return 0.0 if iw <= 0 or ih <= 0 else iw * ih / max(1, min(area(a), area(b)))

    for scales in ((1.0, 0.6), (0.4,)):
        cand = [b for sc in scales for b in shape_preds(shape_model, img, sc, args) if on_paper(b)]
        if cand:
            # 信心太低的大框常是手或半個框，只留信心 >= 最高分 * 0.75 的框
            top = max(b[4] for b in cand)
            cand = [b for b in cand if b[4] >= 0.75 * top]
            # 從大框開始留，跟已留的框重疊太多就當作同一個圖形丟掉
            kept = []
            for b in sorted(cand, key=area, reverse=True):
                if all(overlap(b, k) < 0.6 for k in kept):
                    kept.append(b)
            # 框上下左右各外擴 SHAPE_PAD px (不超出圖片)
            return [(max(0, x1 - SHAPE_PAD), max(0, y1 - SHAPE_PAD),
                     min(W, x2 + SHAPE_PAD), min(H, y2 + SHAPE_PAD), cf) for x1, y1, x2, y2, cf in kept]
    return []


def find_shape(shape_model, img, paper_polys, args):
    """find_shapes 裡面積最大的那個，回傳 (x1, y1, x2, y2, conf) 或 None"""
    shapes = find_shapes(shape_model, img, paper_polys, args)
    return shapes[0] if shapes else None


def roundness(binary):
    """筆畫外輪廓凸包的圓度 4πA/P²：正圓 1.0、正方形 0.785、越扁越尖越小"""
    m = cv2.morphologyEx((binary > 127).astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return 0.0
    hull = cv2.convexHull(max(cnts, key=cv2.contourArea))
    p = cv2.arcLength(hull, True)
    return 4 * np.pi * cv2.contourArea(hull) / (p * p) if p else 0.0


def task_of(name, args):
    """關卡名稱 (小寫，例 ch2-t1)：--task 有指定就用它，不然從檔名抓 Ch2-t1 這種字樣，抓不到回傳 None"""
    if getattr(args, "task", "auto") != "auto":
        return args.task.lower()
    m = re.search(r"ch\d+-t\d+", str(name), re.IGNORECASE)
    return m.group(0).lower() if m else None


def round_thr_for(task, args):
    """這個關卡的圓度改判門檻 (0 = 不改判)"""
    return TASK_ROUND_THR.get(task, getattr(args, "round_thr", ROUND_THR))


def classify_shape(cls_model, img, shp, args, thr=None):
    """跟 PDMS2_web/prepare.py 同流程: 圖形框切正方形 -> 黑底白線 binary(224) -> 分類。
    模型判 square 但圓度 > thr 就改判 circle (thr 不給就用 args.round_thr；依關卡用 round_thr_for 算)。
    回傳 (類別, 信心, binary 224 灰階圖, 備註, 各類機率 {類別: 機率})
    備註只有被圓度改判時才有字 (例 "round 0.95, model square 0.96")，這時信心欄放的是圓度；各類機率永遠是模型原始輸出"""
    sys.path.insert(0, str(BASE_DIR.parent / "PDMS2_web"))
    from prepare import crop_square, to_binary

    x1, y1, x2, y2 = shp[:4]
    _, (cx1, cy1, cx2, cy2) = crop_square(img, (x1, y1, x2, y2), CLS_PAD)
    # 正方形會切到框外的桌緣 / 紙邊，to_binary 只留最大塊會選到它們；
    # 所以只取框內，再用框邊的像素往外延伸補成同一個正方形 (不會多出邊線)
    x1, y1 = max(x1, cx1), max(y1, cy1)
    x2, y2 = min(x2, cx2), min(y2, cy2)
    crop = cv2.copyMakeBorder(img[y1:y2, x1:x2], y1 - cy1, cy2 - y2, x1 - cx1, cx2 - x2,
                              cv2.BORDER_REPLICATE)
    binary = cv2.resize(to_binary(crop), (CLS_SIZE, CLS_SIZE), interpolation=cv2.INTER_AREA)
    r = cls_model.predict(cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR), imgsz=CLS_SIZE,
                          device=args.device, verbose=False)[0]
    i = int(r.probs.top1)
    label, conf = r.names[i], float(r.probs.top1conf)
    probs = {r.names[k]: float(p) for k, p in enumerate(r.probs.data.tolist())}
    if thr is None:
        thr = getattr(args, "round_thr", ROUND_THR)
    if label == "square" and thr > 0:
        rd = roundness(binary)
        if rd > thr:
            # 改判時信心欄放圓度 (模型給 circle 的機率通常很低，放那個反而誤導)
            return "circle", rd, binary, f"round {rd:.2f}, model square {conf:.2f}", probs
    return label, conf, binary, "", probs


def fmt_probs(probs):
    """{類別: 機率} -> "circle 0.03  cross 0.00  other 0.01  square 0.96" """
    return "  ".join(f"{k} {v:.2f}" for k, v in probs.items())


def load_shape_models(args):
    """載入圖形偵測 + 形狀分類模型，找不到就回傳 None"""
    from ultralytics import YOLO

    shape_model = cls_model = None
    if os.path.exists(args.shape_model):
        shape_model = YOLO(args.shape_model)
        print(f"載入圖形偵測: {args.shape_model}")
    else:
        print(f"[WARN] 找不到圖形偵測權重 {args.shape_model}，d 無作用")
    if shape_model is not None and os.path.exists(args.cls_model):
        cls_model = YOLO(args.cls_model)
        print(f"載入形狀分類: {args.cls_model} (classes={list(cls_model.names.values())})")
    elif shape_model is not None:
        print(f"[WARN] 找不到形狀分類權重 {args.cls_model}，只畫圖形框不分類")
    return shape_model, cls_model


def draw_shape_cls(view, shp, cls):
    """在 view 上畫圖形框 + 分類結果，右上角貼 cls 看到的 binary 圖。shp/cls 為 None 或 False 就不畫"""
    if not shp:
        return
    x1, y1, x2, y2, cf = shp
    txt = f"{cls[0]}{'*' if cls[3] else ''} {cls[1]:.2f}  (det {cf:.2f})" if cls else f"shape {cf:.2f}"
    cv2.rectangle(view, (x1, y1), (x2, y2), (0, 0, 255), 2)
    cv2.putText(view, txt, (x1, max(y1 - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)


def paste_binary(view, cls):
    """右上角貼分類器實際看到的 binary 224 圖，下面列出各類機率 (最高的標黃)"""
    if not cls:
        return
    label, cf, binary, _, probs = cls
    h, w = view.shape[:2]
    if h > CLS_SIZE + 50 + 22 * len(probs) and w > CLS_SIZE + 10:
        x0 = w - CLS_SIZE - 10
        view[40:40 + CLS_SIZE, x0:w - 10] = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(view, (x0, 40), (w - 10, 40 + CLS_SIZE), (255, 0, 255), 2)
        cv2.putText(view, f"{label} {cf:.2f}", (x0, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
        top = max(probs, key=probs.get)
        for j, (k, v) in enumerate(probs.items()):
            y = 40 + CLS_SIZE + 22 * (j + 1)
            cv2.rectangle(view, (x0, y - 16), (w - 10, y + 5), (0, 0, 0), -1)
            cv2.rectangle(view, (x0 + 80, y - 12), (x0 + 80 + int(v * (CLS_SIZE - 140)), y + 2), (255, 0, 255), -1)
            cv2.putText(view, f"{k}", (x0 + 4, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 255, 255) if k == top else (255, 255, 255), 1)
            cv2.putText(view, f"{v:.2f}", (w - 52, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 255, 255) if k == top else (255, 255, 255), 1)


def browse_images(model, args):
    """看圖模式: s 下一張、a 上一張、m 切換 YOLO/SAM2、q/ESC 離開"""
    if model is None:
        sys.exit("看圖模式需要模型")
    folder = Path(args.images)
    files = sorted(f for f in folder.iterdir() if f.suffix.lower() in IMG_EXTS)
    if not files:
        sys.exit(f"{folder} 裡沒有圖片")

    sam = None
    if args.sam:
        if not os.path.exists(args.sam_model):
            sys.exit(f"找不到 SAM2 權重 {args.sam_model}")
        from ultralytics import SAM

        sam = SAM(args.sam_model)
        print(f"載入 SAM2: {args.sam_model}")
    use_sam = sam is not None

    shape_model, cls_model = load_shape_models(args)
    show_shapes = False
    print(f"共 {len(files)} 張   s: 下一張   a: 上一張" + ("   m: 切換 YOLO/SAM2" if sam else "")
          + ("   d: 開關圖形框" + (" + 形狀分類" if cls_model else "") if shape_model else "")
          + "   q/ESC: 離開")

    win = "Paper Seg"
    i = 0
    cache = {}  # i -> (img, yolo 結果, sam 結果, 圖形框 (沒找到是 False，還沒算是 None), 分類結果 (同左))
    while True:
        f = files[i]
        if i not in cache:
            # cv2.imread 讀不了中文路徑，改用 imdecode
            img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
            r = sr = shp = cls = None
            if img is not None:
                r = model.predict(img, conf=args.conf, imgsz=args.imgsz, device=args.device, verbose=False)[0]
                if sam is not None and len(r.boxes):
                    sr = sam(img, bboxes=r.boxes.xyxy.cpu().numpy(), device=args.device, verbose=False)[0]
            cache = {i: (img, r, sr, shp, cls)}  # 只留目前這張
        img, r, sr, shp, cls = cache[i]
        if show_shapes and shape_model is not None and img is not None and shp is None:
            shp = find_shape(shape_model, img, mask_polys(r), args) or False
            cache[i] = (img, r, sr, shp, cls)
        if show_shapes and cls_model is not None and shp is not None and cls is None:
            cls = classify_shape(cls_model, img, shp, args, round_thr_for(task_of(f.name, args), args)) if shp else False
            cache[i] = (img, r, sr, shp, cls)

        if img is None:
            print(f"[{i + 1}/{len(files)}] 讀取失敗: {f.name}")
            view = np.zeros((200, 600, 3), np.uint8)
            mode, n = "-", 0
        else:
            labels = [f"{r.names[int(c)]} {float(cf):.2f}" for c, cf in zip(r.boxes.cls, r.boxes.conf)]
            if use_sam:
                mode, polys, color = "SAM2", mask_polys(sr), (255, 0, 255)
            else:
                mode, polys, color = "YOLO", mask_polys(r), (0, 255, 0)
            n = len(polys)
            view = draw_masks(img, polys, labels, color)
            msg = f"[{i + 1}/{len(files)}] {f.name}  {mode}  paper: {n}"
            if show_shapes and shp is not None:
                draw_shape_cls(view, shp, cls)
                msg += f"  shape: {shp[4]:.2f}" if shp else "  shape: 無"
                if cls:
                    msg += (f"  cls: {cls[0]} {cls[1]:.2f}" + (f" (圓度改判: {cls[3]})" if cls[3] else "")
                            + f"  [{fmt_probs(cls[4])}]")
            print(msg)
            s = view_scale(view, args.max_view)
            view = cv2.resize(view, None, fx=s, fy=s) if s < 1.0 else view
            if show_shapes:
                paste_binary(view, cls)
        hint = ("[s] next [a] prev" + (" [m] YOLO/SAM2" if sam else "")
                + (" [d] shape" if shape_model else "") + " [q] quit")
        cv2.putText(view, f"{i + 1}/{len(files)}  {mode}  paper: {n}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(view, hint, (10, view.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        cv2.imshow(win, view)

        key = cv2.waitKey(0) & 0xFF
        if key in (ord("q"), 27) or cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
            break
        if key == ord("s"):
            if i == len(files) - 1:
                print("已經是最後一張")
            else:
                i += 1
        elif key == ord("a"):
            i = max(0, i - 1)
        elif key == ord("m") and sam is not None:
            use_sam = not use_sam
        elif key == ord("d") and shape_model is not None:
            show_shapes = not show_shapes
            print(f"圖形框: {'ON' if show_shapes else 'OFF'}")
    cv2.destroyAllWindows()


def view_scale(img, max_w):
    return min(1.0, max_w / img.shape[1])


def select_roi(img, max_w):
    """在縮放後的影像上選 ROI，回傳原圖座標 (x, y, w, h)，取消則回傳 None"""
    s = view_scale(img, max_w)
    disp = cv2.resize(img, None, fx=s, fy=s) if s < 1.0 else img
    win = "Select ROI"
    x, y, w, h = cv2.selectROI(win, disp, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(win)
    if w == 0 or h == 0:
        return None

    H, W = img.shape[:2]
    x, y, w, h = (int(round(v / s)) for v in (x, y, w, h))
    x, y = max(0, x), max(0, y)
    return x, y, min(w, W - x), min(h, H - y)


def load_roi(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return d["x"], d["y"], d["w"], d["h"]


def save_roi(path, roi):
    x, y, w, h = roi
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"x": x, "y": y, "w": w, "h": h}, f, indent=2)


def main():
    args = parse_args()
    if args.images:
        browse_images(load_model(args.model), args)
        return

    os.makedirs(args.out, exist_ok=True)
    roi_path = os.path.join(args.out, "roi.json")
    roi = load_roi(roi_path)
    if roi:
        print(f"載入 ROI: x={roi[0]} y={roi[1]} w={roi[2]} h={roi[3]}")

    model = load_model(args.model)
    detecting = model is not None and not args.no_detect
    shape_model, cls_model = load_shape_models(args)
    show_shapes = False

    cap = open_camera(args.cam, args.width, args.height)
    print(f"攝影機解析度: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print("r: 設定ROI   x: 清除ROI   d: 開關圖形+分類   y: 開關偵測   SPACE: 拍照   q/ESC: 離開")

    win = "Camera"
    count = 0
    fps = 0.0
    t_prev = time.perf_counter()
    while True:
        ok, frame = cap.read()
        if not ok:
            print("讀取影像失敗")
            break

        # 偵測結果畫在 view 上，frame 保持原圖給拍照用
        view = frame.copy()
        counts = Counter()
        if detecting:
            if roi:
                x, y, w, h = roi
                view[y:y + h, x:x + w], counts = detect(model, frame[y:y + h, x:x + w], args)
            else:
                view, counts = detect(model, frame, args)
        shp = cls = None
        if show_shapes:
            # 有 ROI 只在 ROI 裡找圖形，座標再換回整張
            ox, oy, src = (roi[0], roi[1], frame[roi[1]:roi[1] + roi[3], roi[0]:roi[0] + roi[2]]) if roi else (0, 0, frame)
            shp = find_shape(shape_model, src, [], args)
            if shp:
                if cls_model is not None:
                    cls = classify_shape(cls_model, src, shp, args, round_thr_for(task_of("", args), args))
                x1, y1, x2, y2, cf = shp
                shp = (x1 + ox, y1 + oy, x2 + ox, y2 + oy, cf)
            draw_shape_cls(view, shp, cls)

        now = time.perf_counter()
        fps = 0.9 * fps + 0.1 / max(now - t_prev, 1e-6)
        t_prev = now

        s = view_scale(view, args.max_view)
        disp = cv2.resize(view, None, fx=s, fy=s) if s < 1.0 else view
        if roi:
            x, y, w, h = (int(v * s) for v in roi)
            cv2.rectangle(disp, (x, y), (x + w, y + h), (0, 0, 255), 2)
        status = f"ROI {roi[2]}x{roi[3]}" if roi else "ROI: full"
        if show_shapes:
            paste_binary(disp, cls)
        cv2.putText(disp, f"saved: {count}  {status}  [r] ROI [x] clear [d] shape [y] detect [SPACE] shot [q] quit",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        if detecting:
            names = model.names.values()
            det_txt = "  ".join(f"{n}: {counts.get(n, 0)}" for n in names)
            cv2.putText(disp, f"FPS {fps:4.1f}  {det_txt}",
                        (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        else:
            cv2.putText(disp, "detect: OFF" if model else "detect: no model",
                        (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow(win, disp)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break

        if key == ord("r"):
            new_roi = select_roi(frame.copy(), args.max_view)
            if new_roi:
                roi = new_roi
                save_roi(roi_path, roi)
                print(f"設定 ROI: x={roi[0]} y={roi[1]} w={roi[2]} h={roi[3]}")
            else:
                print("取消設定 ROI")

        elif key == ord("x"):
            roi = None
            if os.path.exists(roi_path):
                os.remove(roi_path)
            print("已清除 ROI")

        elif key == ord("d"):
            if shape_model is None:
                print("沒有圖形偵測模型")
            else:
                show_shapes = not show_shapes
                print(f"圖形偵測 + 形狀分類: {'ON' if show_shapes else 'OFF'}")

        elif key == ord("y"):
            if model is None:
                print("沒有載入模型，無法偵測")
            else:
                detecting = not detecting
                print(f"偵測: {'ON' if detecting else 'OFF'}")

        elif key == ord(" "):
            if roi:
                x, y, w, h = roi
                shot = frame[y:y + h, x:x + w]
            else:
                shot = frame
            name = f"{args.prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}.jpg"
            path = os.path.join(args.out, name)
            cv2.imwrite(path, shot)
            count += 1
            print(f"[存檔] {path}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
