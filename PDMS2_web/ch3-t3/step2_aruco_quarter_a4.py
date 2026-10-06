import cv2
import numpy as np
import os

ALLOWED_ARUCO_IDS = (0, 1)  # 紙上印的 ArUco id


def detect_aruco_and_draw_quarter_a4(image_path, output_path=None, aruco_size_cm=2.8):
    """
    檢測ArUco標記，畫出1/4 A4大小的矩形（綠色框線），並計算比例尺
    """
    # 讀取圖片
    image = cv2.imread(image_path)
    if image is None:
        print(f"無法讀取圖片: {image_path}")
        return None, None, None

    # 複製原圖用於繪製結果
    result_image = image.copy()

    # 初始化ArUco字典和檢測器 (適配不同OpenCV版本)
    try:
        # OpenCV 4.7+
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        detector = cv2.aruco.ArucoDetector(aruco_dict)
        corners, ids, _ = detector.detectMarkers(image)
    except AttributeError:
        try:
            # OpenCV 4.0-4.6
            aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
            aruco_params = cv2.aruco.DetectorParameters_create()
            corners, ids, _ = cv2.aruco.detectMarkers(
                image, aruco_dict, parameters=aruco_params
            )
        except AttributeError:
            # 更舊版本或其他情況
            aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            corners, ids, _ = cv2.aruco.detectMarkers(image, aruco_dict)

    # 只用紙上的 ArUco（ALLOWED_ARUCO_IDS），忽略桌面等其他標記；多個符合時取面積最大者
    picked = []
    if ids is not None:
        picked = [
            (c, i)
            for c, i in zip(corners, ids.ravel())
            if int(i) in ALLOWED_ARUCO_IDS
        ]
        if len(picked) < len(corners):
            ignored = sorted(int(i) for i in ids.ravel() if int(i) not in ALLOWED_ARUCO_IDS)
            print(f"忽略非指定 ArUco id: {ignored}")
    if picked:
        picked.sort(key=lambda t: cv2.contourArea(t[0][0]), reverse=True)
        corners = (picked[0][0],)
        ids = np.array([[picked[0][1]]])
        print(f"使用 ArUco id {int(picked[0][1])}")

    if len(picked) > 0:
        aruco_corners = corners[0][0].astype(np.float32)

        # 角點修到次像素：ArUco 只有幾十 px 時，整數角點 1px 誤差就會讓方向偏 1~2 度
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        side_px = float(np.mean([
            np.linalg.norm(aruco_corners[(k + 1) % 4] - aruco_corners[k]) for k in range(4)
        ]))
        win = int(np.clip(side_px / 10, 2, 5))
        refined = aruco_corners.reshape(-1, 1, 2).copy()
        cv2.cornerSubPix(
            gray, refined, (win, win), (-1, -1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.01),
        )
        c0, c1, c2, c3 = refined.reshape(4, 2).astype(np.float64)

        # 計算ArUco的中心點（像素）
        center_x, center_y = np.mean([c0, c1, c2, c3], axis=0)

        # 寬方向 = c0->c1，高方向 = c0->c3。各取兩條平行邊平均，分別算比例尺（吸收透視壓縮）
        width_len = (np.linalg.norm(c1 - c0) + np.linalg.norm(c2 - c3)) / 2.0
        height_len = (np.linalg.norm(c3 - c0) + np.linalg.norm(c2 - c1)) / 2.0
        if width_len < 1e-6 or height_len < 1e-6:
            print("ArUco 邊長異常，無法建立標準方框")
            return None, None, result_image
        px_per_cm_w = width_len / aruco_size_cm
        px_per_cm_h = height_len / aruco_size_cm

        # 計算像素到厘米的比例尺（距離換算用兩方向平均）
        pixels_per_cm = (px_per_cm_w + px_per_cm_h) / 2.0

        print(f"ArUco中心點: ({center_x:.1f}, {center_y:.1f})")
        print(f"ArUco像素邊長: 寬 {width_len:.1f} / 高 {height_len:.1f} pixels")
        print(f"比例尺: {pixels_per_cm:.2f} pixels/cm (寬 {px_per_cm_w:.2f} / 高 {px_per_cm_h:.2f})")

        # A4紙尺寸：21cm x 29.7cm，1/4 A4約為 10.5cm x 14.85cm
        quarter_a4_width_cm = 10.5
        quarter_a4_height_cm = 14.85

        # 轉換為像素尺寸
        quarter_a4_width_px = quarter_a4_width_cm * px_per_cm_w
        quarter_a4_height_px = quarter_a4_height_cm * px_per_cm_h

        print(f"1/4 A4尺寸: {quarter_a4_width_px:.0f} x {quarter_a4_height_px:.0f} pixels")

        # 方向：四條邊一起估一個旋轉角，強制寬高互相垂直，確保畫出來是長方形（不是平行四邊形）
        # 影像座標(y 向下)中 高方向 = 寬方向轉 +90 度，所以高方向的邊轉 -90 度後可與寬方向平均
        def _unit(v):
            return v / np.linalg.norm(v)

        def _rot_m90(v):
            return np.array([v[1], -v[0]])

        width_dir = _unit(
            _unit(c1 - c0) + _unit(c2 - c3)
            + _rot_m90(_unit(c3 - c0)) + _rot_m90(_unit(c2 - c1))
        )
        height_dir = np.array([-width_dir[1], width_dir[0]])

        half_width_vec = width_dir * (quarter_a4_width_px / 2.0)
        half_height_vec = height_dir * (quarter_a4_height_px / 2.0)
        center = np.array([center_x, center_y], dtype=np.float64)

        top_left = center - half_width_vec - half_height_vec
        top_right = center + half_width_vec - half_height_vec
        bottom_right = center + half_width_vec + half_height_vec
        bottom_left = center - half_width_vec + half_height_vec

        quarter_a4_corners = np.round(
            np.array([top_left, top_right, bottom_right, bottom_left])
        ).astype(np.int32)

        # 繪製ArUco標記（紅色框線）
        cv2.aruco.drawDetectedMarkers(result_image, corners, ids)

        # 繪製1/4 A4矩形（綠色框線）
        cv2.polylines(
            result_image, [quarter_a4_corners], True, (0, 255, 0), 1
        )  # 綠色，線寬1

        # 添加文字說明
        cv2.putText(
            result_image,
            f"Scale: {pixels_per_cm:.2f} px/cm",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )
        cv2.putText(
            result_image,
            f"ArUco: {aruco_size_cm}cm",
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )
        cv2.putText(
            result_image,
            f"1/4 A4: {quarter_a4_width_cm}x{quarter_a4_height_cm}cm",
            (10, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )

        print(f"✓ 成功檢測ArUco並繪製1/4 A4矩形")

        # 保存結果圖片
        if output_path:
            cv2.imwrite(output_path, result_image)
            print(f"結果已保存到: {output_path}")

        return quarter_a4_corners, pixels_per_cm, result_image
    else:
        print(f"未檢測到指定的ArUco標記 (id {list(ALLOWED_ARUCO_IDS)})")
        return None, None, result_image


def main():
    """測試函數"""
    input_dir = "img"
    output_dir = "result"

    # 確保輸出目錄存在
    os.makedirs(output_dir, exist_ok=True)

    # 處理所有圖片
    for filename in os.listdir(input_dir):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, f"step2_{filename}")

            print(f"\n處理圖片: {filename}")
            corners, scale, result = detect_aruco_and_draw_quarter_a4(
                input_path, output_path
            )

            if corners is not None:
                print(f"✓ 成功檢測ArUco並繪製1/4 A4矩形")
            else:
                print("✗ 未能檢測到ArUco標記")


if __name__ == "__main__":
    main()
