import cv2
import numpy as np
import torch

_original_torch_load = torch.load
def safe_load(*args, **kwargs):
    # 如果呼叫時沒有特別指定 weights_only，就強制設為 False
    kwargs.setdefault('weights_only', False)
    return _original_torch_load(*args, **kwargs)
torch.load = safe_load

from ultralytics import YOLO
import sys
import os
from pathlib import Path
from segment_anything import sam_model_registry, SamPredictor

# ================== 核心設定 ==================
CONF = 0.5
BASE_DIR = Path(__file__).resolve().parent

# ================== 初始化模型 ==================
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[DEBUG] 目前使用設備: {device}", flush=True)

# 1. YOLO 模型 (僅用於提供 Box)
MODEL_PATH = BASE_DIR / "toybrick_top.pt"
try:
    print(f"[DEBUG] 開始加載 YOLO 模型: {MODEL_PATH}", flush=True)
    yolo_model = YOLO(str(MODEL_PATH))
    print("[DEBUG] YOLO 模型加載完成", flush=True)
except Exception as e:
    print(f"[ERROR] YOLO 模型加載失敗：{e}", flush=True)
    sys.exit(-1)

# 2. SAM 模型 (用於精細分割)
SAM_CHECKPOINT = BASE_DIR / "sam_vit_b_01ec64.pth"
try:
    print(f"[DEBUG] 開始加載 SAM 模型: {SAM_CHECKPOINT}", flush=True)
    sam = sam_model_registry["vit_b"](checkpoint=str(SAM_CHECKPOINT))
    sam.to(device=device)
    sam_predictor = SamPredictor(sam)
    print("[DEBUG] SAM 模型加載完成", flush=True)
except Exception as e:
    print(f"[ERROR] SAM 模型加載失敗：{e}", flush=True)
    sys.exit(-1)

def return_score(score):
    sys.exit(int(score))

# ================== 輔助函數 ==================

def get_sam_masks(frame, boxes):
    if len(boxes) == 0: return []
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    sam_predictor.set_image(img_rgb)
    sam_masks = []
    for box in boxes:
        masks, _, _ = sam_predictor.predict(box=np.array(box), multimask_output=False)
        sam_masks.append(masks[0])
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
if __name__ == "__main__":
    print("[DEBUG] ch1-t1 main.py 開始執行", flush=True)

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