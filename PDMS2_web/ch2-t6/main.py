# main.py — ch2-t6 兩點連線 AI 評分版 (Web 後端呼叫用)
import os
import sys
import cv2
import numpy as np
import torch
import segmentation_models_pytorch as smp
from skimage.morphology import skeletonize
from pathlib import Path

# --- 引入 get_cm1 的裁切功能 ---
from get_cm1 import perform_crop

# --- 1. 核心參數設定 ---
PIXEL_PER_CM = 100  # 100px = 1cm
BASE_DIR = Path(__file__).resolve().parent
LINE_MODEL_PATH = os.path.join(BASE_DIR, "best_model.pth")

def return_score(score: int):
    """將分數透過 exit code 傳回給後端系統"""
    sys.exit(int(score))

# --- 2. 核心判斷邏輯 ---
def get_red_line_skeleton(img, model, device):
    h, w = img.shape[:2]
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    full_mask = np.zeros((h, w), dtype=np.uint8)
    patch_size = 512

    for y in range(0, h, patch_size):
        for x in range(0, w, patch_size):
            y_end, x_end = min(y + patch_size, h), min(x + patch_size, w)
            patch = img_rgb[y:y_end, x:x_end]
            ph, pw = patch.shape[:2]
            input_p = np.zeros((512, 512, 3), dtype=np.uint8)
            input_p[:ph, :pw] = patch
            input_t = (torch.from_numpy(input_p).permute(2, 0, 1).float() / 255.0 - 
                       torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)) / torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
            with torch.no_grad():
                pred = model(input_t.unsqueeze(0).to(device))
                p_mask = (pred > 0.4).cpu().numpy().squeeze()
            full_mask[y:y_end, x:x_end] = (p_mask[:ph, :pw] * 255).astype(np.uint8)

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(full_mask)
    best_label = -1
    max_area = 0
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] > max_area and stats[i, cv2.CC_STAT_WIDTH] > 100:
            max_area = stats[i, cv2.CC_STAT_AREA]
            best_label = i
            
    if best_label == -1: return None, None
    line_mask = np.zeros_like(full_mask)
    line_mask[labels == best_label] = 1
    skel = skeletonize(line_mask).astype(np.uint8) * 255
    y_coords, x_coords = np.where(skel > 0)
    return list(zip(x_coords, y_coords)), skel

def get_two_dots_coords(img):
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, b_mask = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
    m_h, m_w = int(h * 0.1), int(w * 0.1)
    b_mask[:m_h, :] = 0
    b_mask[h-m_h:, :] = 0
    b_mask[:, :m_w] = 0
    b_mask[:, w-m_w:] = 0
    
    num, labels, stats, centroids = cv2.connectedComponentsWithStats(b_mask)
    candidates = []
    
    for i in range(1, num):
        area = stats[i, cv2.CC_STAT_AREA]
        sw = stats[i, cv2.CC_STAT_WIDTH]
        sh = stats[i, cv2.CC_STAT_HEIGHT]
        ratio = min(sw, sh) / max(sw, sh)
        if 400 < area < 8000 and ratio > 0.7:
            cx, cy = centroids[i]
            candidates.append({'pos': (int(cx), int(cy)), 'area': area})
            
    candidates = sorted(candidates, key=lambda x: x['area'], reverse=True)[:2]
    dots = sorted([c['pos'] for c in candidates], key=lambda d: d[0])
    return (dots[0], dots[1]) if len(dots) >= 2 else (None, None)

def point_to_segment_dist(px, py, dot1, dot2):
    x1, y1 = dot1
    x2, y2 = dot2
    dx, dy = x2 - x1, y2 - y1
    l2 = dx*dx + dy*dy
    if l2 == 0: return np.sqrt((px-x1)**2 + (py-y1)**2)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / l2))
    return np.sqrt((px - (x1 + t * dx))**2 + (py - (y1 + t * dy))**2)

# --- 3. 主程式：先裁切，再計分 ---
def main():
    if len(sys.argv) > 2:
        uid = sys.argv[1]
        img_id = sys.argv[2]
        
        # 定義原圖與裁切圖的絕對路徑
        origin_path = os.path.join(BASE_DIR.parent, "kid", uid, f"{img_id}.jpg")
        cropped_path = os.path.join(BASE_DIR.parent, "kid", uid, f"{img_id}_cropped.jpg")
    else:
        print("參數不足，用法：python main.py <uid> <img_id>", file=sys.stderr)
        return_score(-1)

    # 1. 呼叫 get_cm1 進行裁切
    print("開始執行 AI 裁切...")
    crop_success = perform_crop(origin_path, cropped_path)
    
    if not crop_success:
        print("裁切失敗，無法進行後續評分", file=sys.stderr)
        return_score(-1)

    # 2. 讀取裁切完成的圖片進行計分
    img = cv2.imread(cropped_path)
    if img is None:
        print(f"圖片讀取失敗：{cropped_path}", file=sys.stderr)
        return_score(-1)

    # 載入紅線計分 AI 模型
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = smp.Unet(encoder_name="resnet34", in_channels=3, classes=1, activation='sigmoid')
    
    if os.path.exists(LINE_MODEL_PATH):
        model.load_state_dict(torch.load(LINE_MODEL_PATH, map_location=device))
        model.to(device).eval()
    else:
        print(f"找不到紅線模型檔案：{LINE_MODEL_PATH}", file=sys.stderr)
        return_score(-1)

    # 分析邏輯
    red_points, skel_red = get_red_line_skeleton(img, model, device)
    dot1, dot2 = get_two_dots_coords(img)
    
    score = -1
    result_img = img.copy()

    if red_points and dot1 and dot2:
        pixel_dists = [point_to_segment_dist(x, y, dot1, dot2) for x, y in red_points]
        max_dist_cm = max(pixel_dists) / PIXEL_PER_CM
        
        score = 2 if max_dist_cm < 0.6 else (1 if max_dist_cm <= 1.2 else 0)
        
        cv2.line(result_img, dot1, dot2, (255, 255, 0), 3) 
        visible_skel = cv2.dilate(skel_red, np.ones((3, 3), np.uint8))
        result_img[visible_skel > 0] = [0, 255, 255] 
        cv2.putText(result_img, f"Score: {score} | Max: {max_dist_cm:.2f}cm", (50, 150), 
                    cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 255, 0), 5)
    else:
        print("偵測失敗：找不到紅線或兩點", file=sys.stderr)
        cv2.putText(result_img, "Detection Failed", (50, 150), 
                    cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 5)

    # 輸出結果
    result_dir = os.path.join(BASE_DIR.parent, "kid", uid)
    os.makedirs(result_dir, exist_ok=True)
    out_path = os.path.join(result_dir, f"{img_id}_result.jpg")
    
    cv2.imwrite(out_path, result_img)
    print(f"✅ 分析完成：{out_path} | 得分：{score}")
    
    return_score(score)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] ch2-t6 執行失敗: {e}", file=sys.stderr)
        return_score(-1)