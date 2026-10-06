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
CONF = 0.75
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

# 2. SAM2 模型 (ultralytics，用於精細分割)
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

def detect_blocks_boxes(frame, conf=CONF):
    results = yolo_model.predict(source=frame, conf=conf, verbose=False)
    boxes = []
    for r in results:
        if r.boxes is None: continue
        for box in r.boxes:
            if int(box.cls[0]) == 0:
                boxes.append(box.xyxy[0].cpu().numpy())
    return boxes

def remove_blocks_with_mask(binary, masks, extra_px=10):
    h, w = binary.shape
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (extra_px * 2, extra_px * 2))
    for mask in masks:
        mask_binary = (mask > 0).astype(np.uint8)
        mask_dilated = cv2.dilate(mask_binary, kernel)
        binary[mask_dilated > 0] = 0
    return binary

def extract_line_skeleton(binary):
    skeleton = np.zeros(binary.shape, np.uint8)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (7, 7))
    temp = np.copy(binary)
    while True:
        open_img = cv2.morphologyEx(temp, cv2.MORPH_OPEN, element)
        temp2 = cv2.subtract(temp, open_img)
        eroded = cv2.erode(temp, element)
        skeleton = cv2.bitwise_or(skeleton, temp2)
        temp = eroded.copy()
        if cv2.countNonZero(temp) == 0: break
    return skeleton

def is_mask_near_skeleton(mask, skeleton, tol=15):
    ys, xs = np.where(mask > 0)
    h, w = skeleton.shape
    for x, y in zip(xs, ys):
        x0, x1 = max(0, x - tol), min(w, x + tol + 1)
        y0, y1 = max(0, y - tol), min(h, y + tol + 1)
        if np.any(skeleton[y0:y1, x0:x1] > 0):
            return True
    return False

def draw_block_markers(frame, boxes, masks, is_correct, skeleton):
    # 標註骨架線 (Cyan)
    skeleton_bgr = cv2.cvtColor(skeleton, cv2.COLOR_GRAY2BGR)
    skeleton_bgr[skeleton > 0] = (255, 255, 0)
    frame = cv2.addWeighted(skeleton_bgr, 0.8, frame, 1.0, 0)
    
    overlay = frame.copy()
    for i, mask in enumerate(masks):
        # 正確為白色，錯誤為紅色
        color = (255, 255, 255) if is_correct[i] else (0, 0, 255)
        overlay[mask > 0] = color
        box = boxes[i]
        center = (int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2))
        cv2.circle(frame, center, 10, color, -1)

    return cv2.addWeighted(overlay, 0.4, frame, 0.6, 0)

# ================== 主評分邏輯 ==================
def score_from_image(img_path, conf=CONF):
    img = cv2.imread(img_path)
    if img is None: raise ValueError(f"讀取圖片失敗：{img_path}")

    display_frame = img.copy()

    gray = cv2.cvtColor(display_frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 0)
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 27, 10
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    boxes = detect_blocks_boxes(display_frame, conf=conf)
    masks = get_sam_masks(display_frame, boxes)

    binary_masked = binary.copy()
    if masks:
        binary_masked = remove_blocks_with_mask(binary_masked, masks)

    skeleton = extract_line_skeleton(binary_masked)
    
    is_correct = []
    correct_num = 0
    for mask in masks:
        is_near = is_mask_near_skeleton(mask, skeleton, tol=15)
        is_correct.append(is_near)
        if is_near: correct_num += 1

    result_img = draw_block_markers(display_frame, boxes, masks, is_correct, skeleton)

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