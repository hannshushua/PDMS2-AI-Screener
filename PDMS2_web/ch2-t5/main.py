# main.py — ch2-t5 塗色評分版 (Web 後端呼叫用)
import sys
import cv2
import numpy as np
import os
from pathlib import Path

from get_cm1 import perform_crop
from exceed_correct import detect_horizontal_lines
from draw_range_correct import analyze_paint

BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parent

def main():
    if len(sys.argv) < 3:
        print("用法：python main.py <uid> <img_id>", file=sys.stderr)
        sys.exit(0)

    uid = sys.argv[1]
    img_id = sys.argv[2]

    origin_path = os.path.join(ROOT, "kid", uid, f"{img_id}.jpg")
    cropped_path = os.path.join(ROOT, "kid", uid, f"{img_id}_cropped.jpg")
    result_path = os.path.join(ROOT, "kid", uid, f"{img_id}_result.jpg")

    # 1. AI 紙張裁切
    print("開始 AI 紙張裁切...")
    if not perform_crop(origin_path, cropped_path):
        print("裁切失敗，使用原圖", file=sys.stderr)
        img_orig = cv2.imread(origin_path)
        if img_orig is None:
            sys.exit(0)
        cv2.imwrite(cropped_path, img_orig)

    img = cv2.imread(cropped_path)
    if img is None:
        print(f"裁切圖讀取失敗：{cropped_path}", file=sys.stderr)
        sys.exit(0)

    # 2. 偵測兩條水平基準線
    y_top, y_bot = detect_horizontal_lines(img)
    if y_top is None or y_bot is None:
        print("[Warning] 無法偵測水平線，使用預設範圍")
        h = img.shape[0]
        y_top, y_bot = int(h * 0.3), int(h * 0.7)

    # 3. 分析塗色範圍並評分
    try:
        score, result_img = analyze_paint(img, y_top, y_bot)
    except Exception as e:
        print(f"[Error] 分析過程發生錯誤: {e}", file=sys.stderr)
        score = 0
        result_img = img

    # 4. 儲存結果圖
    cv2.imwrite(result_path, result_img)
    print(f"結果圖已儲存：{result_path} | 得分：{score}")
    sys.exit(score)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] ch2-t5 執行失敗: {e}", file=sys.stderr)
        sys.exit(0)
