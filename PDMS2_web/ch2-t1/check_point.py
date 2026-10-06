import cv2
import numpy as np
from skimage.morphology import skeletonize
import math


class check_point:

    def __init__(self, SCALE):
        self.SCALE = SCALE

    def check_point(self, url):

        # 讀取圖片並二值化
        img = cv2.imread(url, cv2.IMREAD_GRAYSCALE)
        blur = cv2.GaussianBlur(img, (3, 3), 0)
        _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 骨架化
        skeleton = skeletonize(binary > 0).astype(np.uint8)

        # 找端點（8鄰域只有1個鄰居的點）
        def find_endpoints(skel):
            endpoints = []
            for y in range(1, skel.shape[0] - 1):
                for x in range(1, skel.shape[1] - 1):
                    if skel[y, x]:
                        neighbors = np.sum(skel[y - 1 : y + 2, x - 1 : x + 2]) - 1
                        if neighbors == 1:
                            endpoints.append((x, y))
            return endpoints

        # 使用 numpy 計算距離
        def calculate_distance_numpy(point1, point2):
            """使用 numpy 計算兩點距離"""
            return math.sqrt(
                (point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2
            )

        # 找8鄰域的骨架點
        def get_neighbors(skel, point):
            x, y = point
            neighbors = []
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < skel.shape[1] and 0 <= ny < skel.shape[0]:
                        if skel[ny, nx]:
                            neighbors.append((nx, ny))
            return neighbors

        # 路徑追蹤函數
        def trace_path(skel, start_point):
            if not skel[start_point[1], start_point[0]]:
                return []

            path = [start_point]
            visited = set([start_point])
            current = start_point

            while True:
                neighbors = get_neighbors(skel, current)
                # 過濾掉已經訪問過的點
                unvisited_neighbors = [n for n in neighbors if n not in visited]

                if not unvisited_neighbors:
                    break

                # 選擇下一個點（這裡選擇第一個未訪問的鄰居）
                next_point = unvisited_neighbors[0]
                path.append(next_point)
                visited.add(next_point)
                current = next_point

            return path

        # 找距離左下角最近的端點作為開頭
        def find_start_endpoint(endpoints, img_shape):
            if not endpoints:
                return None
            bottom_left_x, bottom_left_y = 0, img_shape[0]
            min_dist = float("inf")
            start_point = None

            for point in endpoints:
                dist = math.sqrt(
                    (point[0] - bottom_left_x) ** 2 + (point[1] - bottom_left_y) ** 2
                )
                if dist < min_dist:
                    min_dist = dist
                    start_point = point

            return start_point

        endpoints = find_endpoints(skeleton)
        # print("所有端點座標:", endpoints)

        if endpoints:
            if len(endpoints) == 2:
                dist_specific = calculate_distance_numpy(endpoints[0], endpoints[1])
                # print(f"\n起點 到 終點的距離: {dist_specific:.2f} 像素")

                # 把二值化圖像轉成可顯示彩色的 BGR 圖片
                binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

                # 畫紅色端點
                for x, y in endpoints:
                    cv2.circle(binary_bgr, (x, y), 3, (0, 0, 255), -1)

                # 用綠色線連接它
                cv2.line(binary_bgr, endpoints[0], endpoints[1], (0, 255, 0), 2)

                # 把骨架轉成可顯示的 BGR 圖片（用於對比）
                skeleton_bgr = cv2.cvtColor(skeleton * 255, cv2.COLOR_GRAY2BGR)

                # 在骨架圖上也畫端點和連線
                for x, y in endpoints:
                    cv2.circle(skeleton_bgr, (x, y), 3, (0, 0, 255), -1)
                    cv2.line(skeleton_bgr, endpoints[0], endpoints[1], (0, 255, 0), 2)

                # 顯示結果
                img = cv2.resize(img, (0, 0), fx=self.SCALE, fy=self.SCALE)
                # cv2.imshow('img', img)
                binary_bgr = cv2.resize(
                    binary_bgr, (0, 0), fx=self.SCALE, fy=self.SCALE
                )
                # cv2.imshow('binary_with_endpoints', binary_bgr)  # 在二值化圖像上顯示
                skeleton_bgr = cv2.resize(
                    skeleton_bgr, (0, 0), fx=self.SCALE, fy=self.SCALE
                )
                # cv2.imshow('skeleton_with_endpoints', skeleton_bgr)  # 在骨架圖像上顯示
                return float(dist_specific), skeleton_bgr

            # 只有一個突出的線段
            elif len(endpoints) == 1:
                # 選擇開頭點
                start_point = find_start_endpoint(endpoints, skeleton.shape)
                # print(f"選定的開頭點: {start_point}")

                # 進行路徑追蹤
                main_path = trace_path(skeleton, start_point)

                # 計算路徑總長度
                if len(main_path) > 1:
                    total_length = 0
                    for i in range(len(main_path) - 1):
                        dist = math.sqrt(
                            (main_path[i + 1][0] - main_path[i][0]) ** 2
                            + (main_path[i + 1][1] - main_path[i][1]) ** 2
                        )
                        total_length += dist

                # 視覺化結果
                skeleton_bgr = cv2.cvtColor(skeleton * 255, cv2.COLOR_GRAY2BGR)

                # 畫所有端點（紅色小圓圈）
                for x, y in endpoints:
                    cv2.circle(skeleton_bgr, (x, y), 3, (0, 0, 255), -1)

                if endpoints and len(main_path) > 0:
                    # 畫開頭點（綠色大圓圈）
                    cv2.circle(skeleton_bgr, start_point, 3, (0, 255, 0), 2)
                    cv2.putText(
                        skeleton_bgr,
                        "START",
                        (start_point[0] + 10, start_point[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2,
                    )

                    # 畫終點（黃色圓圈）
                    if len(main_path) > 1:
                        end_point = main_path[-1]
                        cv2.circle(skeleton_bgr, end_point, 3, (0, 255, 255), 2)
                        cv2.putText(
                            skeleton_bgr,
                            "END",
                            (end_point[0] + 10, end_point[1] + 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 255, 255),
                            2,
                        )

                dist_specific = calculate_distance_numpy(main_path[0], main_path[-1])
                cv2.line(skeleton_bgr, main_path[0], main_path[-1], (255, 255, 255), 2)
                # print(f'端點距離 : {dist_specific}')

                # 顯示結果

                img = cv2.resize(img, (0, 0), fx=self.SCALE, fy=self.SCALE)
                # cv2.imshow('img', img)
                binary = cv2.resize(binary, (0, 0), fx=self.SCALE, fy=self.SCALE)
                # cv2.imshow('binary_with_endpoints', binary)  # 在二值化圖像上顯示
                skeleton_bgr = cv2.resize(
                    skeleton_bgr, (0, 0), fx=self.SCALE, fy=self.SCALE
                )
                # cv2.imshow('skeleton_with_endpoints', skeleton_bgr)  # 在骨架圖像上顯示
                return float(dist_specific), skeleton_bgr

            else:
                dist_specific = calculate_distance_numpy(endpoints[0], endpoints[1])
                # print(f"\n起點 到 終點的距離: {dist_specific:.2f} 像素")

                # 把二值化圖像轉成可顯示彩色的 BGR 圖片
                binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

                # 畫紅色端點
                for x, y in endpoints:
                    cv2.circle(binary_bgr, (x, y), 3, (0, 0, 255), -1)

                # 把骨架轉成可顯示的 BGR 圖片（用於對比）
                skeleton_bgr = cv2.cvtColor(skeleton * 255, cv2.COLOR_GRAY2BGR)

                # 在骨架圖上也畫端點和連線
                for x, y in endpoints:
                    cv2.circle(skeleton_bgr, (x, y), 3, (0, 0, 255), -1)

                # 顯示結果

                img = cv2.resize(img, (0, 0), fx=self.SCALE, fy=self.SCALE)
                # cv2.imshow('img', img)
                binary_bgr = cv2.resize(
                    binary_bgr, (0, 0), fx=self.SCALE, fy=self.SCALE
                )
                # cv2.imshow('binary_with_endpoints', binary_bgr)  # 在二值化圖像上顯示
                skeleton_bgr = cv2.resize(
                    skeleton_bgr, (0, 0), fx=self.SCALE, fy=self.SCALE
                )
                # cv2.imshow('skeleton_with_endpoints', skeleton_bgr)  # 在骨架圖像上顯示

                return float(dist_specific), skeleton_bgr
        # 完美連接的圖形
        else:

            skeleton_bgr = cv2.cvtColor(skeleton * 255, cv2.COLOR_GRAY2BGR)
            img = cv2.resize(img, (0, 0), fx=self.SCALE, fy=self.SCALE)
            cv2.putText(
                skeleton_bgr,
                "Perfect !",
                (20, 50),
                cv2.FONT_HERSHEY_COMPLEX,
                0.3,
                (0, 255, 0),
                1,
            )
            binary = cv2.resize(binary, (0, 0), fx=self.SCALE, fy=self.SCALE)
            cv2.putText(
                binary,
                "Perfect !",
                (20, 50),
                cv2.FONT_HERSHEY_COMPLEX,
                0.3,
                (0, 255, 0),
                1,
            )
            skeleton_bgr = cv2.resize(
                skeleton_bgr, (0, 0), fx=self.SCALE, fy=self.SCALE
            )

            # cv2.imshow('Origin pic', img)
            # cv2.imshow('binary', binary)
            # cv2.imshow('path_tracing_result', skeleton_bgr)

            return float(0.0), skeleton_bgr


if __name__ == "__main__":

    SCALE = 3
    # for i in range(5):
    #     url = f"ready\1_{i}.jpg"
    #     cp = check_point(SCALE)
    #     cp.check_point(url)
    url = f"ready\\1_1.jpg"
    cp = check_point(SCALE)
    cp.check_point(url)
