# exceed_correct.py
import cv2
import numpy as np


def group_lines_1d(ylist, gap=8):
    # ylist 可能是 numpy array，不能直接用 if not ylist
    if ylist is None or len(ylist) == 0:
        return []
    ylist = sorted(ylist)
    grouped = []
    group = [ylist[0]]
    for y in ylist[1:]:
        if abs(y - group[-1]) <= gap:
            group.append(y)
        else:
            grouped.append(group)
            group = [y]
    grouped.append(group)
    return [int(np.median(g)) for g in grouped]


def detect_horizontal_lines(image, show_debug=False):
    # 支援傳入路徑或圖片物件
    if isinstance(image, str):
        img = cv2.imdecode(np.fromfile(image, dtype=np.uint8), cv2.IMREAD_COLOR)
    else:
        img = image

    if img is None:
        return None, None

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # BlackHat 強化暗線條
    bh = cv2.morphologyEx(
        gray, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (51, 51))
    )
    _, bw = cv2.threshold(bh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 移除紅色塗線
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask_red = cv2.inRange(hsv, (0, 70, 40), (10, 255, 255)) | cv2.inRange(
        hsv, (170, 70, 40), (180, 255, 255)
    )
    bw[mask_red > 0] = 0

    # 邊緣遮罩
    margin_x = int(0.03 * w)
    margin_y = int(0.03 * h)
    bw[:margin_y, :] = 0
    bw[h - margin_y :, :] = 0
    bw[:, :margin_x] = 0
    bw[:, w - margin_x :] = 0

    # 閉運算補斷線
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((3, 45), np.uint8))

    # 簡單列投影
    row_sum = np.sum(bw > 0, axis=1)
    # 門檻：該列至少有 12% 是黑線
    candidates = np.where(row_sum > (0.12 * w))[0]

    if len(candidates) == 0:
        return None, None

    grouped_y = group_lines_1d(candidates, gap=15)

    # 取最上面和最下面兩條
    if len(grouped_y) >= 2:
        y_top = min(grouped_y)
        y_bot = max(grouped_y)
    elif len(grouped_y) == 1:
        y_top = y_bot = grouped_y[0]
    else:
        return None, None

    return y_top, y_bot
