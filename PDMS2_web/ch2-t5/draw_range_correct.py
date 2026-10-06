# draw_range_correct.py
import cv2
import numpy as np
import os
from PIL import Image, ImageDraw, ImageFont

def draw_text_cn(img, text, pos, color=(255, 0, 0), size=24):
    try:
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        # 嘗試載入微軟正黑體，若失敗則用預設
        font_path = "C:/Windows/Fonts/msjh.ttc"
        if not os.path.exists(font_path):
            font_path = "arial.ttf"
        
        font = ImageFont.truetype(font_path, size)
        draw.text(pos, text, font=font, fill=color)
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    except Exception:
        # Fallback
        cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        return img

def analyze_paint(image, y_top, y_bot, show_windows=False):
    if isinstance(image, str):
        img = cv2.imdecode(np.fromfile(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    else:
        img = image.copy()

    if img is None:
        raise ValueError("圖片無效")

    h, w = img.shape[:2]
    
    # 1. 產生紅筆遮罩
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, (0, 43, 46), (10, 255, 255))
    mask2 = cv2.inRange(hsv, (156, 43, 46), (180, 255, 255))
    mask = mask1 + mask2
    
    # 去雜訊
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3,3), np.uint8))
    mask = cv2.dilate(mask, np.ones((3,3), np.uint8))

    # 2. 偵測黑線的水平範圍 (x_left, x_right)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    band_top = gray[max(0, y_top - 8):min(h, y_top + 8), :]
    band_bot = gray[max(0, y_bot - 8):min(h, y_bot + 8), :]
    col_dark_top = np.where(np.min(band_top, axis=0) < 80)[0]
    col_dark_bot = np.where(np.min(band_bot, axis=0) < 80)[0]
    if len(col_dark_top) > 10 and len(col_dark_bot) > 10:
        x_left = max(int(np.percentile(col_dark_top, 5)), int(np.percentile(col_dark_bot, 5)))
        x_right = min(int(np.percentile(col_dark_top, 95)), int(np.percentile(col_dark_bot, 95)))
    else:
        x_left, x_right = 0, w

    # 3. 定義塗色區域 (y_top ~ y_bot, x_left ~ x_right)
    y_start = max(0, y_top + 5)
    y_end = min(h, y_bot - 5)

    roi = mask[y_start:y_end, x_left:x_right]
    total_pixels = roi.shape[0] * roi.shape[1]
    painted_pixels = cv2.countNonZero(roi)

    ratio = 0
    if total_pixels > 0:
        ratio = painted_pixels / total_pixels

    # 4. 計算超出區域 (限制在黑線水平範圍內)
    mask_top = mask[0:y_top, x_left:x_right]
    out_top = cv2.countNonZero(mask_top)

    mask_bot = mask[y_bot:h, x_left:x_right]
    out_bot = cv2.countNonZero(mask_bot)
    
    protrude_count = 0
    if out_top > 50: protrude_count += 1
    if out_bot > 50: protrude_count += 1

    # 4. 評分邏輯 (可自訂)
    score = 0
    msg = ""
    if ratio > 0.5:
        if protrude_count == 0:
            score = 2
            msg = "塗色完整且未出界"
        elif protrude_count == 1:
            score = 1
            msg = "塗色完整但稍有出界"
        else:
            score = 0
            msg = "塗色完整但出界嚴重"
    elif ratio > 0.2:
        score = 1
        msg = "塗色面積不足"
    else:
        score = 0
        msg = "未有效作答"

    # 5. 繪製結果圖
    result_img = img.copy()
    cv2.line(result_img, (x_left, y_top), (x_right, y_top), (255, 0, 0), 2)
    cv2.line(result_img, (x_left, y_bot), (x_right, y_bot), (255, 0, 0), 2)
    
    # 標示超出部分
    if out_top > 50:
        cv2.putText(result_img, "OUT!", (10, y_top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    if out_bot > 50:
        cv2.putText(result_img, "OUT!", (10, y_bot + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    # 加上文字
    info = f"Score: {score} | Ratio: {ratio:.1%} | Out: {protrude_count}"
    result_img = draw_text_cn(result_img, info, (10, 30), (0, 0, 255))
    result_img = draw_text_cn(result_img, msg, (10, 70), (255, 0, 0))

    return score, result_img
