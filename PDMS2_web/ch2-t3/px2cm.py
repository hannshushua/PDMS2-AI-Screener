# get_pixel_per_cm.py
import cv2
import numpy as np
import os

def get_pixel_per_cm_from_a4(image_path, real_width_cm=29.7, show_debug=False, save_cropped=True, output_folder="cropped_a4"):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("圖片讀取失敗，請確認路徑正確")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(blur, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    a4_contour = max(contours, key=cv2.contourArea)
    epsilon = 0.02 * cv2.arcLength(a4_contour, True)
    approx = cv2.approxPolyDP(a4_contour, epsilon, True)

    if len(approx) != 4:
        raise ValueError("無法偵測 A4 紙四邊形輪廓")

    if show_debug:
        debug_img = img.copy()
        cv2.drawContours(debug_img, [approx], -1, (0, 0, 255), 3)
        cv2.imshow("Detected A4 Contour", cv2.resize(debug_img, (800, 600)))
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    # 整理四個角點
    pts = approx.reshape(4, 2).astype(np.float32)
    pts = sorted(pts, key=lambda p: p[0])  # 先左右
    left = sorted(pts[0:2], key=lambda p: p[1])
    right = sorted(pts[2:4], key=lambda p: p[1])
    tl, bl = left
    tr, br = right

    # 計算像素/公分比例
    a4_pixel_width = np.linalg.norm(tr - tl)
    pixel_per_cm = float(a4_pixel_width / real_width_cm)  # 轉換為 Python 原生 float

    # 儲存裁切後的A4區域
    cropped_path = None
    if save_cropped:
        # 建立輸出資料夾
        os.makedirs(output_folder, exist_ok=True)
        
        # 定義目標尺寸（標準化為A4比例）
        target_width = 842  # A4寬度（像素）
        target_height = 595  # A4高度（像素）
        
        # 原始四個角點（順序：左上、右上、右下、左下）
        src_pts = np.array([tl, tr, br, bl], dtype=np.float32)
        
        # 目標四個角點
        dst_pts = np.array([
            [0, 0],
            [target_width, 0],
            [target_width, target_height],
            [0, target_height]
        ], dtype=np.float32)
        
        # 計算透視變換矩陣
        transform_matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        
        # 進行透視變換
        warped = cv2.warpPerspective(img, transform_matrix, (target_width, target_height))
        
        # 儲存裁切後的圖片
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        cropped_filename = f"{image_name}_a4_cropped.jpg"
        cropped_path = os.path.join(output_folder, cropped_filename)
        cv2.imwrite(cropped_path, warped)
        
        print(f"A4區域已儲存至: {cropped_path}")

    return pixel_per_cm, None, cropped_path

def crop_a4_region_simple(image_path, output_folder="cropped_a4"):
    """簡單版本：只裁切A4區域，不計算像素比例"""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("圖片讀取失敗，請確認路徑正確")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    a4_contour = max(contours, key=cv2.contourArea)
    epsilon = 0.02 * cv2.arcLength(a4_contour, True)
    approx = cv2.approxPolyDP(a4_contour, epsilon, True)

    if len(approx) != 4:
        raise ValueError("無法偵測 A4 紙四邊形輪廓")

    # 整理四個角點
    pts = approx.reshape(4, 2).astype(np.float32)
    pts = sorted(pts, key=lambda p: p[0])
    left = sorted(pts[0:2], key=lambda p: p[1])
    right = sorted(pts[2:4], key=lambda p: p[1])
    tl, bl = left
    tr, br = right

    # 建立輸出資料夾
    os.makedirs(output_folder, exist_ok=True)
    
    # 定義目標尺寸
    target_width = 842
    target_height = 595
    
    # 透視變換
    src_pts = np.array([tl, tr, br, bl], dtype=np.float32)
    dst_pts = np.array([
        [0, 0],
        [target_width, 0],
        [target_width, target_height],
        [0, target_height]
    ], dtype=np.float32)
    
    transform_matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(img, transform_matrix, (target_width, target_height))
    
    # 儲存
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    cropped_filename = f"{image_name}_a4_cropped.jpg"
    cropped_path = os.path.join(output_folder, cropped_filename)
    cv2.imwrite(cropped_path, warped)
    
    return cropped_path

# 單獨執行這個檔案時顯示紙張輪廓並儲存裁切區域
if __name__ == "__main__":
    image_path = r''
    
    # 方法1: 完整功能（計算像素比例 + 儲存裁切圖）
    pixel_per_cm, _, cropped_path = get_pixel_per_cm_from_a4(
        image_path, 
        show_debug=True, 
        save_cropped=True,
        output_folder="cropped_a4"
    )
    print(f"每公分像素：{pixel_per_cm:.2f}")
    if cropped_path:
        print(f"裁切圖片已儲存：{cropped_path}")
    
    # 方法2: 只裁切A4區域（不計算像素比例）
    # cropped_path = crop_a4_region_simple(image_path, "cropped_a4")
    # print(f"A4區域已儲存：{cropped_path}")