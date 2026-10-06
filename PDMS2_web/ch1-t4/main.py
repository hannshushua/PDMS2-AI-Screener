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

# ================== 模型與環境設定 ==================
device = "cuda" if torch.cuda.is_available() else "cpu"
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"
TOP_MODEL_PATH = BASE_DIR.parent / "models" / "cube_top.pt"    # 俯視圖模型
SIDE_MODEL_PATH = BASE_DIR.parent / "models" / "cube_side.pt"  # 側視圖模型
SAM_CHECKPOINT = BASE_DIR.parent / "models" / "sam2_b.pt"

print(f"[DEBUG] 目前使用設備: {device}", flush=True)

# 初始化 YOLO
try:
    print(f"[DEBUG] 開始加載 YOLO 模型: top={TOP_MODEL_PATH} side={SIDE_MODEL_PATH}", flush=True)
    yolo_top = YOLO(str(TOP_MODEL_PATH))
    yolo_side = YOLO(str(SIDE_MODEL_PATH))
    print("[DEBUG] YOLO 模型加載完成", flush=True)
except Exception as e:
    print(f"[ERROR] YOLO 模型加載失敗：{e}", flush=True)
    sys.exit(-1)

# 初始化 SAM2 (ultralytics)
try:
    print(f"[DEBUG] 開始加載 SAM2 模型: {SAM_CHECKPOINT}", flush=True)
    sam_model = SAM(str(SAM_CHECKPOINT))
    print("[DEBUG] SAM2 模型加載完成", flush=True)
except Exception as e:
    print(f"[ERROR] SAM2 模型加載失敗：{e}", flush=True)
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

# ================== 俯視圖 (TOP View) 分析 ==================
CONF_TOP = 0.75

# OFFSET_RATIO：判定「排列有對齊」的容忍度，相對於積木最長邊。
# 中心點在 X 或 Y 其中一軸的標準差小於「積木最長邊 x 此比例」就算對齊。
# 數值越大越寬鬆（原本寫死 1/8 = 0.125，對 3 歲小朋友太嚴）
OFFSET_RATIO = 0.25

def analyze_image_top(frame, model):
    # === 暫時停用俯視圖 ROI 裁切，直接分析整張原圖 ===
    # 要恢復裁切：把下面四行的註解拿掉，並移除 cropped = frame.copy()
    # if TOP_ROI_W > 0 and TOP_ROI_H > 0:
    #     cropped = frame[TOP_ROI_Y:TOP_ROI_Y+TOP_ROI_H, TOP_ROI_X:TOP_ROI_X+TOP_ROI_W].copy()
    # else:
    #     cropped = frame.copy()
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

    # === 暫時停用 offset(對齊) 判斷，只保留旋轉判斷 ===
    # offset = False
    # if len(centers) >= 2:
    #     threshold = max_mask_side * OFFSET_RATIO
    #     std_x = np.std([p[0] for p in centers])
    #     std_y = np.std([p[1] for p in centers])
    #     offset = std_x < threshold or std_y < threshold
    # print(f"[DEBUG] offset 檢查：積木最長邊={max_mask_side}, 容忍門檻={threshold:.2f} ({OFFSET_RATIO} 邊長), std_x={std_x:.2f}, std_y={std_y:.2f} -> {'對齊 OK' if offset else 'Offset NG'}", flush=True)
    offset = True  # 停用中：一律視為對齊合格

    is_rotate_ng = not all(rotate_ok_list) if rotate_ok_list else False
    # if not offset or is_rotate_ng: GET_POINT = 1
    if is_rotate_ng: GET_POINT = 1
    
    # summary = f"{'Offset !' if not offset else 'No Offset'} | {'Rotate !' if is_rotate_ng else 'No Rotate'}"
    summary = f"{'Rotate !' if is_rotate_ng else 'No Rotate'}"
    cv2.putText(cropped, summary, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0,0,255) if GET_POINT==1 else (0,0,0), 3)
    return cropped, summary, GET_POINT

# ================== 側視圖 (SIDE View) 分析 ==================
CONF_SIDE = 0.75
# GAP_RATIO：縫隙需超過積木寬度的幾成才算「有縫隙」，數值越大越不敏感
# 注意：本關有縫隙會扣分，此值調低會變嚴格（與 ch1-t2/t3 統一為 0.08）
GAP_RATIO = 0.08

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

    if not centroids:
        cv2.putText(annotated, "NG: No valid mask", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,255), 3)
        return annotated, 0

    # 自動分層
    sorted_items = sorted(enumerate(centroids), key=lambda x: x[1][1])
    avg_h = np.mean([b[3]-b[1] for b in yolo_boxes])
    layer_threshold = avg_h * 0.5
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
    
    # 用中位數而非平均，避免單一個偵測歪掉的框拉走整體寬度
    avg_w = np.median([b[2]-b[0] for b in yolo_boxes])
    # 中心點距離要扣掉一個積木寬度，才是真正的縫隙寬度
    l1_gap = abs(p1_a[0]-p1_b[0]) - avg_w
    l2_gap = abs(p2_a[0]-p2_b[0]) - avg_w
    gap_threshold = avg_w * GAP_RATIO
    l1_has, l2_has = l1_gap > gap_threshold, l2_gap > gap_threshold
    print(f"[DEBUG] 積木寬度: {avg_w:.2f}, 縫隙閾值: {gap_threshold:.2f} ({GAP_RATIO:.2f} W) | L1 縫隙: {l1_gap:.2f} ({l1_gap/avg_w:.2f} W), L2 縫隙: {l2_gap:.2f} ({l2_gap/avg_w:.2f} W)", flush=True)

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
    print("[DEBUG] ch1-t4 main.py 開始執行", flush=True)
    # ===== 測試模式：python main.py --test <側視圖> [俯視圖] =====
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "-t"):
        if len(sys.argv) < 3:
            print("用法：python main.py --test <側視圖路徑> [俯視圖路徑]", flush=True)
            sys.exit(-1)
        side_path = sys.argv[2]
        top_path = sys.argv[3] if len(sys.argv) > 3 else None

        print(f"[TEST] 分析側視圖：{side_path}", flush=True)
        ann_side, s_side = analyze_image_side(side_path, yolo_side)
        print(f"[TEST] 側視圖得分：{s_side}", flush=True)
        _show_result(f"ch1-t4 side  score={s_side}", ann_side, _result_path(side_path))

        if top_path:
            print(f"[TEST] 分析俯視圖：{top_path}", flush=True)
            frame_top = cv2.imread(top_path)
            if frame_top is None:
                print(f"[TEST] 讀不到俯視圖：{top_path}", flush=True)
            else:
                ann_top, _, s_top = analyze_image_top(frame_top, yolo_top)
                print(f"[TEST] 俯視圖得分：{s_top}", flush=True)
                _show_result(f"ch1-t4 top  score={s_top}", ann_top, _result_path(top_path))
        sys.exit(0)

    if len(sys.argv) > 2:
        uid, img_id = sys.argv[1], sys.argv[2]
        SIDE_PATH = os.path.join("kid", uid, f"{img_id}-side.jpg")
        TOP_PATH = os.path.join("kid", uid, f"{img_id}-top.jpg")
    else:
        print("缺少參數 uid, img_id", flush=True); sys.exit(-1)

    try:
        print(f"[DEBUG] 分析側視圖: {SIDE_PATH}", flush=True)
        ann_side, s_side = analyze_image_side(SIDE_PATH, yolo_side)
        cv2.imwrite(os.path.join("kid", uid, f"{img_id}-side_result.jpg"), ann_side)
        
        print(f"[DEBUG] 分析俯視圖: {TOP_PATH}", flush=True)
        frame_top = cv2.imread(TOP_PATH)
        ann_top, _, s_top = analyze_image_top(frame_top, yolo_top)
        cv2.imwrite(os.path.join("kid", uid, f"{img_id}-top_result.jpg"), ann_top)

        final = min([s for s in [s_side, s_top] if s != -1])
        print(f"Final Score: {final}", flush=True)
        return_score(final)
    except Exception as e:
        print(f"[ERROR] 執行失敗: {e}", flush=True); return_score(-1)