import cv2
import numpy as np
import torch
import segmentation_models_pytorch as smp
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PAPER_MODEL_PATH = os.path.join(BASE_DIR, "paper_model.pth")

def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def get_ai_paper_mask(img, model, device):
    h, w = img.shape[:2]
    img_resized = cv2.resize(img, (512, 512))
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    img_norm = img_rgb.astype(np.float32) / 255.0
    img_norm = (img_norm - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    img_tensor = torch.from_numpy(img_norm).permute(2, 0, 1).unsqueeze(0).float().to(device)

    with torch.no_grad():
        pred = model(img_tensor)
        mask = (pred.squeeze().cpu().numpy() > 0.5).astype(np.uint8) * 255

    return cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)

def perform_crop(in_path, out_path):
    if not os.path.exists(in_path):
        print(f"找不到原始圖片：{in_path}", file=sys.stderr)
        return False

    img = cv2.imread(in_path)
    if img is None:
        print(f"圖片讀取失敗：{in_path}", file=sys.stderr)
        return False

    if not os.path.exists(PAPER_MODEL_PATH):
        print(f"找不到模型檔案：{PAPER_MODEL_PATH}", file=sys.stderr)
        return False

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = smp.Unet(encoder_name="resnet34", in_channels=3, classes=1, activation='sigmoid')
    model.load_state_dict(torch.load(PAPER_MODEL_PATH, map_location=device))
    model.to(device).eval()

    mask = get_ai_paper_mask(img, model, device)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        print("AI 找不到紙張輪廓", file=sys.stderr)
        return False

    c = max(contours, key=cv2.contourArea)
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.02 * peri, True)

    if len(approx) != 4:
        print(f"找到的形狀不是四邊形（抓到 {len(approx)} 個角）", file=sys.stderr)
        return False

    pts = approx.reshape(4, 2)
    rect = order_points(pts)
    width, height = 2100, 1485
    dst = np.array([
        [0, 0],
        [width - 1, 0],
        [width - 1, height - 1],
        [0, height - 1]
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (width, height))
    cv2.imwrite(out_path, warped)
    return True

if __name__ == "__main__":
    if len(sys.argv) > 2:
        uid, img_id = sys.argv[1], sys.argv[2]
        in_path = os.path.join(BASE_DIR.parent, "kid", uid, f"{img_id}.jpg")
        out_path = os.path.join(BASE_DIR.parent, "kid", uid, f"{img_id}_cropped.jpg")
        perform_crop(in_path, out_path)
