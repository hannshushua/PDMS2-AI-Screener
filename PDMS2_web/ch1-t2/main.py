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

# 載入側視圖分析模組
try:
    from check_gap import CheckGap
    from MaskAnalyzer import MaskAnalyzer
    from StairChecker import StairChecker
    from PyramidChecker import PyramidCheck
    from LayerGrouping import LayerGrouping
except ImportError as e:
    print(f"[ERROR] 缺少側視圖分析模組：{e}")
    sys.exit(-1)

# ================== 模型與全域設定 ==================
device = "cuda" if torch.cuda.is_available() else "cpu"
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"
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

# 設定分析模式 (0=階梯, 1=金字塔)
MODE_SIDE = 1 

def return_score(score):
    sys.exit(int(score))

# ================== 通用 SAM 輔助函數 ==================
def get_sam_masks_from_boxes(frame, boxes):
    if len(boxes) == 0: return []
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    sam_predictor.set_image(img_rgb)
    
    sam_masks = []
    for box in boxes:
        m, _, _ = sam_predictor.predict(box=np.array(box), multimask_output=False)
        sam_masks.append(m[0])
    return sam_masks

# ================== ROI 裁切設定 (從 .env 載入) ==================
def _read_env_int(key, default=0):
    if not ENV_PATH.exists():
        return default
    try:
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            k, v = raw_line.split("=", 1)
            if k.strip() == key:
                return int(v.strip())
    except Exception:
        return default
    return default

TOP_ROI_X  = _read_env_int("PDMS2_ROI_X")
TOP_ROI_Y  = _read_env_int("PDMS2_ROI_Y")
TOP_ROI_W  = _read_env_int("PDMS2_ROI_W")
TOP_ROI_H  = _read_env_int("PDMS2_ROI_H")
SIDE_ROI_X = _read_env_int("PDMS2_SIDE_ROI_X")
SIDE_ROI_Y = _read_env_int("PDMS2_SIDE_ROI_Y")
SIDE_ROI_W = _read_env_int("PDMS2_SIDE_ROI_W")
SIDE_ROI_H = _read_env_int("PDMS2_SIDE_ROI_H")

# ================== 俯視圖 (TOP View) 分析 ==================
CONF_TOP = 0.8

def analyze_image_top(frame, initial_get_point=2):
    if TOP_ROI_W > 0 and TOP_ROI_H > 0:
        cropped = frame[TOP_ROI_Y:TOP_ROI_Y+TOP_ROI_H, TOP_ROI_X:TOP_ROI_X+TOP_ROI_W].copy()
    else:
        cropped = frame.copy()

    results = yolo_model.predict(source=cropped, conf=CONF_TOP, verbose=False)
    yolo_boxes = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes is not None else []
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
                # 角度判定邏輯
                edge1 = box[1] - box[0]
                edge2 = box[2] - box[1]
                angle = np.arctan2(edge1[1], edge1[0]) * 180 / np.pi if np.linalg.norm(edge1) > np.linalg.norm(edge2) else np.arctan2(edge2[1], edge2[0]) * 180 / np.pi
                angle = abs(angle) % 90
                rotate_ok = (angle <= 10 or angle >= 80)
                rotate_ok_list.append(rotate_ok)
                cv2.drawContours(cropped, [box], 0, (0, 255, 0) if rotate_ok else (0, 0, 255), 2)

    offset = False
    if len(centers) >= 2:
        threshold = max_mask_side // 8
        offset = np.std([p[0] for p in centers]) < threshold or np.std([p[1] for p in centers]) < threshold

    is_rotate_ng = not all(rotate_ok_list) if rotate_ok_list else False
    is_offset_ng = not offset
    if is_offset_ng or is_rotate_ng: GET_POINT = 1
    
    summary = f"{'Offset !' if is_offset_ng else 'No Offset'} | {'Rotate !' if is_rotate_ng else 'No Rotate'}"
    cv2.putText(cropped, summary, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255) if GET_POINT==1 else (0,0,0), 2)
    return cropped, summary, GET_POINT

# ================== 側視圖 (SIDE View) 分析 ==================
CONF_SIDE = 0.8
GAP_THRESHOLD_RATIO = 0.5

def analyze_image_side(img_path, model):
    frame = cv2.imread(img_path)
    if frame is None: raise ValueError(f"讀取圖片失敗：{img_path}")
    if SIDE_ROI_W > 0 and SIDE_ROI_H > 0:
        frame = frame[SIDE_ROI_Y:SIDE_ROI_Y+SIDE_ROI_H, SIDE_ROI_X:SIDE_ROI_X+SIDE_ROI_W].copy()

    annotated_frame = frame.copy()
    instance_mask_canvas = np.zeros_like(frame)

    results = model.predict(source=frame, conf=CONF_SIDE, verbose=False)
    yolo_boxes = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes is not None else []
    masks = get_sam_masks_from_boxes(frame, yolo_boxes)
    
    centroids = []
    SCORE = 2
    IS_GAP = False

    for i, mask in enumerate(masks):
        mask_uint8 = (mask * 255).astype(np.uint8)
        M = cv2.moments(mask_uint8)
        color = np.random.randint(0, 255, (3,)).tolist()
        
        annotated_frame[mask] = annotated_frame[mask] * 0.4 + np.array(color) * 0.6
        instance_mask_canvas[mask] = color

        if M["m00"] != 0:
            cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
            centroids.append((cx, cy))
            cv2.circle(annotated_frame, (int(cx), int(cy)), 10, (255, 255, 255), -1)
            cv2.putText(annotated_frame, f"{i}", (int(cx)-15, int(cy)-15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 3)

    avg_width = np.mean([b[2]-b[0] for b in yolo_boxes]) if len(yolo_boxes)>0 else 1.0
    GAP_THRESHOLD = GAP_THRESHOLD_RATIO * avg_width

    if len(centroids) >= 2:
        gap_checker = CheckGap(gap_threshold=GAP_THRESHOLD, y_layer_threshold=30)
        gap_pairs = gap_checker.check(centroids)
        if gap_pairs:
            IS_GAP = len(gap_pairs) // 2 == 3
            for pair in gap_pairs:
                p1, p2 = pair[0], pair[1]
                cv2.line(annotated_frame, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (0,0,255), 3)
            if MODE_SIDE == 0: SCORE = 1
        else:
            if MODE_SIDE == 1: SCORE = 1

    grouper = LayerGrouping(layer_ratio=0.3)
    layers = grouper.group_by_y(centroids, boxes=yolo_boxes)

    msg = "OK"
    if MODE_SIDE == 0:
        res, msg = StairChecker().check(layers)
        if not res: SCORE = 0
    elif MODE_SIDE == 1:
        avg_bw = avg_width // 2 if len(yolo_boxes)>0 else 0
        res, msg = PyramidCheck().check_pyramid(layers, avg_bw, IS_GAP)
        if not res: SCORE = 0

    score_text = f"Side Score: {SCORE}/2 | {msg}"
    cv2.putText(annotated_frame, score_text, (10, annotated_frame.shape[0] - 20), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

    return annotated_frame, instance_mask_canvas, SCORE

# ================== 主程式執行 ==================
if __name__ == "__main__":
    print("[DEBUG] ch1-t2 main.py 開始執行", flush=True)

    if len(sys.argv) <= 2:
        print("缺少參數 uid, img_id")
        sys.exit(-1)
        
    uid, img_id = sys.argv[1], sys.argv[2]
    
    SIDE_IMG_PATH = os.path.join("kid", uid, f"{img_id}-side.jpg")
    TOP_IMG_PATH = os.path.join("kid", uid, f"{img_id}-top.jpg")

    try:
        # 1. 側視圖分析
        print(f"[DEBUG] 分析側視圖: {SIDE_IMG_PATH}", flush=True)
        ann_side, mask_side, s_side = analyze_image_side(SIDE_IMG_PATH, yolo_model)
        
        # 儲存側視圖結果 (合併原圖遮罩與純遮罩)
        combined_side = np.hstack((cv2.resize(ann_side, (0,0), fx=0.5, fy=0.5), 
                                  cv2.resize(mask_side, (0,0), fx=0.5, fy=0.5)))
        side_res_path = os.path.join("kid", uid, f"{img_id}-side_result.jpg")
        cv2.imwrite(side_res_path, combined_side)
        
        # 2. 俯視圖分析
        print(f"[DEBUG] 分析俯視圖: {TOP_IMG_PATH}", flush=True)
        raw_top = cv2.imread(TOP_IMG_PATH)
        if raw_top is None: raise ValueError("讀取俯視圖失敗")
        
        ann_top, sum_top, s_top = analyze_image_top(raw_top)
        top_res_path = os.path.join("kid", uid, f"{img_id}-top_result.jpg")
        cv2.imwrite(top_res_path, ann_top)

        # 3. 最終最低分計分
        final_score = min([s for s in [s_side, s_top] if s != -1])
        print(f"Side: {s_side}, Top: {s_top} -> Final Score: {final_score}")
        print("[DEBUG] ch1-t2 main.py 執行完成", flush=True)
        return_score(final_score)
        
    except Exception as e:
        print(f"[ERROR] 執行出錯: {e}")
        import traceback
        traceback.print_exc()
        return_score(-1)