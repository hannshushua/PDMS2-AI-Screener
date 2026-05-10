from PaperDetector_edge import PaperDetector_edges
from find_max_area import MaxAreaQuadFinder
import cv2

import sys
import os


def return_score(score):
    sys.exit(int(score))


if __name__ == "__main__":
    # 檢查是否有傳入 id 參數
    score = -1
    if len(sys.argv) > 2:
        try:
            # 使用傳入的 uid 和 id 作為圖片路徑
            uid = sys.argv[1]
            img_id = sys.argv[2]
            # uid = "lull222"
            # img_id = "ch3-t1"
            image_path = os.path.join("kid", uid, f"{img_id}.jpg")
            # for img in range(1, 8):
            # image_path = rf"img\{img}.jpg"

            img = cv2.imread(image_path)
            detector = PaperDetector_edges(image_path)
            edges_path = detector.detect_paper_by_color()
            if edges_path is not None:
                finder = MaxAreaQuadFinder(edges_path)
                finder.find_max_area_quad()
                result_img, kid = finder.draw_and_show()
                result_path = os.path.join("kid", uid, f"{img_id}_result.jpg")
                cv2.imwrite(result_path, result_img)
            if kid is not None:
                if kid < 0.3:
                    print(f"kid = {kid:.2f}, score = 2")
                    score = 2
                elif kid < 1.2:
                    print(f"kid = {kid:.2f}, score = 1")
                    score = 1
                else:
                    print(f"kid = {kid:.2f}, score = 0")
                    score = 0

            return_score(score)
        except Exception as e:
            print(f"[ERROR] ch4-t2 執行失敗: {e}")
            return_score(-1)
    else:
        return_score(-1)
