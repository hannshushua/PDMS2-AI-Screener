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

# 在 A5 區域內放置 2 個方框/ArUco（上下分布）
margin_from_edge_mm = 35  # 距離 A5 邊緣 3.5 cm
margin_px = mm2px(margin_from_edge_mm)

# 計算 A5 區域內的方框中心位置（相對於 A4）
centers = [
    (a5_offset_x + a5_width_px // 2, a5_offset_y + margin_px),  # A5 上方中央
    (
        a5_offset_x + a5_width_px // 2,
        a5_offset_y + a5_height_px - margin_px,
    ),  # A5 下方中央
]

# 方框參數
outer_square_size_mm = 80  # 8 cm (外方框邊長)
border_width_mm = 6  # 0.6 cm (邊框寬度)
inner_square_size_mm = outer_square_size_mm - 2 * border_width_mm  # 6.8 cm (內方框邊長)
outer_square_size_px = mm2px(outer_square_size_mm)
inner_square_size_px = mm2px(inner_square_size_mm)

# ArUco marker parameters
aruco_size_mm = 20  # 2 cm
aruco_size_px = mm2px(aruco_size_mm)
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_id = 0

print("=== 生成 A4 雙面頁面（方形方框版本，A5 區域置中）===")
print(f"A4 尺寸: {a4_width_px} x {a4_height_px} px ({DPI} DPI)")
print(f"A5 尺寸: {a5_width_px} x {a5_height_px} px")
print(f"A5 偏移: ({a5_offset_x}, {a5_offset_y})")
print(f"外方框邊長: {outer_square_size_px} px ({outer_square_size_mm} mm)")
print(f"內方框邊長: {inner_square_size_px} px ({inner_square_size_mm} mm)")
print(f"ArUco 尺寸: {aruco_size_px} px ({aruco_size_mm} mm)")
print()

# ==================== 第一份 ====================
print("--- 生成第一份 ---")

# 正面：只有方框（無 ArUco），A5 區域置中
front_page_1 = np.ones((a4_height_px, a4_width_px, 3), dtype=np.uint8) * 255

for idx, (center_x, center_y) in enumerate(centers):
    # 計算方框的左上角和右下角
    outer_x1 = center_x - outer_square_size_px // 2
    outer_y1 = center_y - outer_square_size_px // 2
    outer_x2 = center_x + outer_square_size_px // 2
    outer_y2 = center_y + outer_square_size_px // 2

    inner_x1 = center_x - inner_square_size_px // 2
    inner_y1 = center_y - inner_square_size_px // 2
    inner_x2 = center_x + inner_square_size_px // 2
    inner_y2 = center_y + inner_square_size_px // 2

    # 畫黑色外方框
    cv2.rectangle(
        front_page_1,
        (outer_x1, outer_y1),
        (outer_x2, outer_y2),
        (0, 0, 0),
        thickness=-1,
    )
    # 畫白色內方框
    cv2.rectangle(
        front_page_1,
        (inner_x1, inner_y1),
        (inner_x2, inner_y2),
        (255, 255, 255),
        thickness=-1,
    )

    # 在內方框中心貼上 ArUco marker
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
        f"方框+ArUco {idx+1}: 中心 ({center_x}, {center_y}), 外方框 {outer_square_size_px}px, 內方框 {inner_square_size_px}px, ArUco {aruco_size_px}px"
    )

print()

# 儲存圖片
cv2.imwrite(os.path.join(OUT_DIR, "a4_front_page1_square.png"), front_page_1)

print("=== 圖片已儲存 ===")
print(f"✓ a4_front_page1_square.png (正面 - 2個黑色方框，ArUco ID {aruco_id} 置中在方框內)")
print()

# 建立 PDF（需要 PIL/Pillow）
try:
    from PIL import Image

    front1_pil = Image.fromarray(cv2.cvtColor(front_page_1, cv2.COLOR_BGR2RGB))
    front1_pil.save(os.path.join(OUT_DIR, "a4_front_square.pdf"), resolution=DPI)

    print("✓ a4_front_square.pdf (單頁PDF: 正面)")
    print()
    print("📐 設計說明：")
    print(f"   - A4 紙張尺寸：210 x 297 mm")
    print(f"   - A5 有效區域：148 x 210 mm (置中於 A4)")
    print(f"   - 2 個方框位於 A5 區域內上下分布")
    print(f"   - 黑色方框（外框 {outer_square_size_mm}mm，內框 {inner_square_size_mm}mm）+ ArUco ID {aruco_id}（{aruco_size_mm}mm）置中於方框")

except ImportError:
    print("⚠️ 未安裝 Pillow，無法生成 PDF")
    print("   請執行: pip install Pillow")

print()
print("✅ 完成！")
