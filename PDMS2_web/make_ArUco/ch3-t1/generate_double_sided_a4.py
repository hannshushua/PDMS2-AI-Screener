import os
import cv2
import numpy as np
from PIL import Image

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# A4 size in mm: 210 x 297
# A5 size in mm: 148 x 210
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

# A5 區域在 A4 上的偏移（置中）
a5_offset_x = (a4_width_px - a5_width_px) // 2
a5_offset_y = (a4_height_px - a5_height_px) // 2

# 在 A5 區域內放置 2 個圓環/ArUco（上下分布）
margin_from_edge_mm = 30  # 距離 A5 邊緣 3 cm
margin_px = mm2px(margin_from_edge_mm)

# 計算 A5 區域內的圓心位置（相對於 A4）
centers = [
    (a5_offset_x + a5_width_px // 2, a5_offset_y + margin_px),  # A5 上方中央
    (
        a5_offset_x + a5_width_px // 2,
        a5_offset_y + a5_height_px - margin_px,
    ),  # A5 下方中央
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

print("=== 生成 A4 雙面頁面（A5 區域置中）===")
print(f"A4 尺寸: {a4_width_px} x {a4_height_px} px ({DPI} DPI)")
print(f"A5 尺寸: {a5_width_px} x {a5_height_px} px")
print(f"A5 偏移: ({a5_offset_x}, {a5_offset_y})")
print(f"外圓半徑: {outer_radius_px} px ({outer_radius_mm} mm)")
print(f"內圓半徑: {inner_radius_px} px ({inner_radius_mm} mm)")
print(f"ArUco 尺寸: {aruco_size_px} px ({aruco_size_mm} mm)")
print()

# ==================== 第一份 ====================
print("--- 生成第一份 ---")

# 正面：只有圓環（無 ArUco），A5 區域置中
front_page_1 = np.ones((a4_height_px, a4_width_px, 3), dtype=np.uint8) * 255

# 繪製 A5 區域邊框（虛線，用於參考，可選）
# cv2.rectangle(front_page_1,
#               (a5_offset_x, a5_offset_y),
#               (a5_offset_x + a5_width_px, a5_offset_y + a5_height_px),
#               (200, 200, 200), 2)

for idx, (center_x, center_y) in enumerate(centers):
    # 畫黑色外圓
    cv2.circle(
        front_page_1, (center_x, center_y), outer_radius_px, (0, 0, 0), thickness=-1
    )
    # 畫白色內圓
    cv2.circle(
        front_page_1,
        (center_x, center_y),
        inner_radius_px,
        (255, 255, 255),
        thickness=-1,
    )
    # 在內圓中心貼上 ArUco marker
    aruco_marker = cv2.aruco.generateImageMarker(aruco_dict, aruco_id, aruco_size_px)
    marker_bgr = cv2.cvtColor(aruco_marker, cv2.COLOR_GRAY2BGR)
    start_x = center_x - aruco_size_px // 2
    start_y = center_y - aruco_size_px // 2
    end_x = min(start_x + aruco_size_px, front_page_1.shape[1])
    end_y = min(start_y + aruco_size_px, front_page_1.shape[0])
    marker_w = end_x - start_x
    marker_h = end_y - start_y
    front_page_1[start_y:end_y, start_x:end_x] = marker_bgr[:marker_h, :marker_w]
    print(
        f"圓環+ArUco {idx+1}: 圓心 ({center_x}, {center_y}), 外圓 {outer_radius_px}px, 內圓 {inner_radius_px}px, ArUco {aruco_size_px}px"
    )

print()

# 儲存圖片
cv2.imwrite(os.path.join(OUT_DIR, "a4_front_page1.png"), front_page_1)

print("=== 圖片已儲存 ===")
print(f"✓ a4_front_page1.png (正面 - 2個黑色圓環，ArUco ID {aruco_id} 置中在圓環內)")
print()

# 建立 PDF（需要 PIL/Pillow）
try:
    from PIL import Image

    front1_pil = Image.fromarray(cv2.cvtColor(front_page_1, cv2.COLOR_BGR2RGB))
    front1_pil.save(os.path.join(OUT_DIR, "a4_front.pdf"), resolution=DPI)

    print("✓ a4_front.pdf (單頁PDF: 正面)")
    print()
    print("📐 設計說明：")
    print(f"   - A4 紙張尺寸：210 x 297 mm")
    print(f"   - A5 有效區域：148 x 210 mm (置中於 A4)")
    print(f"   - 2 個圓環位於 A5 區域內上下分布")
    print(f"   - 黑色圓環（外徑 {outer_radius_mm}mm，內徑 {inner_radius_mm}mm）+ ArUco ID {aruco_id}（{aruco_size_mm}mm）置中於圓環")

except ImportError:
    print("⚠️ 未安裝 Pillow，無法生成 PDF")
    print("   請執行: pip install Pillow")

print()
print("✅ 完成！")
