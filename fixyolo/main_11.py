"""
main_11.py - ch1-t1 (串積木) 本地測試版 (鏡頭即時分析)

從 PDMS2_web/ch1-t1/main.py 改來，拿掉網頁 uid/img_id 流程與 exit code 回傳，純本地分析。
流程：
    1. YOLO seg (line.pt) 找繩子、YOLO seg (cube_top.pt) 找積木
    2. SAM2 開啟時：兩個模型的 box 一起丟給 SAM2 (同一張圖只算一次特徵) 切出精細遮罩
       SAM2 關閉時：直接用 YOLO seg 自己的遮罩 (比較快，邊緣比較粗)
    3. 積木中心點離繩子遮罩夠近 (<= 積木邊長 * NEAR_RATIO，約半顆積木) 就算穿在繩上
    4. 計分同原版：扣掉 2 顆底座，4 顆得 2 分、3 顆得 1 分
限制：從正上方看，積木「壓在 / 靠在繩子上」跟「穿在繩子上」長得一樣，單張照片分不出來。

用法:
    python main_11.py                       # 開鏡頭即時分析 (預設開 SAM2)
    python main_11.py --no-sam              # 開鏡頭即時分析，一開始先關 SAM2
    python main_11.py --cam 1               # 指定攝影機
    python main_11.py img.jpg               # 單張
    python main_11.py capture/ 0921test/    # 多個資料夾 / 檔案
    python main_11.py img.jpg --show        # 跑完顯示結果視窗
    python main_11.py --conf 0.6 --out out  # 調整積木 YOLO 信心值、輸出資料夾
    python main_11.py --line-conf 0.4       # 調整繩子 YOLO 信心值
    python main_11.py --near 0.6            # 調整中心點到繩子的距離門檻 (積木邊長的比例)

鏡頭模式按鍵 (ROI 設定與 take.py 共用 capture/roi.json，有設 ROI 就只分析 ROI 裡面):
    s         : 開 / 關 SAM2
    r         : 設定 ROI
    x         : 清除 ROI
    SPACE     : 存下目前這張原圖 (capture/) 跟結果圖 (--out)
    q / ESC   : 離開

結果圖存到 --out (預設 out/)，檔名 <原檔名>_result.jpg
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

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

from take import open_camera, select_roi, load_roi, save_roi, view_scale

# ================== 核心設定 ==================
CONF = 0.75             # 積木 YOLO 信心值
LINE_CONF = 0.5         # 繩子 YOLO 信心值
NEAR_RATIO = 0.55       # 積木中心點到繩子的距離 <= 積木邊長 * NEAR_RATIO 才算在繩上
                        # (穿在繩上時中心那段繩子被蓋住，距離約半顆積木 0.42~0.52；旁邊沒穿的大多 >= 0.59)
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "cube_top.pt"
LINE_MODEL_PATH = BASE_DIR / "models" / "line.pt"
SAM_CHECKPOINT = BASE_DIR / "models" / "sam2_b.pt"
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

device = "cuda" if torch.cuda.is_available() else "cpu"
yolo_model = None
line_model = None
sam_model = None


def load_models(line_path=LINE_MODEL_PATH):
    global yolo_model, line_model, sam_model
    print(f"[DEBUG] 目前使用設備: {device}", flush=True)
    print(f"[DEBUG] 載入繩子模型: {line_path}", flush=True)
    line_model = YOLO(str(line_path))
    print(f"[DEBUG] 載入積木模型: {MODEL_PATH}", flush=True)
    yolo_model = YOLO(str(MODEL_PATH))
    print(f"[DEBUG] 載入 SAM2 模型: {SAM_CHECKPOINT}", flush=True)
    sam_model = SAM(str(SAM_CHECKPOINT))
    print("[DEBUG] 模型載入完成", flush=True)


# ================== 輔助函數 ==================

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

def detect(model, frame, conf):
    """YOLO seg：回傳 (boxes, 原圖大小的遮罩 list[bool HxW])，只留 class 0"""
    r = model.predict(source=frame, conf=conf, retina_masks=True, verbose=False)[0]
    if r.boxes is None or len(r.boxes) == 0:
        return [], []
    keep = r.boxes.cls.cpu().numpy().astype(int) == 0
    boxes = list(r.boxes.xyxy.cpu().numpy()[keep])
    masks = list(r.masks.data.cpu().numpy()[keep] > 0.5) if r.masks is not None else []
    return boxes, masks

def segment(frame, conf=CONF, line_conf=LINE_CONF, use_sam=True):
    """回傳 (繩子遮罩 bool HxW, 積木遮罩 list)"""
    rope_boxes, rope_masks = detect(line_model, frame, line_conf)
    cube_boxes, cube_masks = detect(yolo_model, frame, conf)
    if use_sam and (rope_boxes or cube_boxes):
        sam_masks = get_sam_masks(frame, rope_boxes + cube_boxes)
        if len(sam_masks) == len(rope_boxes) + len(cube_boxes):
            rope_masks, cube_masks = sam_masks[:len(rope_boxes)], sam_masks[len(rope_boxes):]
    rope = np.zeros(frame.shape[:2], bool)
    for m in rope_masks:   # 繩子常被積木切成好幾段，合成一張
        rope |= m
    return rope, cube_masks


def judge_strung(masks, rope, near_ratio=NEAR_RATIO):
    """
    每顆積木中心點離繩子多遠 (中心點 = 積木遮罩的重心)。
    距離 <= 積木邊長 * near_ratio 就算在繩上。
    回傳 (is_correct list, 每顆的 (中心, 距離, 門檻))
    """
    if rope.any():
        dist = cv2.distanceTransform((~rope).astype(np.uint8), cv2.DIST_L2, 5)
    else:
        dist = np.full(rope.shape, np.inf, np.float32)
    is_correct, infos = [], []
    for m in masks:
        ys, xs = np.where(m)
        if len(xs) == 0:
            is_correct.append(False)
            infos.append(((0, 0), np.inf, 0))
            continue
        cx, cy = xs.mean(), ys.mean()
        d = float(dist[int(round(cy)), int(round(cx))])
        thr = np.sqrt(len(xs)) * near_ratio
        is_correct.append(d <= thr)
        infos.append(((cx, cy), d, thr))
    return is_correct, infos


def draw_block_markers(frame, masks, is_correct, rope, infos):
    vis = frame.copy()
    vis[rope] = (vis[rope] * 0.4 + np.array([255, 255, 0]) * 0.6).astype(np.uint8)   # 繩子 (青色)

    overlay = vis.copy()
    for i, mask in enumerate(masks):
        # 正確為白色，錯誤為紅色
        color = (255, 255, 255) if is_correct[i] else (0, 0, 255)
        overlay[mask] = color
    vis = cv2.addWeighted(overlay, 0.4, vis, 0.6, 0)

    for i, (center, d, thr) in enumerate(infos):
        c = tuple(int(v) for v in center)
        color = (255, 255, 255) if is_correct[i] else (0, 0, 255)
        cv2.circle(vis, c, 8, color, -1)
        txt = "inf" if np.isinf(d) else f"{d:.0f}/{thr:.0f}"   # 距離 / 門檻 (像素)
        cv2.putText(vis, txt, (c[0] + 10, c[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
        cv2.putText(vis, txt, (c[0] + 10, c[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return vis

# ================== 主評分邏輯 ==================
def calc_score(correct_num):
    # 計分邏輯：2個是基礎，多1個加1分
    correct_num_for_score = correct_num
    if correct_num_for_score >= 2:
        correct_num_for_score -= 2

    if correct_num_for_score == 4:
        return 2
    elif correct_num_for_score == 3:
        return 1
    return 0


def analyze(img, conf=CONF, line_conf=LINE_CONF, near_ratio=NEAR_RATIO, use_sam=True):
    rope, masks = segment(img, conf, line_conf, use_sam)
    is_correct, infos = judge_strung(masks, rope, near_ratio)
    correct_num = sum(is_correct)
    result_img = draw_block_markers(img, masks, is_correct, rope, infos)
    return calc_score(correct_num), correct_num, result_img


def score_from_image(img_path, conf=CONF, line_conf=LINE_CONF, near_ratio=NEAR_RATIO, use_sam=True):
    img = cv2.imread(str(img_path))
    if img is None: raise ValueError(f"讀取圖片失敗：{img_path}")
    return analyze(img, conf, line_conf, near_ratio, use_sam)

# ================== 本地測試 ==================
def collect_images(paths):
    imgs = []
    for p in map(Path, paths):
        if p.is_dir():
            imgs += sorted(f for f in p.iterdir()
                           if f.suffix.lower() in IMG_EXTS and not f.stem.endswith("_result"))
        elif p.is_file():
            imgs.append(p)
        else:
            print(f"[WARN] 找不到：{p}", flush=True)
    return imgs


def show_result(title, img):
    h, w = img.shape[:2]
    scale = min(1.0, 1280 / max(w, 1), 720 / max(h, 1))
    view = cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1.0 else img
    cv2.imshow("result", view)
    cv2.setWindowTitle("result", title)
    print("[TEST] 按任意鍵下一張，q / ESC 結束顯示", flush=True)
    return cv2.waitKey(0) & 0xFF not in (ord("q"), 27)


def score_and_save(img_path, out_dir, args):
    score, num, result_img = score_from_image(img_path, conf=args.conf, line_conf=args.line_conf,
                                              near_ratio=args.near, use_sam=args.sam)
    save_path = out_dir / f"{img_path.stem}_result.jpg"
    cv2.imwrite(str(save_path), result_img)
    print(f"{img_path.name}: score={score}, num={num} -> {save_path}", flush=True)
    return score, num, result_img


def run_files(inputs, out_dir, args, show):
    imgs = collect_images(inputs)
    if not imgs:
        sys.exit("沒有可分析的圖片")
    load_models(args.line)

    results = []
    for img_path in imgs:
        try:
            score, num, result_img = score_and_save(img_path, out_dir, args)
        except Exception as e:
            print(f"[ERROR] {img_path}: {e}", flush=True)
            continue
        results.append((img_path.name, score, num))
        if show:
            show = show_result(f"{img_path.name}  score={score}  num={num}", result_img)
    cv2.destroyAllWindows()

    print("\n===== 總結 =====")
    for name, score, num in results:
        print(f"{name:40s} score={score}  num={num}")


def put_status(img, lines):
    for i, txt in enumerate(lines):
        y = 25 + i * 25
        cv2.putText(img, txt, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(img, txt, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)


def run_camera(args, out_dir):
    cap_dir = Path(args.capture)
    cap_dir.mkdir(parents=True, exist_ok=True)
    roi_path = cap_dir / "roi.json"
    roi = load_roi(roi_path)
    if roi:
        print(f"載入 ROI: x={roi[0]} y={roi[1]} w={roi[2]} h={roi[3]}")

    load_models(args.line)
    cap = open_camera(args.cam, args.width, args.height)
    print(f"攝影機解析度: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print("s: 開關SAM2   r: 設定ROI   x: 清除ROI   SPACE: 存圖   q/ESC: 離開")

    use_sam = args.sam
    fps = 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            print("讀取影像失敗")
            break

        if roi:
            x, y, w, h = roi
            shot = frame[y:y + h, x:x + w]
        else:
            shot = frame

        t0 = time.perf_counter()
        try:
            score, num, result_img = analyze(shot, args.conf, args.line_conf, args.near, use_sam)
        except Exception as e:
            print(f"[ERROR] 分析失敗: {e}", flush=True)
            score, num, result_img = 0, 0, shot.copy()
        dt = time.perf_counter() - t0
        fps = 1 / dt if fps == 0 else fps * 0.9 + (1 / dt) * 0.1   # 平滑一下

        s = view_scale(result_img, 1280)
        disp = cv2.resize(result_img, None, fx=s, fy=s) if s < 1.0 else result_img.copy()
        put_status(disp, [
            f"score={score}  num={num}   SAM2={'ON' if use_sam else 'OFF'}   {fps:.1f} FPS",
            "[s] SAM2 [r] ROI [x] clear [SPACE] save [q] quit",
        ])
        cv2.imshow("Camera", disp)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break

        if key == ord("s"):
            use_sam = not use_sam
            fps = 0.0
            print(f"SAM2: {'ON' if use_sam else 'OFF'}")

        elif key == ord("r"):
            new_roi = select_roi(frame.copy(), 1280)
            if new_roi:
                roi = new_roi
                save_roi(roi_path, roi)
                print(f"設定 ROI: x={roi[0]} y={roi[1]} w={roi[2]} h={roi[3]}")
            else:
                print("取消設定 ROI")

        elif key == ord("x"):
            roi = None
            if roi_path.exists():
                roi_path.unlink()
            print("已清除 ROI")

        elif key == ord(" "):
            img_path = cap_dir / f"ch1-t1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            cv2.imwrite(str(img_path), shot)
            save_path = out_dir / f"{img_path.stem}_result.jpg"
            cv2.imwrite(str(save_path), result_img)
            print(f"[存檔] {img_path} -> {save_path}  score={score} num={num} SAM2={'ON' if use_sam else 'OFF'}",
                  flush=True)

    cap.release()
    cv2.destroyAllWindows()


def main():
    p = argparse.ArgumentParser(description="ch1-t1 串積木 本地測試")
    p.add_argument("inputs", nargs="*", help="圖片或資料夾；不給就開鏡頭即時分析")
    p.add_argument("--out", default="out", help="結果圖輸出資料夾")
    p.add_argument("--conf", type=float, default=CONF, help="積木 YOLO 信心值")
    p.add_argument("--line-conf", type=float, default=LINE_CONF, help="繩子 YOLO 信心值")
    p.add_argument("--near", type=float, default=NEAR_RATIO, help="中心點到繩子的距離門檻 (積木邊長的比例)")
    p.add_argument("--line", default=str(LINE_MODEL_PATH), help="繩子 seg 模型")
    p.add_argument("--no-sam", dest="sam", action="store_false", help="不用 SAM2，直接用 YOLO seg 遮罩")
    p.add_argument("--show", action="store_true", help="(檔案模式) 顯示結果視窗")
    p.add_argument("--cam", type=int, default=0, help="攝影機編號")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--capture", default="capture", help="拍照存檔資料夾")
    args = p.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.inputs:
        run_files(args.inputs, out_dir, args, args.show)
    else:
        run_camera(args, out_dir)


if __name__ == "__main__":
    main()
