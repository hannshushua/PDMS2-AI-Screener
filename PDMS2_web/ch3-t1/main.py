from PaperDetector_yolo import PaperDetector_yolo
from BoxDistanceAnalyzer import BoxDistanceAnalyzer
import cv2
import sys
import os


def return_score(score):
    sys.exit(int(score))


if __name__ == "__main__":
    # 預設失敗分數，任何流程失敗都回傳 -1
    score = -1

    # 檢查是否有傳入 uid 與 id
    if len(sys.argv) <= 2:
        print("缺少參數，使用方式: python main.py <uid> <img_id>")
        return_score(score)

    uid = sys.argv[1]
    img_id = sys.argv[2]
    image_path = os.path.join("kid", uid, f"{img_id}.jpg")

    if not os.path.exists(image_path):
        print(f"找不到圖片: {image_path}")
        return_score(score)

    print(f"\n正在處理圖片: {image_path}")
    print("====先用模型裁切 paper 區域====")

    detector_path = None
    min_dist_cm = None
    max_dist_cm = None

    try:
        detector = PaperDetector_yolo(image_path)
        detector.detect_paper_by_yolo()

        if detector.result is not None:
            detected_path = os.path.join("kid", uid, f"{img_id}_detected.jpg")
            cv2.imwrite(detected_path, detector.result)
            print(f"偵測框圖片已儲存: {detected_path}")

        if detector.original is not None:
            region = detector.extract_paper_region()
            if region is not None:
                detector_path = detector.save_results()

        print("====再用裁切後圖片進行評分====")
        if detector_path:
            if detector.object_mask_points_warped is None:
                print("原圖未偵測到 object mask，無法進行距離評分")
            else:
                result = BoxDistanceAnalyzer(
                    detector_path,
                    contour_points=detector.object_mask_points_warped,
                    largest_contour_points=detector.object_mask_largest_contour_warped,
                )
                if result is not None:
                    result_img, min_dist_cm, max_dist_cm = result
                    if result_img is not None:
                        result_path = os.path.join("kid", uid, f"{img_id}_result.jpg")
                        cv2.imwrite(result_path, result_img)

        if min_dist_cm is not None and max_dist_cm is not None:
            correct = 4.0
            kid = max(abs(min_dist_cm - correct), abs(max_dist_cm - correct))
            if kid < 0.6:
                print(f"kid = {kid:.2f}, score = 2")
                score = 2
            elif kid < 1.2:
                print(f"kid = {kid:.2f}, score = 1")
                score = 1
            else:
                print(f"kid = {kid:.2f}, score = 0")
                score = 0
        else:
            print("裁切或距離分析失敗，score = -1")
    except Exception as e:
        print(f"流程執行失敗: {e}")

    return_score(score)
