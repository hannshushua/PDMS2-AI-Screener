import cv2
import numpy as np
import os
from step1_paper_contour import detect_paper_contour
from step2_aruco_quarter_a4 import detect_aruco_and_draw_quarter_a4


def optimized_point_to_contour_distance(point, contour):
    """優化的點到輪廓距離計算"""
    # 轉換為正確的數據類型
    point_tuple = (float(point[0]), float(point[1]))
    # 使用OpenCV的內建函數，速度更快
    distance = cv2.pointPolygonTest(contour, point_tuple, True)
    return abs(distance)


def optimized_rectangle_to_contour_distance(rect_corners, contour):
    """優化的矩形到輪廓距離計算"""
    distances = []

    # 減少採樣點數，只取關鍵點
    num_points = 10  # 進一步減少採樣點

    for i in range(4):
        p1 = rect_corners[i]
        p2 = rect_corners[(i + 1) % 4]

        max_distance = 0

        # 在邊上採樣
        for j in range(num_points + 1):
            t = j / num_points
            point = p1 + t * (p2 - p1)
            distance = optimized_point_to_contour_distance(point, contour)
            max_distance = max(max_distance, distance)

        distances.append(max_distance)

    return distances


def fast_calculate_distances(image_path, output_path=None):
    """
    快速版本的距離計算
    """
    print(f"  [快速模式] 處理圖片: {os.path.basename(image_path)}")

    # 讀取圖片
    image = cv2.imread(image_path)
    if image is None:
        print(f"無法讀取圖片: {image_path}")
        return None

    result_image = image.copy()

    # 步驟1：檢測紙張輪廓
    paper_contour, _ = detect_paper_contour(image_path)
    if paper_contour is None:
        print("無法檢測到紙張輪廓")
        return None

    # 大幅簡化輪廓
    epsilon = 0.005 * cv2.arcLength(paper_contour, True)  # 降低簡化誤差
    simplified_contour = cv2.approxPolyDP(paper_contour, epsilon, True)
    print(f"    輪廓簡化: {len(paper_contour)} -> {len(simplified_contour)} 點")

    # 步驟2：檢測ArUco並繪製1/4 A4矩形
    quarter_a4_corners, pixels_per_cm, _ = detect_aruco_and_draw_quarter_a4(image_path)
    if quarter_a4_corners is None:
        print("無法檢測到ArUco標記")
        return None

    # 繪製紙張輪廓（藍色）
    cv2.drawContours(result_image, [paper_contour], -1, (255, 0, 0), 1)

    # 繪製1/4 A4矩形（綠色）
    cv2.polylines(result_image, [quarter_a4_corners], True, (0, 255, 0), 1)

    # 快速計算邊線距離
    edge_distances = optimized_rectangle_to_contour_distance(
        quarter_a4_corners, simplified_contour
    )

    # 快速計算角點距離
    corner_distances = []
    for corner in quarter_a4_corners:
        distance = optimized_point_to_contour_distance(corner, simplified_contour)
        corner_distances.append(distance)

    # 簡化的視覺化 - 只顯示最重要的線條
    max_edge_idx = edge_distances.index(max(edge_distances))
    max_corner_idx = corner_distances.index(max(corner_distances))

    # 只畫最大距離的線條
    # 最大邊線距離（橘線）
    p1 = quarter_a4_corners[max_edge_idx]
    p2 = quarter_a4_corners[(max_edge_idx + 1) % 4]
    mid_edge = (p1 + p2) / 2
    cv2.line(
        result_image,
        tuple(mid_edge.astype(int)),
        tuple(mid_edge.astype(int)),
        (0, 165, 255),
        2,
    )
    cv2.putText(
        result_image,
        f"Max Edge: {edge_distances[max_edge_idx]/pixels_per_cm:.2f}cm",
        tuple((mid_edge + [0, -20]).astype(int)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 165, 255),
        2,
    )

    # 最大角點距離（紫線）
    corner = quarter_a4_corners[max_corner_idx]
    cv2.circle(result_image, tuple(corner), 4, (255, 0, 255), -1)
    cv2.putText(
        result_image,
        f"Max Corner: {corner_distances[max_corner_idx]/pixels_per_cm:.2f}cm",
        tuple((corner + [10, -10]).astype(int)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 0, 255),
        2,
    )

    # 在左下角顯示距離數據
    img_height = result_image.shape[0]
    edge_distances_cm = (
        [d / pixels_per_cm for d in edge_distances] if pixels_per_cm else edge_distances
    )
    corner_distances_cm = (
        [d / pixels_per_cm for d in corner_distances]
        if pixels_per_cm
        else corner_distances
    )

    max_edge_distance = max(edge_distances_cm)
    max_corner_distance = max(corner_distances_cm)

    cv2.putText(
        result_image,
        f"Max Edge Distance: {max_edge_distance:.2f}cm",
        (50, img_height - 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 165, 255),
        2,
    )
    cv2.putText(
        result_image,
        f"Max Corner Distance: {max_corner_distance:.2f}cm",
        (50, img_height - 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 0, 255),
        2,
    )

    print(f"    最大邊線距離: {max_edge_distance:.2f}cm")
    print(f"    最大角點距離: {max_corner_distance:.2f}cm")

    # 保存結果圖片
    if output_path:
        cv2.imwrite(output_path, result_image)
        print(f"    結果已保存到: {output_path}")

    return result_image, edge_distances, corner_distances


def main():
    """快速測試函數"""
    input_dir = "img"
    output_dir = "result"

    os.makedirs(output_dir, exist_ok=True)

    print("快速距離計算模式")
    print("=" * 40)

    image_files = [
        f
        for f in os.listdir(input_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    for i, filename in enumerate(image_files, 1):
        print(f"\n[{i}/{len(image_files)}] 處理圖片: {filename}")

        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, f"fast_{filename}")

        result = fast_calculate_distances(input_path, output_path)

        if result is not None:
            print(f"✓ 快速處理完成")
        else:
            print("✗ 處理失敗")


if __name__ == "__main__":
    main()
