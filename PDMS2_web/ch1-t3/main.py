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
import os
import sys
from pathlib import Path
from segment_anything import sam_model_registry, SamPredictor

# 載入側視圖分析所需模組
try:
    from check_gap import CheckGap
    from MaskAnalyzer import MaskAnalyzer
    from StairChecker import StairChecker
    from PyramidChecker import PyramidCheck
    from LayerGrouping import LayerGrouping
except ImportError as e:
    print(f"[ERROR] 缺少側視圖分析所需的模組：{e}")
    sys.exit(-1)

# ================== 模型與環境設定 ==================
device = "cuda" if torch.cuda.is_available() else "cpu"
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "toybrick_side.pt"
SAM_CHECKPOINT = BASE_DIR / "sam_vit_b_01ec64.pth" 
SAM_TYPE = "vit_b"

print(f"[DEBUG] 目前使用設備: {device}", flush=True)

# 初始化 YOLO
try:
    print(f"[DEBUG] 開始加載 YOLO 模型: {MODEL_PATH}", flush=True)
    yolo_model = YOLO(str(MODEL_PATH))
    print("[DEBUG] YOLO 模型加載完成", flush=True)
except Exception as e:
    print(f"[ERROR] YOLO 模型加載失敗：{e}", flush=True)
    sys.exit(-1)

# 初始化 SAM
try:
    print(f"[DEBUG] 開始加載 SAM 模型: {SAM_CHECKPOINT}", flush=True)
    sam = sam_model_registry[SAM_TYPE](checkpoint=str(SAM_CHECKPOINT)).to(device)
    sam_predictor = SamPredictor(sam)
    print("[DEBUG] SAM 模型加載完成", flush=True)
except Exception as e:
    print(f"[ERROR] SAM 模型加載失敗：{e}", flush=True)
    sys.exit(-1)

MODE_SIDE = 0  # 0 = 階梯, 1 = 金字塔

def return_score(score):
    sys.exit(int(score))

# ================== 通用 SAM 輔助函數 ==================
def get_sam_masks_from_boxes(frame, boxes):
    """ 根據 YOLO 的 boxes 使用 SAM 生成高品質 Mask """
    if len(boxes) == 0: return []
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    sam_predictor.set_image(img_rgb)
    
    sam_masks = []
    for box in boxes:
        # box 格式 [x1, y1, x2, y2]
        m, _, _ = sam_predictor.predict(box=np.array(box), multimask_output=False)
        sam_masks.append(m[0])
    return sam_masks

# ================== 俯視圖 (TOP View) 分析 ==================
CONF_TOP = 0.8
CROP_RATIO = 0.5

def analyze_image_top(frame, model, initial_get_point=2):
    H, W = frame.shape[:2]
    crop_w, crop_h = int(W * CROP_RATIO), int(H * CROP_RATIO)
    x1, y1 = (W - crop_w) // 2, (H - crop_h) // 2
    cropped = frame[y1:y1+crop_h, x1:x1+crop_w].copy()

    results = model.predict(source=cropped, conf=CONF_TOP, verbose=False)
    yolo_boxes = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes is not None else []
    
    # 使用 SAM 優化分割
    masks = get_sam_masks_from_boxes(cropped, yolo_boxes)

    centers = []
    max_mask_side = 0
    rotate_ok_list = []
    GET_POINT = initial_get_point

    for mask in masks:
        binary_mask = (mask * 255).astype(np.uint8)
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            if cv2.contourArea(cnt) < 300: continue
            x, y, w, h = cv2.boundingRect(cnt)
            max_mask_side = max(max_mask_side, max(w, h))

            M = cv2.moments(cnt)
            if M["m00"] != 0:
                cx, cy = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                centers.append((cx, cy))
                cv2.circle(cropped, (cx, cy), 5, (0, 0, 0), -1)

            if len(cnt) >= 5:
                rect = cv2.minAreaRect(cnt)
                box = np.intp(cv2.boxPoints(rect))
                edge1 = box[1] - box[0]
                edge2 = box[2] - box[1]
                angle = np.arctan2(edge1[1], edge1[0]) * 180 / np.pi if np.linalg.norm(edge1) > np.linalg.norm(edge2) else np.arctan2(edge2[1], edge2[0]) * 180 / np.pi
                
                angle_diff = abs(angle) % 90
                rotate_ok = (angle_diff <= 10 or angle_diff >= 80)
                rotate_ok_list.append(rotate_ok)
                cv2.drawContours(cropped, [box], 0, (0, 255, 0) if rotate_ok else (0, 0, 255), 2)

    offset = False
    if len(centers) >= 2 and max_mask_side > 0:
        threshold = max_mask_side // 8
        offset = np.std([p[0] for p in centers]) < threshold or np.std([p[1] for p in centers]) < threshold

    is_rotate_ng = not all(rotate_ok_list) if rotate_ok_list else False
    is_offset_ng = not offset
    if is_offset_ng or is_rotate_ng: GET_POINT = 1
    
    summary = f"{'Offset !' if is_offset_ng else 'No Offset'} | {'Rotate !' if is_rotate_ng else 'No Rotate'}"
    cv2.putText(cropped, summary, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0,0,255) if GET_POINT==1 else (0,0,0), 3)
    return cropped, summary, GET_POINT

# ================== 側視圖 (SIDE View) 分析 ==================
CONF_SIDE = 0.8
GAP_THRESHOLD_RATIO = 1.05

def analyze_image_side(img_path, model):
    frame = cv2.imread(img_path)
    if frame is None: raise ValueError(f"讀不到圖片：{img_path}")
    frame = cv2.flip(frame, 1) # 左右翻面

    annotated = frame.copy()
    instance_mask_canvas = np.zeros_like(frame)

    results = model.predict(source=frame, conf=CONF_SIDE, verbose=False)
    yolo_boxes = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes is not None else []
    
    # 使用 SAM 精細分割
    masks = get_sam_masks_from_boxes(frame, yolo_boxes)
    
    centroids = []
    SCORE = 2
    IS_GAP = False

    for i, mask in enumerate(masks):
        mask_uint8 = (mask * 255).astype(np.uint8)
        M = cv2.moments(mask_uint8)
        color = np.random.randint(0, 255, (3,)).tolist()
        
        # 繪製半透明遮罩與純遮罩圖
        annotated[mask] = annotated[mask] * 0.4 + np.array(color) * 0.6
        instance_mask_canvas[mask] = color

        if M["m00"] != 0:
            cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
            centroids.append((cx, cy))
            cv2.circle(annotated, (int(cx), int(cy)), 10, (255, 255, 255), -1)

    # 結構判斷 (使用精確的質心)
    avg_w = np.mean([b[2]-b[0] for b in yolo_boxes]) if len(yolo_boxes) > 0 else 1.0
    gap_checker = CheckGap(gap_threshold=GAP_THRESHOLD_RATIO*avg_w, y_layer_threshold=15)
    gap_pairs = gap_checker.check(centroids)
    
    if gap_pairs:
        IS_GAP = True
        for p1, p2, _ in gap_pairs:
            cv2.line(annotated, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (0,0,255), 3)
        if MODE_SIDE == 0: SCORE = 1
    else:
        if MODE_SIDE == 1: SCORE = 1

    layers = LayerGrouping(layer_ratio=0.3).group_by_y(centroids, boxes=yolo_boxes)
    
    msg = "OK"
    if MODE_SIDE == 0:
        res, msg = StairChecker().check(layers)
        if not res: SCORE = 0
    else:
        res, msg = PyramidCheck().check_pyramid(layers, avg_w//2, IS_GAP)
        if not res: SCORE = 0

    cv2.putText(annotated, f"Score: {SCORE}/2 | {msg}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    
    # 水平合併結果圖 (原圖+遮罩 | 純實例遮罩)
    combined = np.hstack((cv2.resize(annotated, (0,0), fx=0.5, fy=0.5), 
                          cv2.resize(instance_mask_canvas, (0,0), fx=0.5, fy=0.5)))
    return combined, SCORE

# ================== 主程式執行區塊 ==================
if __name__ == "__main__":
    print("[DEBUG] ch1-t3 main.py 開始執行", flush=True)

    if len(sys.argv) <= 2:
        print("缺少參數 uid, img_id")
        sys.exit(-1)
        
    uid, img_id = sys.argv[1], sys.argv[2]
    SIDE_IMG_PATH = os.path.join("kid", uid, f"{img_id}-side.jpg")
    TOP_IMG_PATH = os.path.join("kid", uid, f"{img_id}-top.jpg")

    try:
        # 1. 執行側視圖分析
        print(f"[DEBUG] 分析側視圖: {SIDE_IMG_PATH}", flush=True)
        result_side, s_side = analyze_image_side(SIDE_IMG_PATH, yolo_model)
        side_res_path = os.path.join("kid", uid, f"{img_id}-side_result.jpg")
        cv2.imwrite(side_res_path, result_side)
        print(f"側視圖得分: {s_side}")

        # 2. 執行俯視圖分析
        print(f"[DEBUG] 分析俯視圖: {TOP_IMG_PATH}", flush=True)
        frame_top = cv2.imread(TOP_IMG_PATH)
        if frame_top is None: raise ValueError("讀取俯視圖失敗")
        
        result_top, summary, s_top = analyze_image_top(frame_top, yolo_model)
        top_res_path = os.path.join("kid", uid, f"{img_id}-top_result.jpg")
        cv2.imwrite(top_res_path, result_top)
        print(f"俯視圖得分: {s_top}")

        # 3. 輸出最終計分
        final_score = min([s for s in [s_side, s_top] if s != -1])
        print(f"最終最低得分：{final_score}")
        print("[DEBUG] ch1-t3 main.py 執行完成", flush=True)
        return_score(final_score)
        
    except Exception as e:
        print(f"[ERROR] 執行出錯: {e}")
        import traceback
        traceback.print_exc()
        return_score(-1)