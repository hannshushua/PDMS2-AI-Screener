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

# ================== 模型與環境設定 ==================
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

def return_score(score):
    sys.exit(int(score))

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

# ================== 通用 SAM 輔助函數 ==================
def get_sam_masks_from_boxes(frame, boxes):
    """ 根據 YOLO 的 boxes 使用 SAM 生成高品質 Mask """
    if len(boxes) == 0: return []
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    sam_predictor.set_image(img_rgb)
    
    sam_masks = []
    for box in boxes:
        m, _, _ = sam_predictor.predict(box=np.array(box), multimask_output=False)
        sam_masks.append(m[0])
    return sam_masks

# ================== 俯視圖 (TOP View) 分析 ==================
CONF_TOP = 0.6

def analyze_image_top(frame, model):
    if TOP_ROI_W > 0 and TOP_ROI_H > 0:
        cropped = frame[TOP_ROI_Y:TOP_ROI_Y+TOP_ROI_H, TOP_ROI_X:TOP_ROI_X+TOP_ROI_W].copy()
    else:
        cropped = frame.copy()

    results = model.predict(source=cropped, conf=CONF_TOP, verbose=False)
    yolo_boxes = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes is not None else []
    
    masks = get_sam_masks_from_boxes(cropped, yolo_boxes)
    centers = []
    max_mask_side = 0
    rotate_ok_list = []
    GET_POINT = 2

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
                edge1, edge2 = box[1] - box[0], box[2] - box[1]
                angle = np.arctan2(edge1[1], edge1[0]) * 180 / np.pi if np.linalg.norm(edge1) > np.linalg.norm(edge2) else np.arctan2(edge2[1], edge2[0]) * 180 / np.pi
                angle_diff = abs(angle) % 90
                rotate_ok = (angle_diff <= 10 or angle_diff >= 80)
                rotate_ok_list.append(rotate_ok)
                cv2.drawContours(cropped, [box], 0, (0, 255, 0) if rotate_ok else (0, 0, 255), 2)

    offset = False
    if len(centers) >= 2:
        threshold = max_mask_side // 8
        offset = np.std([p[0] for p in centers]) < threshold or np.std([p[1] for p in centers]) < threshold

    is_rotate_ng = not all(rotate_ok_list) if rotate_ok_list else False
    if not offset or is_rotate_ng: GET_POINT = 1
    
    summary = f"{'Offset !' if not offset else 'No Offset'} | {'Rotate !' if is_rotate_ng else 'No Rotate'}"
    cv2.putText(cropped, summary, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0,0,255) if GET_POINT==1 else (0,0,0), 3)
    return cropped, summary, GET_POINT

# ================== 側視圖 (SIDE View) 分析 ==================
CONF_SIDE = 0.7
GAP_RATIO = 0.9

def analyze_image_side(IMG_PATH, model):
    frame = cv2.imread(IMG_PATH)
    if frame is None: raise ValueError("讀圖失敗")
    if SIDE_ROI_W > 0 and SIDE_ROI_H > 0:
        frame = frame[SIDE_ROI_Y:SIDE_ROI_Y+SIDE_ROI_H, SIDE_ROI_X:SIDE_ROI_X+SIDE_ROI_W].copy()
    frame = cv2.convertScaleAbs(frame, alpha=1.4, beta=10)
    annotated = frame.copy()
    
    results = model.predict(source=frame, conf=CONF_SIDE, verbose=False)
    yolo_boxes = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes is not None else []
    masks = get_sam_masks_from_boxes(frame, yolo_boxes)
    
    centroids = []
    for i, mask in enumerate(masks):
        mask_uint8 = (mask * 255).astype(np.uint8)
        M = cv2.moments(mask_uint8)
        color = np.random.randint(0, 255, (3,)).tolist()
        annotated[mask] = annotated[mask] * 0.4 + np.array(color) * 0.6
        if M["m00"] != 0:
            cx, cy = M["m10"]/M["m00"], M["m01"]/M["m00"]
            centroids.append((cx, cy))
            cv2.circle(annotated, (int(cx), int(cy)), 8, (255, 255, 255), -1)
            cv2.putText(annotated, f"ID:{i}", (int(cx), int(cy)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

    if len(yolo_boxes) != 4:
        cv2.putText(annotated, f"NG: Found {len(yolo_boxes)} blocks", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,255), 3)
        return annotated, 0

    # 自動分層
    sorted_items = sorted(enumerate(centroids), key=lambda x: x[1][1])
    avg_h = np.mean([b[3]-b[1] for b in yolo_boxes])
    layer_threshold = avg_h * 0.3
    layers = []
    current_layer = [sorted_items[0]]
    for i in range(1, len(sorted_items)):
        if abs(sorted_items[i][1][1] - current_layer[-1][1][1]) < layer_threshold:
            current_layer.append(sorted_items[i])
        else:
            layers.append(current_layer)
            current_layer = [sorted_items[i]]
    layers.append(current_layer)

    if len(layers) != 2 or any(len(l) != 2 for l in layers):
        cv2.putText(annotated, "NG: Layering Error", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,255), 3)
        return annotated, 0

    # 空隙檢查與繪圖
    l1_idx, l2_idx = [x[0] for x in layers[0]], [x[0] for x in layers[1]]
    p1_a, p1_b = centroids[l1_idx[0]], centroids[l1_idx[1]]
    p2_a, p2_b = centroids[l2_idx[0]], centroids[l2_idx[1]]
    
    l1_gap, l2_gap = abs(p1_a[0]-p1_b[0]), abs(p2_a[0]-p2_b[0])
    avg_w = np.mean([b[2]-b[0] for b in yolo_boxes])
    gap_threshold = avg_w * GAP_RATIO
    l1_has, l2_has = l1_gap > gap_threshold, l2_gap > gap_threshold

    if l1_has:
        cv2.line(annotated, (int(p1_a[0]), int(p1_a[1])), (int(p1_b[0]), int(p1_b[1])), (0,0,255), 5)
        cv2.putText(annotated, "GAP", (int((p1_a[0]+p1_b[0])/2), int((p1_a[1]+p1_b[1])/2)-10), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,255), 3)
    if l2_has:
        cv2.line(annotated, (int(p2_a[0]), int(p2_a[1])), (int(p2_b[0]), int(p2_b[1])), (0,0,255), 5)
        cv2.putText(annotated, "GAP", (int((p2_a[0]+p2_b[0])/2), int((p2_a[1]+p2_b[1])/2)-10), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,255), 3)

    SCORE = 1 if (l1_has or l2_has) else 2
    cv2.putText(annotated, f"{'GAP' if SCORE==1 else 'NO GAP'} | Score: {SCORE}/2", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,0) if SCORE==2 else (0,165,255), 3)
    return annotated, SCORE

# ================== Main 執行區塊 ==================
if __name__ == "__main__":
    print("[DEBUG] ch1-t4 main.py 開始執行", flush=True)
    if len(sys.argv) > 2:
        uid, img_id = sys.argv[1], sys.argv[2]
        SIDE_PATH = os.path.join("kid", uid, f"{img_id}-side.jpg")
        TOP_PATH = os.path.join("kid", uid, f"{img_id}-top.jpg")
    else:
        print("缺少參數 uid, img_id", flush=True); sys.exit(-1)

    try:
        print(f"[DEBUG] 分析側視圖: {SIDE_PATH}", flush=True)
        ann_side, s_side = analyze_image_side(SIDE_PATH, yolo_model)
        cv2.imwrite(os.path.join("kid", uid, f"{img_id}-side_result.jpg"), ann_side)
        
        print(f"[DEBUG] 分析俯視圖: {TOP_PATH}", flush=True)
        frame_top = cv2.imread(TOP_PATH)
        ann_top, _, s_top = analyze_image_top(frame_top, yolo_model)
        cv2.imwrite(os.path.join("kid", uid, f"{img_id}-top_result.jpg"), ann_top)

        final = min([s for s in [s_side, s_top] if s != -1])
        print(f"Final Score: {final}", flush=True)
        return_score(final)
    except Exception as e:
        print(f"[ERROR] 執行失敗: {e}", flush=True); return_score(-1)