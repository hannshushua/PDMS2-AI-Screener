"""
ch2 畫圖三關共用 —— 分類「之前」的所有前處理：
  影像 -> paper 模型 bbox + SAM2 找紙張
       -> 在紙張 mask 範圍內用 shape 模型(YOLO) 多尺度圈出手繪圖形（CV 保底）
       -> 切正方形(框外用框邊像素補) -> 轉黑底白線 binary(224)
  找框 + 切圖跟 fixyolo/take.py 一樣 (shape_cls.pt 是用這套切出來的圖訓練的)

用法：
  from prepare import Preparer
  prep = Preparer()                                # 載 models/paper_seg.pt + sam2_b.pt
  r = prep.prepare(img_path, out_dir, stem)        # 回傳 dict
      r["ok"]           是否成功圈到圖形
      r["reason"]       失敗原因 (read_fail / no_paper / no_shape)
      r["binary_bgr"]   餵給分類器的 224 binary(3通道) BGR 影像
      r["color_path"]   彩色 224 crop 路徑（給 check_point 用）
      r["binary_path"]  黑底白線 224 crop 路徑（給 CrossScorer 用）
      r["vis"]          紙張輪廓 + 圖形框 的可視化 BGR
分類請用 classify.py，評分用各關自己的模組。
"""

from pathlib import Path

import cv2
import numpy as np

MODELS_DIR = Path(__file__).resolve().parent / "models"
DEFAULT_PAPER_WEIGHTS = MODELS_DIR / "paper_seg.pt"
DEFAULT_SAM_WEIGHTS = MODELS_DIR / "sam2_b.pt"
DEFAULT_SHAPE_WEIGHTS = MODELS_DIR / "shape_det.pt"


def pick_device(arg=None):
    if arg:
        return arg
    try:
        import torch
        return "0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


# ---------------- step1: 找白紙 (paper 模型 bbox + SAM2) ----------------
def get_paper_bbox(frame, yolo, device, conf):
    """用 paper 模型取紙張 bbox (x1,y1,x2,y2)，找不到回 None。
    紙張是畫面中最大的物件，故取「面積最大」的框（不是信心最高），
    避免挑到邊緣的高信心小雜訊框。"""
    res = yolo.predict(source=frame, conf=conf, device=device, verbose=False)[0]
    if res.boxes is None or len(res.boxes) == 0:
        return None
    boxes = res.boxes.xyxy.cpu().numpy()
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return boxes[int(np.argmax(areas))]


def sam_mask_from_bbox(frame, sam, bbox, device):
    """以 bbox 提示 SAM2，回傳精修後的紙張 mask (uint8, 0/255) 或 None。"""
    sam_res = sam.predict(source=frame, bboxes=np.array([bbox]),
                          device=device, verbose=False)[0]
    if sam_res.masks is None or len(sam_res.masks) == 0:
        return None
    m = sam_res.masks.data.cpu().numpy()[0]
    mask = (m > 0.5).astype(np.uint8)
    if mask.shape[:2] != frame.shape[:2]:
        mask = cv2.resize(mask, (frame.shape[1], frame.shape[0]),
                          interpolation=cv2.INTER_NEAREST)
    mask = mask * 255
    # SAM 有時會把紙上深色筆跡當成非紙區域、在紙內挖出洞，導致 shape 框中心
    # 落在洞上被誤濾。取最大外輪廓填實，紙張區域維持實心（外邊界不變）。
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        filled = np.zeros_like(mask)
        cv2.drawContours(filled, [max(cnts, key=cv2.contourArea)], -1, 255, cv2.FILLED)
        mask = filled
    return mask


def locate_paper(frame, yolo, sam, device, conf):
    """paper 模型 bbox -> SAM2 精修出紙張 mask。回傳 mask 或 None。"""
    bbox = get_paper_bbox(frame, yolo, device, conf)
    if bbox is None:
        return None
    return sam_mask_from_bbox(frame, sam, bbox, device)


def paper_mask_cv(frame):
    """[備用] CV 亮色最大區塊當紙張 mask；prepare 目前用 YOLO+SAM2，此函式供相容/備援。"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    m = np.zeros_like(gray)
    cv2.drawContours(m, [c], -1, 255, cv2.FILLED)
    return m


# ---------------- step2: 紙內用 shape 模型(YOLO) 找圖形 ----------------
def find_shape_bbox_yolo(frame, shape_yolo, paper_mask, device, conf=0.25):
    """在紙張 mask 範圍內用 shape 模型(YOLO) 找手繪圖形。
    只留「框中心落在紙張內」的偵測（濾掉定位標記等紙外雜訊），
    同區重疊時取信心最高者。回傳 (bbox, label, det_conf) 或 None。
      bbox = (x1,y1,x2,y2) int
      label = 'circle'/'cross'/'diamond'/'rectangle'/'triangle'
    """
    res = shape_yolo.predict(source=frame, conf=conf, device=device, verbose=False)[0]
    if res.boxes is None or len(res.boxes) == 0:
        return None
    H, W = paper_mask.shape[:2]
    # 對 SAM mask 的不完美（邊緣偏緊、殘留小洞）留容忍度：膨脹一小圈再判斷，
    # 膨脹量取紙張大小的 ~2%，過濾紙外雜訊的用意仍在，但不會誤刪紙邊圖形。
    paper_area = int((paper_mask > 0).sum())
    k = max(5, int(0.02 * np.sqrt(paper_area)) | 1) if paper_area else 5
    mask_tol = cv2.dilate(paper_mask,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    boxes = res.boxes.xyxy.cpu().numpy()
    confs = res.boxes.conf.cpu().numpy()
    clss = res.boxes.cls.cpu().numpy().astype(int)
    names = shape_yolo.names
    cand = []  # (conf, bbox, label)
    for (x1, y1, x2, y2), cf, ci in zip(boxes, confs, clss):
        cx = int(round((x1 + x2) / 2))
        cy = int(round((y1 + y2) / 2))
        if not (0 <= cx < W and 0 <= cy < H):
            continue
        # 中心在(膨脹後)紙上，或框與紙重疊夠多，就保留（兩者其一即可）。
        center_ok = mask_tol[cy, cx] > 0
        bx1, by1 = max(0, int(x1)), max(0, int(y1))
        bx2, by2 = min(W, int(x2)), min(H, int(y2))
        sub = paper_mask[by1:by2, bx1:bx2]
        overlap = (sub > 0).mean() if sub.size else 0.0
        if not (center_ok or overlap >= 0.3):  # 都不符 -> 視為紙外雜訊丟棄
            continue
        cand.append((float(cf), (int(x1), int(y1), int(x2), int(y2)), names[ci]))
    if not cand:
        return None
    cf, bbox, label = max(cand, key=lambda t: t[0])
    return bbox, label, cf


# ---------------- step2(新): 多尺度 shape 偵測，同 fixyolo/take.py find_shapes ----------------
# shape_cls.pt (fixyolo/train_all.py) 是用這套「找框 + 切圖」做出來的圖訓練的，分類前處理要跟它一樣
SHAPE_PAD = 10  # 偵測框四周各外擴的 px


def _shape_preds(frame, shape_yolo, scale, device, conf, imgsz):
    """把 frame 縮小 scale 倍貼在黑底中央再偵測 (畫太大的圖形縮小後才不會被切成兩半)，
    回傳換回原圖座標的 [(x1, y1, x2, y2, conf, label), ...]"""
    H, W = frame.shape[:2]
    if scale < 1.0:
        sw, sh = int(W * scale), int(H * scale)
        ox, oy = (W - sw) // 2, (H - sh) // 2
        src = np.zeros_like(frame)
        src[oy:oy + sh, ox:ox + sw] = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_AREA)
    else:
        ox = oy = 0
        src = frame
    r = shape_yolo.predict(source=src, conf=conf, imgsz=imgsz, device=device, verbose=False)[0]
    out = []
    for (x1, y1, x2, y2), cf, ci in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
        x1, x2 = ((v - ox) / scale for v in (x1, x2))
        y1, y2 = ((v - oy) / scale for v in (y1, y2))
        out.append((int(x1), int(y1), int(x2), int(y2), float(cf), shape_yolo.names[int(ci)]))
    return out


def find_shape_bbox_multi(frame, shape_yolo, paper_mask, device, conf=0.25, imgsz=640):
    """多尺度找圖形 (原尺寸 + 縮 0.6，都沒有再試 0.4)，只留框 80% 以上在紙上、信心 >= 最高分*0.75 的框，
    合併重複的框，取面積最大的那個，四周外擴 SHAPE_PAD。paper_mask 為 None 就不過濾。
    回傳 (bbox, label, det_conf) 或 None"""
    H, W = frame.shape[:2]

    def area(b):
        return max(0, b[2] - b[0]) * max(0, b[3] - b[1])

    def on_paper(b):
        # 壓在紙邊的手會超出紙外，所以要框大部分在紙上
        if paper_mask is None:
            return True
        x1, y1, x2, y2 = b[:4]
        sub = paper_mask[max(0, y1):min(H, y2), max(0, x1):min(W, x2)]
        return int((sub > 0).sum()) >= 0.8 * max(1, area(b))

    def overlap(a, b):
        # 交集 / 較小框面積：不同尺度框到同一個圖形、或大框裡的半個框都會接近 1
        iw = min(a[2], b[2]) - max(a[0], b[0])
        ih = min(a[3], b[3]) - max(a[1], b[1])
        return 0.0 if iw <= 0 or ih <= 0 else iw * ih / max(1, min(area(a), area(b)))

    for scales in ((1.0, 0.6), (0.4,)):
        cand = [b for sc in scales for b in _shape_preds(frame, shape_yolo, sc, device, conf, imgsz) if on_paper(b)]
        if cand:
            top = max(b[4] for b in cand)
            cand = [b for b in cand if b[4] >= 0.75 * top]
            kept = []
            for b in sorted(cand, key=area, reverse=True):
                if all(overlap(b, k) < 0.6 for k in kept):
                    kept.append(b)
            x1, y1, x2, y2, cf, label = kept[0]
            return ((max(0, x1 - SHAPE_PAD), max(0, y1 - SHAPE_PAD),
                     min(W, x2 + SHAPE_PAD), min(H, y2 + SHAPE_PAD)), label, cf)
    return None


# ---------------- step2(備用): 紙內用 CV 找圖形 ----------------
def find_shape_bbox(frame, paper_mask, min_area_ratio=0.0005):
    """在紙張 mask 範圍內用 OpenCV(adaptiveThreshold) 找手繪圖形外接框。
    回傳 (x1,y1,x2,y2) 或 None。"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    paper_area = int((paper_mask > 0).sum())
    if paper_area == 0:
        return None
    k = max(5, int(0.035 * np.sqrt(paper_area)))
    inner = cv2.erode(paper_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    if int((inner > 0).sum()) == 0:
        return None
    blk = max(15, int(0.06 * np.sqrt(paper_area)) | 1)
    adap = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY_INV, blk, 12)
    ink = ((adap > 0) & (inner > 0)).astype(np.uint8) * 255
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE,
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                           cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    contours, _ = cv2.findContours(ink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = min_area_ratio * paper_area
    cand = []
    for c in contours:
        if cv2.contourArea(c) < min_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        cand.append(((x, y, w, h), (x + w / 2, y + h / 2)))
    if not cand:
        return None
    xs = np.where(inner.any(axis=0))[0]
    ys = np.where(inner.any(axis=1))[0]
    px1, px2, py1, py2 = xs.min(), xs.max(), ys.min(), ys.max()
    mx, my = 0.22 * (px2 - px1), 0.22 * (py2 - py1)
    cl, cr, ct, cb = px1 + mx, px2 - mx, py1 + my, py2 - my
    central = [b for b, (cx, cy) in cand if cl <= cx <= cr and ct <= cy <= cb]
    if not central:
        pcx, pcy = (px1 + px2) / 2, (py1 + py2) / 2
        central = [min(cand, key=lambda t: (t[1][0] - pcx) ** 2 + (t[1][1] - pcy) ** 2)[0]]
    x1 = min(b[0] for b in central)
    y1 = min(b[1] for b in central)
    x2 = max(b[0] + b[2] for b in central)
    y2 = max(b[1] + b[3] for b in central)
    return (x1, y1, x2, y2)


def crop_square(frame, bbox, pad=30):
    """依 bbox 往外擴 pad，再以中心對齊裁成正方形（超界則平移不裁掉）。"""
    x1, y1, x2, y2 = bbox
    x1, y1, x2, y2 = x1 - pad, y1 - pad, x2 + pad, y2 + pad
    H, W = frame.shape[:2]
    side = min(max(x2 - x1, y2 - y1), H, W)
    ccx, ccy = (x1 + x2) / 2, (y1 + y2) / 2
    cx1 = max(0, min(int(round(ccx - side / 2)), W - side))
    cy1 = max(0, min(int(round(ccy - side / 2)), H - side))
    return frame[cy1:cy1 + side, cx1:cx1 + side].copy(), (cx1, cy1, cx1 + side, cy1 + side)


def crop_square_replicate(frame, bbox, pad=30):
    """同 crop_square 的正方形範圍，但只取 bbox 內的像素，框外用框邊像素往外延伸補滿。
    直接切正方形會切到框外的桌緣 / 紙邊，to_binary 只留最大塊時會選到它們而不是圖形。"""
    _, (cx1, cy1, cx2, cy2) = crop_square(frame, bbox, pad)
    x1, y1 = max(bbox[0], cx1), max(bbox[1], cy1)
    x2, y2 = min(bbox[2], cx2), min(bbox[3], cy2)
    crop = cv2.copyMakeBorder(frame[y1:y2, x1:x2], y1 - cy1, cy2 - y2, x1 - cx1, cx2 - x2,
                              cv2.BORDER_REPLICATE)
    return crop, (cx1, cy1, cx2, cy2)


# ---------------- step3(前段): 轉 binary ----------------
def to_binary(bgr):
    """轉黑底白線（同 cls 訓練資料 class_data 格式）。回傳單通道 uint8(0/255)。"""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    blk = max(15, (gray.shape[0] // 5) | 1)
    b = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                              cv2.THRESH_BINARY_INV, blk, 12)
    b = cv2.morphologyEx(b, cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    b = cv2.morphologyEx(b, cv2.MORPH_OPEN,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2)))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(b, connectivity=8)
    if n > 1:
        biggest = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        b = (lbl == biggest).astype(np.uint8) * 255
    return b


class Preparer:
    """分類前的前處理：找紙張 -> shape 模型(YOLO) 找圖形（CV 保底）-> 切圖 -> binary。"""

    def __init__(self, paper_weights=DEFAULT_PAPER_WEIGHTS,
                 sam_weights=DEFAULT_SAM_WEIGHTS, device=None,
                 paper_conf=0.4, pad=30, size=224,
                 shape_weights=DEFAULT_SHAPE_WEIGHTS, shape_conf=0.25):
        from ultralytics import YOLO, SAM
        self.device = pick_device(device)
        self.paper = YOLO(str(paper_weights))
        self.sam = SAM(str(sam_weights))
        self.shape = YOLO(str(shape_weights))
        self.paper_conf = paper_conf
        self.shape_conf = shape_conf
        self.pad = pad
        self.size = size
        print(f"[prepare] device={self.device}")
        print(f"[prepare] paper(yolo bbox)={paper_weights} + SAM2={sam_weights}")
        print(f"[prepare] shape(yolo)={shape_weights}  classes={self.shape.names}")

    def prepare(self, img_path, out_dir, stem):
        """跑分類前流程。回傳 dict（見模組 docstring）。"""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        frame = cv2.imread(str(img_path))
        if frame is None:
            return {"ok": False, "reason": "read_fail", "vis": None}

        # step1: 找白紙
        paper_mask = locate_paper(frame, self.paper, self.sam, self.device, self.paper_conf)
        if paper_mask is not None and int((paper_mask > 0).sum()) == 0:
            paper_mask = None
        vis = frame.copy()
        if paper_mask is not None:
            cnts, _ = cv2.findContours(paper_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(vis, cnts, -1, (255, 128, 0), 2)
        else:
            print("[prepare] 沒找到紙張，改成整張圖找 shape")

        # step2: shape 模型(YOLO) 多尺度找圖形 (有紙就只留紙上的；沒紙也照找)，找不到再退回 CV
        det_label, det_conf = None, None
        pad = self.pad
        hit = find_shape_bbox_multi(frame, self.shape, paper_mask,
                                    self.device, self.shape_conf)
        if hit is not None:
            bbox, det_label, det_conf = hit
            pad = self.pad - SHAPE_PAD  # 偵測框已外擴 SHAPE_PAD，合計還是 self.pad
        elif paper_mask is not None:
            bbox = find_shape_bbox(frame, paper_mask)
        else:
            return {"ok": False, "reason": "no_paper", "vis": vis}
        if bbox is None:
            return {"ok": False, "reason": "no_shape", "vis": vis}

        # step3: 切正方形 (框外用框邊像素補) + binary
        crop, sq = crop_square_replicate(frame, bbox, pad)
        cv2.rectangle(vis, (sq[0], sq[1]), (sq[2], sq[3]), (0, 255, 0), 3)
        color224 = cv2.resize(crop, (self.size, self.size), interpolation=cv2.INTER_AREA)
        binary224 = cv2.resize(to_binary(crop), (self.size, self.size),
                               interpolation=cv2.INTER_AREA)
        bin_bgr = cv2.cvtColor(binary224, cv2.COLOR_GRAY2BGR)

        color_path = str(out_dir / f"{stem}_crop.jpg")
        binary_path = str(out_dir / f"{stem}_binary.jpg")
        vis_path = str(out_dir / f"{stem}_vis.jpg")
        cv2.imwrite(color_path, color224)
        cv2.imwrite(binary_path, binary224)
        cv2.imwrite(vis_path, vis)

        return {"ok": True, "reason": "", "vis": vis, "bbox": sq,
                "det_label": det_label, "det_conf": det_conf,
                "binary_bgr": bin_bgr, "color224": color224, "binary224": binary224,
                "color_path": color_path, "binary_path": binary_path, "vis_path": vis_path}
