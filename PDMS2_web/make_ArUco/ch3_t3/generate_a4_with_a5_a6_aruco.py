import os
import cv2
import numpy as np
from PIL import Image

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# A4 size in mm: 210 x 297
# A5 size in mm: 148 x 210
# A6 size in mm: 105 x 148
# Convert mm to pixels (assuming 300 DPI)
DPI = 300
MM_PER_INCH = 25.4


def mm2px(mm):
    return int((mm / MM_PER_INCH) * DPI)


# A4 size in pixels
a4_width_px = mm2px(210)
a4_height_px = mm2px(297)

# A5 size in pixels
a5_width_px = mm2px(148)
a5_height_px = mm2px(210)

# A6 size in pixels
a6_width_px = mm2px(105)
a6_height_px = mm2px(148)

# A4 分為上下兩半
half_a4_height = a4_height_px // 2

# 1/4 A4 的中心點（左右分別是 1/4 和 3/4 寬度處）
quarter_a4_x_left = a4_width_px // 4
quarter_a4_x_right = 3 * a4_width_px // 4
quarter_a4_y_upper = a4_height_px // 4
quarter_a4_y_lower = 3 * a4_height_px // 4

# 上半部分 A5 區域置中（用於繪製參考邊框）
a5_upper_offset_x = (a4_width_px - a5_width_px) // 2
a5_upper_offset_y = (half_a4_height - a5_height_px) // 2

# 下半部分 A5 區域置中（用於繪製參考邊框）
a5_lower_offset_x = (a4_width_px - a5_width_px) // 2
a5_lower_offset_y = half_a4_height + (half_a4_height - a5_height_px) // 2

# 垂直中線參數
line_thickness_mm = 3
line_thickness_px = mm2px(line_thickness_mm)

# ArUco marker parameters
aruco_size_mm = 30  # 3 cm
aruco_size_px = mm2px(aruco_size_mm)
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

print("=== 生成 A4 頁面（上下各 2 個 ArUco 在 1/4 A4 中心點）===")
print(f"A4 尺寸: {a4_width_px} x {a4_height_px} px ({DPI} DPI)")
print(f"1/4 A4 尺寸: {a4_width_px // 2} x {a4_height_px // 2} px")
print(f"ArUco 尺寸: {aruco_size_px} px ({aruco_size_mm} mm)")
print()

# 建立白色 A4 畫布
page = np.ones((a4_height_px, a4_width_px, 3), dtype=np.uint8) * 255

# ==================== 上半部分 ====================
print("--- 上半部分（左右 1/4 A4 中心點）---")

# 在上半部 1/4 A4 中心點放置 2 個 ArUco
upper_centers = [
    (quarter_a4_x_left, quarter_a4_y_upper),  # 左側 1/4 中心
    (quarter_a4_x_right, quarter_a4_y_upper),  # 右側 1/4 中心
]

aruco_ids = [0, 1]  # 左邊 ID 0，右邊 ID 1

for idx, (center_x, center_y) in enumerate(upper_centers):
    # 產生 ArUco marker
    aruco_marker = cv2.aruco.generateImageMarker(
        aruco_dict, aruco_ids[idx], aruco_size_px
    )
    # 貼上 ArUco marker
    start_x = center_x - aruco_size_px // 2
    start_y = center_y - aruco_size_px // 2
    marker_bgr = cv2.cvtColor(aruco_marker, cv2.COLOR_GRAY2BGR)
    # 防止 marker 超出邊界
    end_x = min(start_x + aruco_size_px, page.shape[1])
    end_y = min(start_y + aruco_size_px, page.shape[0])
    marker_w = end_x - start_x
    marker_h = end_y - start_y
    page[start_y:end_y, start_x:end_x] = marker_bgr[:marker_h, :marker_w]

    print(
        f"ArUco ID {aruco_ids[idx]} (上-{'左' if idx == 0 else '右'} 1/4 中心): 位置 ({center_x}, {center_y})"
    )

# # 繪製 1/4 A4 區域邊框（灰色虛線，用於參考）
# # 上左 1/4
# cv2.rectangle(page, (0, 0), (a4_width_px // 2, a4_height_px // 2), (200, 200, 200), 2)
# # 上右 1/4
# cv2.rectangle(
#     page, (a4_width_px // 2, 0), (a4_width_px, a4_height_px // 2), (200, 200, 200), 2
# )

print()

# ==================== 下半部分 ====================
print("--- 下半部分（左右 1/4 A4 中心點）---")

# 在下半部 1/4 A4 中心點放置 2 個 ArUco
lower_centers = [
    (quarter_a4_x_left, quarter_a4_y_lower),  # 左側 1/4 中心
    (quarter_a4_x_right, quarter_a4_y_lower),  # 右側 1/4 中心
]

for idx, (center_x, center_y) in enumerate(lower_centers):
    # 產生 ArUco marker
    aruco_marker = cv2.aruco.generateImageMarker(
        aruco_dict, aruco_ids[idx], aruco_size_px
    )
    # 貼上 ArUco marker
    start_x = center_x - aruco_size_px // 2
    start_y = center_y - aruco_size_px // 2
    marker_bgr = cv2.cvtColor(aruco_marker, cv2.COLOR_GRAY2BGR)
    # 防止 marker 超出邊界
    end_x = min(start_x + aruco_size_px, page.shape[1])
    end_y = min(start_y + aruco_size_px, page.shape[0])
    marker_w = end_x - start_x
    marker_h = end_y - start_y
    page[start_y:end_y, start_x:end_x] = marker_bgr[:marker_h, :marker_w]

    print(
        f"ArUco ID {aruco_ids[idx]} (下-{'左' if idx == 0 else '右'} 1/4 中心): 位置 ({center_x}, {center_y})"
    )

# # 繪製 1/4 A4 區域邊框（灰色虛線，用於參考）
# # 下左 1/4
# cv2.rectangle(
#     page, (0, a4_height_px // 2), (a4_width_px // 2, a4_height_px), (200, 200, 200), 2
# )
# # 下右 1/4
# cv2.rectangle(
#     page,
#     (a4_width_px // 2, a4_height_px // 2),
#     (a4_width_px, a4_height_px),
#     (200, 200, 200),
#     2,
# )

print()

# # 繪製 A5 區域邊框（灰色虛線，用於參考）
# cv2.rectangle(
#     page,
#     (a5_lower_offset_x, a5_lower_offset_y),
#     (a5_lower_offset_x + a5_width_px, a5_lower_offset_y + a5_height_px),
#     (200, 200, 200),
#     2,
# )

print()

# 垂直中線
center_x = a4_width_px // 2
line_x1 = center_x - line_thickness_px // 2
line_x2 = center_x + line_thickness_px // 2
cv2.rectangle(page, (line_x1, 0), (line_x2, a4_height_px), (0, 0, 0), -1)
print(f"垂直中線: x = {center_x} px，範圍 {line_x1} ~ {line_x2} px")

# 儲存圖片
cv2.imwrite(os.path.join(OUT_DIR, "a4_with_a5_a6_aruco.png"), page)

print("=== 圖片已儲存 ===")
print("✓ a4_with_a5_a6_aruco.png (A4頁面，4個ArUco在各1/4 A4中心點)")
print()

# 建立 PDF（需要 PIL/Pillow）
try:
    from PIL import Image

    # 將 OpenCV BGR 轉換為 PIL RGB
    page_pil = Image.fromarray(cv2.cvtColor(page, cv2.COLOR_BGR2RGB))

    # 建立 PDF
    page_pil.save(os.path.join(OUT_DIR, "a4_with_a5_a6_aruco.pdf"), resolution=DPI)

    print("✓ a4_with_a5_a6_aruco.pdf")
    print()
    print("📐 設計說明：")
    print(f"   - A4 紙張尺寸：210 x 297 mm")
    print(f"   - A4 切成 4 等份（2x2 網格）")
    print(f"   - 每個 1/4 A4 區域：{a4_width_px // 2} x {a4_height_px // 2} px")
    print(f"   - ArUco 位置：各 1/4 A4 區域的中心點")
    print(f"   - ArUco 尺寸：{aruco_size_mm} x {aruco_size_mm} mm")
    print(f"   - 總共 4 個 ArUco 標記")
    print(f"     * 上左 1/4 中心: ID 0")
    print(f"     * 上右 1/4 中心: ID 1")
    print(f"     * 下左 1/4 中心: ID 0")
    print(f"     * 下右 1/4 中心: ID 1")
    print()
    print("   灰色邊框僅供參考，可在程式中註解掉")

except ImportError:
    print("⚠️ 未安裝 Pillow，無法生成 PDF")
    print("   請執行: pip install Pillow")

print()
print("✅ 完成！")
