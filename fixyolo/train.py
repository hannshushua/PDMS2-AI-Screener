"""
train.py - YOLO segmentation / detection 訓練 (先做離線資料擴增)

資料集格式: Roboflow 匯出的 YOLO seg 格式 (polygon) 或 YOLO detect 格式 (bbox，配 --task detect)
    <dataset>/
        data.yaml          (讀 names / nc)
        train/images, train/labels
        valid/images, valid/labels   (或 val/)
        test/images,  test/labels    (可有可無)

只擴增 train，每張原圖產生 7 張擴增 + 原圖 = 8 張:
    rot      旋轉
    zoomin   放大
    zoomout  縮小
    shift    平移
    contrast 對比
    expo     曝光
    flipud   上下顛倒
幾何類的擴增會把每個 polygon 畫成遮罩、跟圖片一起變換，再找輪廓轉回 polygon，
所以超出畫面的部分會被正確裁掉。valid / test 不擴增，原封不動複製。
detect 模式的 bbox 先當成 4 角矩形一起變換，最後取外接框寫回。

擴增結果存到 <dataset>_aug/ (detect 存 <dataset>_aug_det/；已存在就直接沿用，加 --reaug 重做)

用法:
    python train.py --dataset line_dataset
    python train.py --dataset line_dataset --model yolo11s-seg.pt --epochs 150 --imgsz 640
    python train.py --dataset line_dataset --reaug            # 重新產生擴增資料
    python train.py --dataset line_dataset --aug-only         # 只做擴增不訓練
    python train.py --dataset button_tape_cloth --task detect # bbox 資料集訓練偵測模型
"""
import argparse
import random
import shutil
from pathlib import Path

import cv2
import numpy as np
import yaml

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
BASE_DIR = Path(__file__).resolve().parent

# ================== 擴增參數 ==================
ROT_DEG = (8, 20)          # 旋轉角度範圍 (隨機正負)
ZOOM_IN = (1.15, 1.4)      # 放大倍率
ZOOM_OUT = (0.6, 0.85)     # 縮小倍率
SHIFT = (0.08, 0.18)       # 平移量 (圖寬/高的比例，隨機正負)
CONTRAST = [(0.55, 0.8), (1.25, 1.6)]   # 對比 (降低 or 提高)
EXPOSURE = [(0.45, 0.75), (1.3, 1.8)]   # 曝光 gamma (<1 變亮, >1 變暗)
MIN_POLY_AREA = 15         # 變換後太小的碎片丟掉 (像素面積)
PAD_COLOR = (114, 114, 114)


# ================== 讀寫標註 ==================
def read_labels(path, w, h):
    """回傳 [(cls, Nx2 像素座標 polygon), ...]，bbox (cls cx cy bw bh) 轉成 4 角矩形"""
    out = []
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        v = line.split()
        if len(v) == 5:         # bbox
            cx, cy, bw, bh = map(float, v[1:])
            x1, y1, x2, y2 = cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2
            pts = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32) * [w, h]
        elif len(v) >= 7:       # polygon，至少 3 個點
            pts = np.array(v[1:], dtype=np.float32).reshape(-1, 2) * [w, h]
        else:
            continue
        out.append((int(v[0]), pts))
    return out


def write_labels(path, polys, w, h, task="segment"):
    lines = []
    for cls, pts in polys:
        norm = np.clip(pts / [w, h], 0, 1)
        if task == "detect":    # 取外接框
            (x1, y1), (x2, y2) = norm.min(0), norm.max(0)
            if x2 - x1 <= 0 or y2 - y1 <= 0:
                continue
            lines.append(f"{cls} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}")
        else:
            lines.append(f"{cls} " + " ".join(f"{x:.6f} {y:.6f}" for x, y in norm))
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


def count_label_types(*label_dirs):
    """回傳 (bbox 行數, polygon 行數)"""
    n_box = n_poly = 0
    for d in label_dirs:
        if d is None or not d.is_dir():
            continue
        for f in d.glob("*.txt"):
            for line in f.read_text().splitlines():
                n = len(line.split())
                if n == 5:
                    n_box += 1
                elif n >= 7:
                    n_poly += 1
    return n_box, n_poly


# ================== 幾何變換 ==================
def warp(img, polys, M):
    """用 2x3 仿射矩陣 M 變換圖片，polygon 走遮罩變換再取輪廓"""
    h, w = img.shape[:2]
    out_img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=PAD_COLOR)
    out_polys = []
    for cls, pts in polys:
        mask = np.zeros((h, w), np.uint8)
        cv2.fillPoly(mask, [np.round(pts).astype(np.int32)], 255)
        mask = cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            if cv2.contourArea(c) < MIN_POLY_AREA or len(c) < 3:
                continue
            out_polys.append((cls, c.reshape(-1, 2).astype(np.float32)))
    return out_img, out_polys


def center_affine(w, h, angle=0.0, scale=1.0, tx=0.0, ty=0.0):
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    M[0, 2] += tx
    M[1, 2] += ty
    return M


def rand_sign():
    return random.choice((-1, 1))


def aug_rot(img, polys):
    h, w = img.shape[:2]
    return warp(img, polys, center_affine(w, h, angle=rand_sign() * random.uniform(*ROT_DEG)))


def aug_zoomin(img, polys):
    h, w = img.shape[:2]
    return warp(img, polys, center_affine(w, h, scale=random.uniform(*ZOOM_IN)))


def aug_zoomout(img, polys):
    h, w = img.shape[:2]
    return warp(img, polys, center_affine(w, h, scale=random.uniform(*ZOOM_OUT)))


def aug_shift(img, polys):
    h, w = img.shape[:2]
    tx = rand_sign() * random.uniform(*SHIFT) * w
    ty = rand_sign() * random.uniform(*SHIFT) * h
    return warp(img, polys, center_affine(w, h, tx=tx, ty=ty))


def aug_flipud(img, polys):
    h = img.shape[0]
    return cv2.flip(img, 0), [(c, np.column_stack([p[:, 0], (h - 1) - p[:, 1]])) for c, p in polys]


# ================== 顏色變換 (標註不變) ==================
def aug_contrast(img, polys):
    a = random.uniform(*random.choice(CONTRAST))
    mean = img.mean()
    out = np.clip((img.astype(np.float32) - mean) * a + mean, 0, 255).astype(np.uint8)
    return out, polys


def aug_exposure(img, polys):
    g = random.uniform(*random.choice(EXPOSURE))
    lut = np.clip(((np.arange(256) / 255.0) ** g) * 255, 0, 255).astype(np.uint8)
    return cv2.LUT(img, lut), polys


AUGS = [
    ("rot", aug_rot),
    ("zoomin", aug_zoomin),
    ("zoomout", aug_zoomout),
    ("shift", aug_shift),
    ("contrast", aug_contrast),
    ("expo", aug_exposure),
    ("flipud", aug_flipud),
]


# ================== 資料集處理 ==================
def find_split(root, names):
    for n in names:
        if (root / n / "images").is_dir():
            return root / n
    return None


def copy_split(src, dst):
    (dst / "images").mkdir(parents=True, exist_ok=True)
    (dst / "labels").mkdir(parents=True, exist_ok=True)
    for f in (src / "images").iterdir():
        if f.suffix.lower() in IMG_EXTS:
            shutil.copy2(f, dst / "images" / f.name)
            lbl = src / "labels" / (f.stem + ".txt")
            if lbl.exists():
                shutil.copy2(lbl, dst / "labels" / lbl.name)


def augment_split(src, dst, task):
    (dst / "images").mkdir(parents=True, exist_ok=True)
    (dst / "labels").mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in (src / "images").iterdir() if f.suffix.lower() in IMG_EXTS)
    for i, f in enumerate(files, 1):
        img = cv2.imread(str(f))
        if img is None:
            print(f"[WARN] 讀不到 {f}，跳過")
            continue
        h, w = img.shape[:2]
        polys = read_labels(src / "labels" / (f.stem + ".txt"), w, h)

        # 原圖
        shutil.copy2(f, dst / "images" / f.name)
        write_labels(dst / "labels" / (f.stem + ".txt"), polys, w, h, task)

        for tag, fn in AUGS:
            a_img, a_polys = fn(img, polys)
            name = f"{f.stem}_{tag}"
            cv2.imwrite(str(dst / "images" / (name + ".jpg")), a_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            write_labels(dst / "labels" / (name + ".txt"), a_polys, w, h, task)

        if i % 20 == 0 or i == len(files):
            print(f"  擴增 {i}/{len(files)}", flush=True)
    return len(files)


def build_aug_dataset(src_root, dst_root, reaug, task):
    data_yaml = dst_root / "data.yaml"
    if data_yaml.exists() and not reaug:
        print(f"[INFO] 沿用已存在的擴增資料集 {dst_root} (要重做加 --reaug)")
        return data_yaml

    train = find_split(src_root, ["train"])
    val = find_split(src_root, ["valid", "val"])
    test = find_split(src_root, ["test"])
    if train is None or val is None:
        raise SystemExit(f"[ERROR] {src_root} 底下找不到 train/images 或 valid/images")

    n_box, n_poly = count_label_types(train / "labels", val / "labels", test and test / "labels")
    print(f"[INFO] 標註: bbox {n_box} 行, polygon {n_poly} 行")
    if n_box + n_poly == 0:
        raise SystemExit(f"[ERROR] {src_root} 裡沒有任何標註")
    if task == "segment" and n_box > 0:
        raise SystemExit(f"[ERROR] 有 {n_box} 行是 bbox 不是 polygon，無法訓練 segment。"
                         f"改用 --task detect，或回 Roboflow 用 Polygon 重標")

    if dst_root.exists():
        shutil.rmtree(dst_root)

    src_yaml = src_root / "data.yaml"
    meta = yaml.safe_load(src_yaml.read_text(encoding="utf-8")) if src_yaml.exists() else {}
    names = meta.get("names")
    if names is None:
        raise SystemExit(f"[ERROR] {src_yaml} 裡沒有 names")

    print(f"[INFO] 擴增 train ({len(AUGS)} 種 + 原圖 = {len(AUGS) + 1} 倍) -> {dst_root}")
    n = augment_split(train, dst_root / "train", task)
    print(f"[INFO] train: {n} 張 -> {n * (len(AUGS) + 1)} 張")
    copy_split(val, dst_root / "valid")
    if test is not None:
        copy_split(test, dst_root / "test")

    out = {
        "path": str(dst_root.resolve()),
        "train": "train/images",
        "val": "valid/images",
        "nc": len(names),
        "names": names,
    }
    if test is not None:
        out["test"] = "test/images"
    data_yaml.write_text(yaml.safe_dump(out, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return data_yaml


def main():
    ap = argparse.ArgumentParser(description="資料擴增 + YOLO seg / detect 訓練")
    ap.add_argument("--dataset", required=True, help="資料集資料夾 (含 data.yaml、train/、valid/)")
    ap.add_argument("--task", choices=["segment", "detect"], default="segment",
                    help="segment (polygon 標註) 或 detect (bbox 標註)")
    ap.add_argument("--model", default=None,
                    help="起始權重 (預設 segment: yolo11n-seg.pt / detect: yolo11n.pt)")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--device", default=None, help="例: 0 / cpu (預設自動)")
    ap.add_argument("--name", default=None, help="runs/<task>/<name> (預設用資料集名稱)")
    ap.add_argument("--seed", type=int, default=0, help="擴增亂數種子")
    ap.add_argument("--reaug", action="store_true", help="強制重新產生擴增資料")
    ap.add_argument("--aug-only", action="store_true", help="只做擴增，不訓練")
    args = ap.parse_args()

    src = Path(args.dataset)
    if src.is_file():                       # 也接受直接給 data.yaml
        src = src.parent
    if not src.is_absolute() and not src.exists():
        src = BASE_DIR / src
    src = src.resolve()
    if not src.is_dir():
        raise SystemExit(f"[ERROR] 找不到資料集 {args.dataset}")

    random.seed(args.seed)
    np.random.seed(args.seed)
    detect = args.task == "detect"
    model_path = args.model or ("yolo11n.pt" if detect else "yolo11n-seg.pt")
    # detect 跟 segment 的擴增標註格式不同，分開存
    aug_root = src.parent / f"{src.name}_aug{'_det' if detect else ''}"
    data_yaml = build_aug_dataset(src, aug_root, args.reaug, args.task)
    if args.aug_only:
        print(f"[INFO] 擴增完成: {data_yaml}")
        return

    from ultralytics import YOLO

    model = YOLO(model_path)
    if model.task != args.task:
        raise SystemExit(f"[ERROR] {model_path} 是 {model.task} 模型，跟 --task {args.task} 不符")
    run_name = args.name or f"{src.name}_{'det' if detect else 'seg'}"
    model.train(
        data=str(data_yaml),
        task=args.task,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        device=args.device,
        project=str(BASE_DIR / "runs" / args.task),
        name=run_name,
    )
    print(f"[INFO] 訓練完成，最佳權重在 runs/{args.task}/{run_name}*/weights/best.pt")


if __name__ == "__main__":
    main()
