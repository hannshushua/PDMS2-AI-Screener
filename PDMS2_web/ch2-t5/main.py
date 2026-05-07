# main.py (修正版：正確處理路徑與檔案寫入)
# -*- coding: utf-8 -*-
import sys
import cv2
import numpy as np
import os
from pathlib import Path

# 引用同一資料夾下的模組
from cut_paper import get_pixel_per_cm_from_a4
from exceed_correct import detect_horizontal_lines
from draw_range_correct import analyze_paint

# 設定根目錄
ROOT = Path(__file__).resolve().parent.parent

def main():
    # 1. 接收參數
    if len(sys.argv) < 3:
        print("Usage: python main.py [uid] [task_id]")
        sys.exit(-1)

    uid = sys.argv[1]
    img_id = sys.argv[2] # 例如 "Ch2-t5"

    # 建構檔案路徑 (使用 pathlib 處理路徑，比較穩)
    # 來源: kid/UID/Ch2-t5.jpg
    src_path = ROOT / "kid" / uid / f"{img_id}.jpg"
    # 結果: kid/UID/Ch2-t5_result.jpg
    res_path = ROOT / "kid" / uid / f"{img_id}_result.jpg"

    print(f"[-] Processing: {src_path}")

    if not src_path.exists():
        print(f"[Error] 檔案不存在: {src_path}")
        sys.exit(-1)

    # 2. 裁切 A4 紙
    # 注意：get_pixel_per_cm_from_a4 現在只回傳圖片，不存檔
    warped = get_pixel_per_cm_from_a4(src_path)
    
    if warped is None:
        print("[Error] 裁切失敗，無法識別 A4 紙，使用原圖繼續嘗試")
        # 若裁切失敗，嘗試用原圖 (Fallback)
        warped = cv2.imdecode(np.fromfile(str(src_path), dtype=np.uint8), cv2.IMREAD_COLOR)

    # 3. 偵測水平線
    y_top, y_bot = detect_horizontal_lines(warped)
    
    if y_top is None or y_bot is None:
        print("[Warning] 無法偵測水平線，使用預設範圍")
        h, w = warped.shape[:2]
        y_top, y_bot = int(h*0.3), int(h*0.7)

    # 4. 分析塗色並取得結果圖
    try:
        score, result_img = analyze_paint(warped, y_top, y_bot)
    except Exception as e:
        print(f"[Error] 分析過程發生錯誤: {e}")
        score = -1
        result_img = warped

    # 5. 儲存結果圖 (這一步最重要！)
    try:
        is_success, buffer = cv2.imencode(".jpg", result_img)
        if is_success:
            with open(str(res_path), "wb") as f:
                f.write(buffer)
            print(f"[Success] 結果圖已儲存: {res_path}")
        else:
            print("[Error] 圖片編碼失敗")
    except Exception as e:
        print(f"[Error] 寫入檔案失敗: {e}")

    # 6. 回傳分數 (exit code)
    sys.exit(score)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[Error] ch2-t5 執行失敗: {e}")
        sys.exit(-1)