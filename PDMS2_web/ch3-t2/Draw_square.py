import cv2
import numpy as np
import os


def Draw_square(img_path=None, output_path="Draw_square"):
    img = cv2.imread(img_path)
    if img is None:
        print("讀取圖片失敗，請確認檔案路徑正確！")
        return

    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
    corners, ids, rejected = detector.detectMarkers(img)

    if corners:
        for marker_corners in corners:
            pts = marker_corners[0].astype(np.float32)  # 4x2
            center = np.mean(pts, axis=0)
            aruco_size = np.linalg.norm(pts[0] - pts[1])
            black_size = aruco_size * 4
            half = black_size / 2
            vec_x = pts[1] - pts[0]
            angle = np.arctan2(vec_x[1], vec_x[0])
            R = np.array(
                [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
            )
            rel_corners = np.array(
                [[-half, -half], [half, -half], [half, half], [-half, half]]
            )
            black_corners = (R @ rel_corners.T).T + center
            black_corners_int = black_corners.astype(int)
            cv2.polylines(
                img, [black_corners_int], isClosed=True, color=(0, 0, 255), thickness=1
            )
            print("黑框四角座標：")
            for i, pt in enumerate(black_corners):
                print(f"Corner {i+1}: x={pt[0]:.1f}, y={pt[1]:.1f}")
        name = img_path.split(os.sep)[-1].split("_")[0]
        path = os.path.join("ch3-t2", output_path, f"{name}.png")
        cv2.imwrite(path, img)
        print(f"結果已儲存為 '{path}'")
        return path, black_corners_int
    else:
        print("未檢測到任何 ARUCO 標記")
        return None


if __name__ == "__main__":
    path = r"extracted\img1_extracted_paper.jpg"
    path, black_corners_int = Draw_square(path)
    print(f"黑框四角座標：{black_corners_int}")
