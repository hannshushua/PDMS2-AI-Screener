import cv2
import numpy as np
import os
from paper_contour_model import detect_paper_contour_by_model


def judge_score(target_img_path, standard_area):
    """
    核心邏輯函式：讀取圖片 -> 排除反光 -> 計算面積 -> 判定分數
    回傳一個字典 (result_data)，包含所有需要的資訊供顯示使用
    """
    # 1. 讀取圖片
    img = cv2.imread(target_img_path)
    if img is None:
        print(f"錯誤: 無法讀取圖片 {target_img_path}")
        return None

    # 2. 使用模型偵測紙張輪廓
    try:
        best_cnt, _, mask_area, model_path = detect_paper_contour_by_model(img)
    except FileNotFoundError as e:
        return {"error": str(e), "img": img}

    if mask_area <= 0:
        return {"error": "模型未偵測到有效 paper mask", "img": img}

    best_area = float(mask_area)

    # 輕量矩形檢查僅作提示，不再作為輪廓來源
    is_rectangular = True
    if best_cnt is not None:
        x, y, w, h = cv2.boundingRect(best_cnt)
        rect_area = w * h
        extent = float(cv2.contourArea(best_cnt)) / rect_area if rect_area > 0 else 0.0
        if extent <= 0.65:
            is_rectangular = False
            print("警告：模型輪廓矩形充滿度偏低，請確認拍攝角度/遮擋。")
    else:
        is_rectangular = False
        print("警告：僅取得 mask 面積，無法繪製輪廓。")

    print(f"使用模型輪廓: {model_path}")
    print(f"mask 面積像素數: {mask_area}")

    # 4. 計算比例與評分
    ratio = best_area / standard_area
    score = -1
    desc = ""

    # 評分邏輯 (嚴格版)
    if ratio > 0.90:
        score = 0
        desc = "Score 0 (Full)"
    elif 0.40 <= ratio <= 0.60:
        score = 2
        desc = "Score 2 (Half)"
    else:
        score = 1
        # 區分是拿到小張還是大張
        percent = ratio * 100
        desc = f"Score 1 ({percent:.1f}%)"

    # 5. 打包結果回傳
    result_data = {
        "img": img,  # 原圖 (供顯示用)
        "contour": best_cnt,  # 找到的輪廓
        "area": best_area,  # 當前面積
        "ratio": ratio,  # 比例
        "score": score,  # 分數
        "desc": desc,  # 描述文字
        "is_rectangular": is_rectangular,  # 是否通過形狀檢查
    }

    return result_data


def show_result(result_data):
    """
    顯示函式：接收 judge_score 的結果 -> 繪圖 -> 顯示視窗
    """
    if result_data is None or "error" in result_data:
        print("無法顯示結果 (資料錯誤或無影像)")
        return

    img = result_data["img"]
    cnt = result_data["contour"]
    score = result_data["score"]
    desc = result_data["desc"]
    ratio = result_data["ratio"]
    area = result_data["area"]

    # 複製圖片以免破壞原圖
    display_img = img.copy()

    # 1. 畫出輪廓 (綠色)
    if cnt is not None:
        # 如果形狀檢查未通過(可能是反光)，改用黃色警示；通過用綠色
        color = (0, 255, 0) if result_data["is_rectangular"] else (0, 255, 255)
        cv2.drawContours(display_img, [cnt], -1, color, 4)

        # 畫出包圍框 (紅色)
        x, y, w, h = cv2.boundingRect(cnt)
        cv2.rectangle(display_img, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # 2. 準備顯示文字
        text_info = f"{desc} | Ratio: {ratio:.2f}"

        # 為了讓文字清楚，加個左上角黑色背景條
        cv2.rectangle(display_img, (0, 0), (360, 36), (0, 0, 0), -1)
        cv2.putText(
            display_img,
            text_info,
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1,
        )

    # 3. 縮放顯示 (避免圖片太大超出螢幕)
    h, w = display_img.shape[:2]
    max_width = 800
    if w > max_width:
        scale = max_width / w
        new_dim = (max_width, int(h * scale))
        final_view = cv2.resize(display_img, new_dim, interpolation=cv2.INTER_AREA)
    else:
        final_view = display_img

    # 4. 顯示視窗
    print(f"--- 詳細數據 ---")
    print(f"面積: {area:.0f}")
    print(f"比例: {ratio:.2f}")
    print(f"判定: {desc}")

    cv2.imshow("Judge Result", final_view)
    print("按下任意鍵關閉視窗...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# --- 主程式執行區 ---

# 1. 設定基準面積 (請填入你之前測得的數值)
STANDARD_AREA = 17224

# 2. 指定圖片路徑
for i in range(1, 7):
    target_path = rf"iten57\img\{i}.jpg"

    # 3. 執行
    if os.path.exists(target_path):
        # 步驟一：計算與判定
        result = judge_score(target_path, STANDARD_AREA)

        # 步驟二：顯示結果
        show_result(result)
    else:
        print("找不到檔案")
