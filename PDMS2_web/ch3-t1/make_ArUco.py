import cv2
import numpy as np

# A4 size in mm: 210 x 297
# Convert mm to pixels (assuming 300 DPI)
DPI = 300
MM_PER_INCH = 25.4


def mm2px(mm):
    return int((mm / MM_PER_INCH) * DPI)


# A4 size in pixels
a4_width_px = mm2px(210)
a4_height_px = mm2px(297)

# Create white A4 canvas
canvas = np.ones((a4_height_px, a4_width_px, 3), dtype=np.uint8) * 255


# 六個圓環的圓心座標，分布在四角與上下邊中央
margin_mm = 50  # 距離邊緣 5 公分
margin_px = mm2px(margin_mm)

centers = [
    (margin_px, margin_px),  # 左上
    (a4_width_px - margin_px, margin_px),  # 右上
    (margin_px, a4_height_px - margin_px),  # 左下
    (a4_width_px - margin_px, a4_height_px - margin_px),  # 右下
    (margin_px, a4_height_px // 2),  # 左邊中央
    (a4_width_px - margin_px, a4_height_px // 2),  # 右邊中央
]


# 圓環參數
outer_radius_mm = 40  # 4 cm
border_width_mm = 6  # 0.6 cm
inner_radius_mm = outer_radius_mm - border_width_mm  # 3.4 cm
outer_radius_px = mm2px(outer_radius_mm)
inner_radius_px = mm2px(inner_radius_mm)

# ArUco marker parameters
aruco_size_mm = 20  # 2 cm
aruco_size_px = mm2px(aruco_size_mm)
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_id = 0

for idx, (center_x, center_y) in enumerate(centers):
    # 畫黑色外圓
    cv2.circle(canvas, (center_x, center_y), outer_radius_px, (0, 0, 0), thickness=-1)
    # 畫白色內圓
    cv2.circle(
        canvas, (center_x, center_y), inner_radius_px, (255, 255, 255), thickness=-1
    )
    # 產生 ArUco marker
    aruco_marker = cv2.aruco.generateImageMarker(aruco_dict, aruco_id, aruco_size_px)
    # 貼上 ArUco marker
    start_x = center_x - aruco_size_px // 2
    start_y = center_y - aruco_size_px // 2
    marker_bgr = cv2.cvtColor(aruco_marker, cv2.COLOR_GRAY2BGR)
    # 防止 marker 超出邊界
    end_x = min(start_x + aruco_size_px, canvas.shape[1])
    end_y = min(start_y + aruco_size_px, canvas.shape[0])
    marker_w = end_x - start_x
    marker_h = end_y - start_y
    canvas[start_y:end_y, start_x:end_x] = marker_bgr[:marker_h, :marker_w]


# 印出每個圓環參數
print("Black ring (annulus) parameters:")
for idx, (center_x, center_y) in enumerate(centers):
    print(f"Ring {idx+1}: Center: (x = {center_x}, y = {center_y})")
    print(f"  Outer radius: {outer_radius_px} px ({outer_radius_mm} mm)")
    print(f"  Inner radius: {inner_radius_px} px ({inner_radius_mm} mm)")

# Save result
cv2.imwrite("a4_aruco.png", canvas)
