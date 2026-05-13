# main.py — ch2-t6 兩點連線 AI 評分版 (Web 後端呼叫用)
import os
import sys
import cv2
import numpy as np
import torch
import segmentation_models_pytorch as smp
from skimage.morphology import skeletonize
from pathlib import Path

from get_cm1 import perform_crop

BASE_DIR = Path(__file__).resolve().parent
LINE_MODEL_PATH = os.path.join(BASE_DIR, "best_model.pth")
PIXEL_PER_CM = 100  # 裁切後 100px = 1cm

def return_score(score: int):
    sys.exit(int(score))

def get_red_line_skeleton(img, model, device):
    h, w = img.shape[:2]
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    full_mask = np.zeros((h, w), dtype=np.uint8)
    patch_size = 512

    for y in range(0, h, patch_size):
        for x in range(0, w, patch_size):
            y_end = min(y + patch_size, h)
            x_end = min(x + patch_size, w)
            patch = img_rgb[y:y_end, x:x_end]
            ph, pw = patch.shape[:2]

            input_p = np.zeros((512, 512, 3), dtype=np.uint8)
            input_p[:ph, :pw] = patch
            input_t = (
                torch.from_numpy(input_p).permute(2, 0, 1).float() / 255.0
                - torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
            ) / torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)

            with torch.no_grad():
                pred = model(input_t.unsqueeze(0).to(device))
                p_mask = (pred > 0.4).cpu().numpy().squeeze()

            full_mask[y:y_end, x:x_end] = (p_mask[:ph, :pw] * 255).astype(np.uint8)

    num, labels, stats, _ = cv2.connectedComponentsWithStats(full_mask)
    best_label, max_area = -1, 0
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] > max_area and stats[i, cv2.CC_STAT_WIDTH] > 100:
            max_area = stats[i, cv2.CC_STAT_AREA]
            best_label = i

    if best_label == -1:
        return None, None

    line_mask = np.zeros_like(full_mask)
    line_mask[labels == best_label] = 1
    skel = skeletonize(line_mask).astype(np.uint8) * 255
    y_coords, x_coords = np.where(skel > 0)
    return list(zip(x_coords, y_coords)), skel

def get_two_dots_coords(img):
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, b_mask = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

    # 排除四周 10% 邊緣（紙張邊界陰影）
    m_h, m_w = int(h * 0.1), int(w * 0.1)
    b_mask[:m_h, :] = 0
    b_mask[h - m_h:, :] = 0
    b_mask[:, :m_w] = 0
    b_mask[:, w - m_w:] = 0

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
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return np.sqrt((px - x1) ** 2 + (py - y1) ** 2)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / l2))
    return np.sqrt((px - (x1 + t * dx)) ** 2 + (py - (y1 + t * dy)) ** 2)

def main():
    if len(sys.argv) < 3:
        print("用法：python main.py <uid> <img_id>", file=sys.stderr)
        return_score(0)

    uid = sys.argv[1]
    img_id = sys.argv[2]

    origin_path = os.path.join(BASE_DIR.parent, "kid", uid, f"{img_id}.jpg")
    cropped_path = os.path.join(BASE_DIR.parent, "kid", uid, f"{img_id}_cropped.jpg")
    result_path = os.path.join(BASE_DIR.parent, "kid", uid, f"{img_id}_result.jpg")

    # 1. AI 紙張裁切
    print("開始 AI 紙張裁切...")
    if not perform_crop(origin_path, cropped_path):
        print("裁切失敗", file=sys.stderr)
        return_score(0)

    img = cv2.imread(cropped_path)
    if img is None:
        print(f"裁切圖讀取失敗：{cropped_path}", file=sys.stderr)
        return_score(0)

    # 2. 載入紅線模型
    if not os.path.exists(LINE_MODEL_PATH):
        print(f"找不到紅線模型：{LINE_MODEL_PATH}", file=sys.stderr)
        return_score(0)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = smp.Unet(encoder_name="resnet34", in_channels=3, classes=1, activation='sigmoid')
    model.load_state_dict(torch.load(LINE_MODEL_PATH, map_location=device))
    model.to(device).eval()

    # 3. 偵測紅線骨架與兩個黑點
    red_points, skel_red = get_red_line_skeleton(img, model, device)
    dot1, dot2 = get_two_dots_coords(img)

    score = 0
    result_img = img.copy()

    if red_points and dot1 and dot2:
        pixel_dists = [point_to_segment_dist(x, y, dot1, dot2) for x, y in red_points]
        max_dist_cm = max(pixel_dists) / PIXEL_PER_CM

        # PDMS-2 Item 67 評分標準
        score = 2 if max_dist_cm < 0.6 else (1 if max_dist_cm <= 1.2 else 0)

        # 畫出結果
        cv2.line(result_img, dot1, dot2, (255, 255, 0), 4)
        visible_skel = cv2.dilate(skel_red, np.ones((3, 3), np.uint8))
        result_img[visible_skel > 0] = [0, 255, 255]
        cv2.putText(
            result_img,
            f"Score: {score} | Max: {max_dist_cm:.2f}cm",
            (50, 150),
            cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 255, 0), 5
        )
    else:
        print("偵測失敗：找不到紅線或兩個點", file=sys.stderr)
        cv2.putText(
            result_img,
            "Detection Failed",
            (50, 150),
            cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 5
        )

    cv2.imwrite(result_path, result_img)
    print(f"結果圖已儲存：{result_path} | 得分：{score}")
    return_score(score)

if __name__ == "__main__":
    main()
