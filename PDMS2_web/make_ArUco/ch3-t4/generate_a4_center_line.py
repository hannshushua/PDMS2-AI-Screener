import os
import cv2
import numpy as np
from PIL import Image

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

DPI = 300
MM_PER_INCH = 25.4


def mm2px(mm):
    return int((mm / MM_PER_INCH) * DPI)


# A4 size in pixels
a4_width_px = mm2px(210)
a4_height_px = mm2px(297)

# 線的粗細
line_thickness_mm = 3
line_thickness_px = mm2px(line_thickness_mm)

print("=== 生成 A4 正面（中間垂直線）===")
print(f"A4 尺寸: {a4_width_px} x {a4_height_px} px ({DPI} DPI)")
print(f"中線粗度: {line_thickness_mm} mm")
print()

# 正面：中間垂直線
front_page = np.ones((a4_height_px, a4_width_px, 3), dtype=np.uint8) * 255

center_x = a4_width_px // 2
line_x1 = center_x - line_thickness_px // 2
line_x2 = center_x + line_thickness_px // 2
cv2.rectangle(front_page, (line_x1, 0), (line_x2, a4_height_px), (0, 0, 0), -1)

print(f"中線位置: x = {center_x} px，範圍 {line_x1} ~ {line_x2} px")
print()

# 儲存圖片
cv2.imwrite(os.path.join(OUT_DIR, "a4_front_centerline.png"), front_page)

print("=== 圖片已儲存 ===")
print("✓ a4_front_centerline.png (正面 - 中間垂直線)")
print()

try:
    front_pil = Image.fromarray(cv2.cvtColor(front_page, cv2.COLOR_BGR2RGB))
    front_pil.save(os.path.join(OUT_DIR, "a4_front_centerline.pdf"), resolution=DPI)
    print("✓ a4_front_centerline.pdf (單頁PDF: 正面)")
    print()
    print("📐 設計說明：")
    print(f"   - A4 紙張尺寸：210 x 297 mm")
    print(f"   - 正面：垂直中線（寬度 {line_thickness_mm} mm）")

except ImportError:
    print("⚠️ 未安裝 Pillow，無法生成 PDF")
    print("   請執行: pip install Pillow")

print()
print("✅ 完成！")
