# main.py — ch2-t4 描水平線 AI 評分版 (Web 後端呼叫用)
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
PIXEL_PER_CM = 100        # AI 裁切後固定 100px = 1cm
DEVIATION_THRESHOLD = 0.1  # 偏離超過 0.1cm 算一次事件

def return_score(score: int):
    sys.exit(int(score))

def get_red_line_data(img, model, device):
    """滑動視窗偵測紅線，選最寬最扁的連通元件後骨架化"""
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

    # sw*(sw/sh) 打分：選最寬最扁的（水平線特徵）
    num, labels, stats, _ = cv2.connectedComponentsWithStats(full_mask, connectivity=8)
    best_label, max_score = -1, 0
    for i in range(1, num):
        x_s, y_s, sw, sh, area = stats[i]
        score = sw * (sw / (sh + 1))
        if score > max_score and sw > 150:
            max_score = score
            best_label = i

    if best_label == -1:
        return None, None

    line_mask = np.zeros_like(full_mask)
    line_mask[labels == best_label] = 1
    skel = skeletonize(line_mask).astype(np.uint8) * 255
    y_coords, x_coords = np.where(skel > 0)
    return list(zip(x_coords, y_coords)), skel

def get_filtered_black_y(img):
    """在畫面中心 ROI 找印刷黑色基準線的 y 座標"""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    roi_top, roi_bottom = h // 4, 3 * h // 4
    roi = gray[roi_top:roi_bottom, :]

    _, b_mask = cv2.threshold(roi, 50, 255, cv2.THRESH_BINARY_INV)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(b_mask, connectivity=8)

    best_y, max_w = None, 0
    for i in range(1, num):
        x, y, sw, sh, area = stats[i]
        if sw > max_w and sw > 4 * sh:
            max_w = sw
            best_y = y + sh / 2 + roi_top

    return best_y

def evaluate_pdms2(red_points, y_black):
    """
    PDMS-2 評分邏輯：
    2分：偏離次數 <= 2 且最大偏離 < 1.2cm
    1分：偏離次數 3-4 次，或 2 次但距離過大
    0分：偏離次數 > 4 次
    """
    if not red_points:
        return 0, 0, 0

    dists = [abs(y - y_black) / PIXEL_PER_CM for x, y in red_points]
    max_dist = max(dists)

    dev_count = 0
    is_deviating = False
    for d in dists:
        if d > DEVIATION_THRESHOLD:
            if not is_deviating:
                dev_count += 1
                is_deviating = True
        else:
            is_deviating = False

    if dev_count > 4:
        score = 0
    elif 3 <= dev_count <= 4:
        score = 1
    elif dev_count <= 2 and max_dist < 1.2:
        score = 2
    else:
        score = 1

    return score, dev_count, max_dist

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

    # 3. 偵測紅線與黑色基準線
    red_points, skel_red = get_red_line_data(img, model, device)
    y_black = get_filtered_black_y(img)

    score = 0
    result_img = img.copy()

    if red_points and y_black is not None:
        score, dev_count, max_dist = evaluate_pdms2(red_points, y_black)

        visible_skel = cv2.dilate(skel_red, np.ones((3, 3), np.uint8))
        result_img[visible_skel > 0] = [0, 255, 255]
        cv2.line(result_img, (0, int(y_black)), (img.shape[1], int(y_black)), (255, 255, 0), 3)
        cv2.putText(
            result_img,
            f"Score: {score} | Devs: {dev_count} | Max: {max_dist:.2f}cm",
            (50, 150),
            cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 255, 0), 5
        )
    else:
        print("偵測失敗：找不到紅線或基準線", file=sys.stderr)
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
    try:
        main()
    except Exception as e:
        print(f"[ERROR] ch2-t4 執行失敗: {e}", file=sys.stderr)
        return_score(0)
