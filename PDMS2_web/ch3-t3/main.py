import cv2
import numpy as np
import os
import sys
from pathlib import Path

# 引用原本的模組 (請確保這些檔案在同一個目錄下)
from step1_paper_contour import detect_paper_contour
from step2_aruco_quarter_a4 import detect_aruco_and_draw_quarter_a4
from fast_step3_calculate_distances import fast_calculate_distances
from fast_scoring import fast_calculate_cutting_score

BASE_DIR = Path(__file__).resolve().parent


def return_score(score):
    sys.exit(int(score))


def process_single_image(image_path, output_dir=None):
    """
    單張圖片處理程序：
    1. 檢測紙張輪廓(藍線)
    2. 根據ArUco畫出1/4 A4矩形(綠框線)並計算比例尺
    3. 快速計算距離(橘線和紫線)
    4. 快速評分
    """
    filename = os.path.basename(image_path)
    if output_dir is None:
        output_dir = str(BASE_DIR / "result")

    # 確保輸出目錄存在
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print(f"Peabody 發展性動作量表 - 單張處理模式")
    print(f"處理檔案: {filename}")
    print("=" * 60)

    if not os.path.exists(image_path):
        print(f"錯誤: 找不到圖片路徑: {image_path}")
        return False

    # --- 步驟1：檢測紙張輪廓 ---
    print("\n[Step 1] 檢測紙張輪廓...")
    step1_output = os.path.join(output_dir, f"step1_{filename}")
    paper_contour, step1_image = detect_paper_contour(image_path, step1_output)

    if paper_contour is not None:
        print(f"  ✓ 成功檢測輪廓 ({len(paper_contour)} 個點)")
    else:
        print("  ✗ 未檢測到紙張輪廓，停止處理")
        return False

    # --- 步驟2：ArUco檢測和1/4 A4矩形 ---
    print("\n[Step 2] 檢測ArUco標記與比例尺...")
    step2_output = os.path.join(output_dir, f"step2_{filename}")
    quarter_a4_corners, pixels_per_cm, step2_image = detect_aruco_and_draw_quarter_a4(
        image_path, step2_output
    )

    if quarter_a4_corners is not None:
        print(f"  ✓ 檢測到ArUco，比例尺: {pixels_per_cm:.2f} pixels/cm")
    else:
        print("  ✗ 未檢測到ArUco標記，停止處理")
        return False

    # --- 步驟3：快速計算距離 ---
    print("\n[Step 3] 計算偏差距離...")
    step3_output = os.path.join(output_dir, f"fast_step3_{filename}")
    final_output = os.path.join(output_dir, f"final_{filename}")

    distance_result = fast_calculate_distances(image_path, step3_output)

    if distance_result is None:
        print("  ✗ 距離計算失敗")
        return False

    result_image, edge_distances, corner_distances = distance_result

    # 儲存最終合成圖
    # cv2.imwrite(final_output, result_image)

    print(f"  ✓ 距離計算完成")
    print(f"    邊線最大距離: {[f'{d/pixels_per_cm:.2f}cm' for d in edge_distances]}")
    print(f"    角點距離:     {[f'{d/pixels_per_cm:.2f}cm' for d in corner_distances]}")

    # --- 步驟4：快速評分 ---
    print("\n[Step 4] 進行自動評分...")
    scored_output = os.path.join(output_dir, f"fast_scored_{filename}")
    score, score_reason, scored_image = fast_calculate_cutting_score(
        image_path, scored_output
    )

    print("-" * 30)
    print(f"【最終評分】: {score} / 2")
    print(f"【評分原因】: {score_reason}")
    print("-" * 30)

    # print(f"\n所有結果已保存至資料夾: {output_dir}")
    return True, score, result_image


if __name__ == "__main__":
    # 使用方式範例: python main.py 1125 ch3-t3

    if len(sys.argv) > 2:
        # 使用傳入的 uid 和 id 作為圖片路徑
        uid = sys.argv[1]
        img_id = sys.argv[2]
        # uid = "1125"
        # img_id = "ch3-t3"
        image_path = os.path.join("kid", uid, f"{img_id}.jpg")
        result_path = os.path.join("kid", uid, f"{img_id}_result.jpg")
    else:
        return_score(-1)

    # image_path = rf"PDMS2_web\kid\1125\ch3-t3.jpg"
    # result_path = rf"PDMS2_web\kid\1125\ch3-t3_result.jpg"
    # 執行主程式
    try:
        success, score, result_img = process_single_image(image_path)
        if not success:
            return_score(-1)
        if result_img is None:
            result_img = cv2.imread(image_path)
        cv2.imwrite(result_path, result_img)
        return_score(score)
    except Exception as e:
        print(f"[ERROR] ch3-t3 執行失敗: {e}")
        return_score(-1)
