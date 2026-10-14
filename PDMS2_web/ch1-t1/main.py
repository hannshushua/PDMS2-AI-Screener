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
import sys
import os
from pathlib import Path

# ================== 核心設定 ==================
# 分析流程：line.pt 找繩子 -> SAM2 切繩子遮罩；cube_top.pt 找積木 -> SAM2 切積木遮罩；
#           積木中心點離繩子夠近 (<= 積木邊長 * NEAR_RATIO，約半顆積木) 就算穿在繩上
CONF = 0.75             # 積木 YOLO 信心值
LINE_CONF = 0.5         # 繩子 YOLO 信心值
NEAR_RATIO = 0.55       # 積木中心點到繩子的距離 <= 積木邊長 * NEAR_RATIO 才算在繩上
                        # (穿在繩上時中心那段繩子被蓋住，距離約半顆積木 0.42~0.52；旁邊沒穿的大多 >= 0.59)
BASE_DIR = Path(__file__).resolve().parent

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

def detect_boxes(model, frame, conf):
    results = model.predict(source=frame, conf=conf, verbose=False)
    boxes = []
    for r in results:
        if r.boxes is None: continue
        for box in r.boxes:
            if int(box.cls[0]) == 0:
                boxes.append(box.xyxy[0].cpu().numpy())
    return boxes

def detect_blocks_boxes(frame, conf=CONF):
    return detect_boxes(yolo_model, frame, conf)

def get_rope_mask(frame, conf=LINE_CONF):
    """line.pt 找繩子 (常被積木切成好幾段)，每段的 box 丟給 SAM2，全部合成一張繩子遮罩"""
    boxes = detect_boxes(line_model, frame, conf)
    rope = np.zeros(frame.shape[:2], bool)
    for m in get_sam_masks(frame, boxes):
        rope |= m
    return rope

def judge_strung(masks, rope):
    """
    每顆積木中心點離繩子多遠 (中心點 = 積木遮罩的重心)。
    距離 <= 積木邊長 * NEAR_RATIO 就算在繩上。
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
        thr = np.sqrt(len(xs)) * NEAR_RATIO
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
def score_from_image(img_path, conf=CONF):
    img = cv2.imread(img_path)
    if img is None: raise ValueError(f"讀取圖片失敗：{img_path}")

    rope = get_rope_mask(img)
    boxes = detect_blocks_boxes(img, conf=conf)
    masks = get_sam_masks(img, boxes)

    is_correct, infos = judge_strung(masks, rope)
    correct_num = sum(is_correct)

    result_img = draw_block_markers(img, masks, is_correct, rope, infos)

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