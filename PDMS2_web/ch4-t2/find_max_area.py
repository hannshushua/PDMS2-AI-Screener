import cv2
import numpy as np
import os
from pathlib import Path
import socket
import uuid
import sys

try:
    import pymysql
except ImportError:
    pymysql = None

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"


def _read_env_value(key, default):
    """從 .env 讀取值"""
    if not ENV_PATH.exists():
        return default
    try:
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            current_key, value = raw_line.split("=", 1)
            if current_key.strip() == key:
                parsed = float(value.strip())
                return parsed if parsed > 0 else default
    except Exception:
        return default
    return default


def _get_machine_id() -> str:
    """取得或生成本機識別碼"""
    if ENV_PATH.exists():
        try:
            for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line.startswith("MACHINE_ID="):
                    machine_id = line.split("=", 1)[1].strip()
                    if machine_id:
                        return machine_id
        except Exception:
            pass
    hostname = socket.gethostname()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, hostname))


def _read_db_config(key: str, default: float) -> float:
    """優先從資料庫讀取本機配置，失敗時回退到 .env"""
    if pymysql is None:
        return _read_env_value(key, default)
    
    if not ENV_PATH.exists():
        return default
    
    db_config = {}
    try:
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            k, v = raw_line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k in {"DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"}:
                db_config[k] = v
    except Exception:
        return _read_env_value(key, default)
    
    if not all(k in db_config for k in ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]):
        return _read_env_value(key, default)
    
    try:
        machine_id = _get_machine_id()
        conn = pymysql.connect(
            host=db_config["DB_HOST"],
            port=int(db_config["DB_PORT"]),
            user=db_config["DB_USER"],
            password=db_config["DB_PASSWORD"],
            database=db_config["DB_NAME"],
            charset="utf8mb4",
            autocommit=True,
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            sql_map = {"PDMS2_PX2CM": "px2cm"}
            if key not in sql_map:
                conn.close()
                return _read_env_value(key, default)
            col_name = sql_map[key]
            cur.execute(
                f"SELECT {col_name} FROM machine_configs WHERE machine_id=%s LIMIT 1",
                (machine_id,)
            )
            row = cur.fetchone()
            conn.close()
            if row and col_name in row:
                parsed = float(row[col_name])
                return parsed if parsed > 0 else default
    except Exception as e:
        print(f"[DB] 查詢遠端配置失敗: {e}，回退到本機 .env", file=sys.stderr)
    
    return _read_env_value(key, default)


def _read_env_float(key, default):
    """向後相容：改用 _read_db_config"""
    return _read_db_config(key, default)


class MaxAreaQuadFinder:
    def __init__(self, image_path):
        default_px2cm = 47.4416628993705
        self.px2cm = _read_db_config("PDMS2_PX2CM", default_px2cm)
        self.image_path = image_path
        self.img = cv2.imread(image_path)
        if self.img is None:
            raise FileNotFoundError(f"無法讀取影像: {image_path}")
        self.max_area = 0
        self.max_contour = None
        self.ordered_pts = None  # (tl, tr, br, bl)
        self.side_lengths = None  # dict

    def find_max_area_quad(self):
        gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        edges = self._build_edge_map(gray)
        image_area = float(gray.shape[0] * gray.shape[1])

        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        best_metric = float("inf")
        best_candidate = None
        largest_area = 0.0
        largest_candidate = None

        for cnt in contours:
            if cv2.contourArea(cnt) < 400:
                continue

            hull = cv2.convexHull(cnt)
            epsilon = 0.02 * cv2.arcLength(hull, True)
            approx = cv2.approxPolyDP(hull, epsilon, True)

            if len(approx) == 4:
                candidate = approx
            else:
                rect = cv2.minAreaRect(hull)
                box = cv2.boxPoints(rect)
                candidate = box.reshape(-1, 1, 2).astype(np.float32)

            area = cv2.contourArea(candidate)
            if area < 400 or area > (0.90 * image_area):
                continue

            ordered = self._order_points(candidate.reshape(4, 2))
            lengths = self._compute_side_lengths(ordered)
            short_sides_cm = sorted(
                [
                    lengths["top"] / self.px2cm,
                    lengths["right"] / self.px2cm,
                    lengths["bottom"] / self.px2cm,
                    lengths["left"] / self.px2cm,
                ]
            )[:2]

            metric = abs(short_sides_cm[0] - 7.5) + abs(short_sides_cm[1] - 7.5)
            if metric < best_metric:
                best_metric = metric
                best_candidate = candidate

            if area > largest_area:
                largest_area = area
                largest_candidate = candidate

        self.max_contour = (
            best_candidate if best_candidate is not None else largest_candidate
        )
        if self.max_contour is not None:
            self.max_area = cv2.contourArea(self.max_contour)
        if self.max_contour is not None:
            self.ordered_pts = self._order_points(self.max_contour.reshape(4, 2))
            self.side_lengths = self._compute_side_lengths(self.ordered_pts)

    @staticmethod
    def _build_edge_map(gray):
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 輸入已經是邊緣圖（黑底白線）時，避免再次 Canny 導致斷邊
        binary_like_ratio = np.mean((gray <= 20) | (gray >= 235))
        if binary_like_ratio > 0.95:
            _, edges = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        else:
            median = float(np.median(blurred))
            lower = int(max(0, 0.66 * median))
            upper = int(min(255, 1.33 * median))
            if lower >= upper:
                lower, upper = 30, 120
            edges = cv2.Canny(blurred, lower, upper)

        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        edges = cv2.dilate(edges, kernel, iterations=1)
        return edges

    def draw_and_show(self):
        if self.max_contour is not None and len(self.max_contour) >= 4:
            contour_to_draw = np.round(self.max_contour).astype(np.int32)
            cv2.drawContours(self.img, [contour_to_draw], -1, (0, 255, 0), 3)
            print("最大面積:", self.max_area)
            print("四個頂點座標:\n", self.max_contour.reshape(4, 2))
            # 顯示四邊長於左上角
            if self.side_lengths:
                print("邊長 :")
                lines = []
                for k in ["top", "right", "bottom", "left"]:
                    v = self.side_lengths[k]
                    lines.append(f"{k}: {(v / self.px2cm):.2f} cm")
                    print(f"  {k}: {v:.2f} 像素, {(v / self.px2cm):.2f} cm")
                # 標註邊長
                self._annotate_lengths()
                # 將四邊長資訊畫在左上角
                x0, y0 = 10, 30
                for i, text in enumerate(lines):
                    cv2.putText(
                        self.img,
                        text,
                        (x0 + 50, y0 + (i * 60) + 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.5,
                        (255, 255, 255),
                        2,
                        cv2.LINE_AA,
                    )
            resized = cv2.resize(self.img, (0, 0), fx=0.5, fy=0.5)
            # cv2.imshow("Max Area Quad", resized)
            name = self.image_path.split(os.sep)[-1].split("_")[0]
            result_dir = Path(__file__).resolve().parent / "result"
            result_dir.mkdir(parents=True, exist_ok=True)
            out_path = result_dir / f"{name}_max_area_quad.jpg"
            print(f"儲存結果到 {out_path}")
            cv2.imwrite(str(out_path), self.img)
            # 找出與7.5差距最大的邊
            if self.side_lengths:
                max_diff = 0
                max_diff_side = None
                for side_name in ["top", "right", "bottom", "left"]:
                    side_length_cm = self.side_lengths[side_name] / self.px2cm
                    diff = abs(side_length_cm - 7.5)
                    if diff > max_diff:
                        max_diff = diff
                        max_diff_side = side_name
                print(f"與7.5cm差距最大的邊: {max_diff_side}, 差距: {max_diff:.2f} cm")
                return self.img, max_diff
        else:
            print("找不到四邊形")

    @staticmethod
    def _order_points(pts):
        # pts: (4,2)
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # tl
        rect[2] = pts[np.argmax(s)]  # br
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # tr
        rect[3] = pts[np.argmax(diff)]  # bl
        return rect

    @staticmethod
    def _dist(a, b):
        return float(np.linalg.norm(a - b))

    def _compute_side_lengths(self, rect):
        (tl, tr, br, bl) = rect
        return {
            "top": self._dist(tl, tr),
            "right": self._dist(tr, br),
            "bottom": self._dist(br, bl),
            "left": self._dist(bl, tl),
            "perimeter": self._dist(tl, tr)
            + self._dist(tr, br)
            + self._dist(br, bl)
            + self._dist(bl, tl),
        }

    def _annotate_lengths(self):
        (tl, tr, br, bl) = self.ordered_pts.astype(int)
        pairs = {
            "top": (tl, tr),
            "right": (tr, br),
            "bottom": (br, bl),
            "left": (bl, tl),
        }
        for name, (p1, p2) in pairs.items():
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            length = self.side_lengths[name]
            cv2.putText(
                self.img,
                f"{name}",
                mid,
                cv2.FONT_HERSHEY_SIMPLEX,
                2,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

    def get_side_lengths(self):
        """取得邊長 (像素) 字典，如果尚未計算或找不到四邊形則回傳 None"""
        return self.side_lengths


# 使用範例
if __name__ == "__main__":
    finder = MaxAreaQuadFinder("edges/4_edges_paper.jpg")
    finder.find_max_area_quad()
    finder.draw_and_show()
