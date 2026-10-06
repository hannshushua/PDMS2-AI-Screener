# square.py
# -*- coding: utf-8 -*-
import os, cv2, math, numpy as np
from skimage.morphology import skeletonize
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent

__all__ = ["SquareGapAnalyzer"]


class SquareGapAnalyzer:
    def __init__(
        self,
        *,
        # —— 評分門檻（接近 90°）——
        dev_good: float = 15.0,
        dev_ok: float = 30.0,
        # —— 端點合併半徑 / 面積下限 ——
        merge_eps_px: int = 12,
        area_min_ratio: float = 0.002,
        # —— 字體係數 ——
        panel_fs_coef: float = 0.00015,
        corner_fs_coef: float = 0.00050,
        # —— 是否強制用形態學骨架（避免 ximgproc 差異）——
        force_morph: bool = False,
        # —— 輸出資料夾 ——
        out_dir: Optional[str] = None,
    ):
        if out_dir is None:
            out_dir = str(BASE_DIR / "output")

        # 輸出資料夾
        self.OUT_DIR = out_dir
        os.makedirs(self.OUT_DIR, exist_ok=True)

        # 參數
        self.DEV_GOOD, self.DEV_OK = dev_good, dev_ok
        self.MERGE_EPS_PX = merge_eps_px
        self.AREA_MIN_RATIO = area_min_ratio
        self.PANEL_FS_COEF, self.CORNER_FS_COEF = panel_fs_coef, corner_fs_coef
        self.FORCE_MORPH = bool(force_morph)

    # ===================== 小工具 =====================
    @staticmethod
    def interior_angle(a, b, c):
        """計算 b 點的內角"""
        ba = np.asarray(a, float) - np.asarray(b, float)
        bc = np.asarray(c, float) - np.asarray(b, float)
        n1, n2 = np.linalg.norm(ba), np.linalg.norm(bc)
        if n1 < 1e-9 or n2 < 1e-9:
            return float("nan")
        cosine = np.dot(ba, bc) / (n1 * n2)
        cosine = np.clip(cosine, -1.0, 1.0)
        angle = np.arccos(cosine)
        return np.degrees(angle)

    @staticmethod
    def cyclic(pts):
        """按角度排序點（逆時針）"""
        P = np.asarray(pts, float)
        center = P.mean(axis=0)
        angles = np.arctan2(P[:, 1] - center[1], P[:, 0] - center[0])
        return P[np.argsort(angles)]

    @staticmethod
    def poly_area(P):
        x = P[:, 0]
        y = P[:, 1]
        return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

    # ===================== 端點偵測 =====================
    def find_endpoints(self, skel):
        """簡單直接的端點偵測：鄰居數 == 1"""
        endpoints = []
        # 確保是二值圖（0/1）
        binary = (skel > 0).astype(np.uint8)

        for y in range(1, binary.shape[0] - 1):
            for x in range(1, binary.shape[1] - 1):
                if binary[y, x] == 1:
                    neighbors = np.sum(binary[y - 1 : y + 2, x - 1 : x + 2]) - 1
                    if neighbors == 1:
                        endpoints.append((x, y))
        return endpoints

    def merge_points(self, points, eps=None):
        if eps is None:
            eps = self.MERGE_EPS_PX
        pts = [np.array(p, float) for p in points]
        out = []
        while pts:
            p = pts.pop(0)
            cluster = [p]
            keep = []
            for q in pts:
                if np.linalg.norm(p - q) <= eps:
                    cluster.append(q)
                else:
                    keep.append(q)
            pts = keep
            c = np.mean(cluster, axis=0)
            out.append((int(round(c[0])), int(round(c[1]))))
        return out

    @staticmethod
    def pair_greedy(points):
        pts = points[:]
        pairs = []
        while len(pts) >= 2:
            p = pts.pop(0)
            distances = [(p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for q in pts]
            j = int(np.argmin(distances))
            pairs.append((p, pts.pop(j)))
        return pairs

    # ===================== 缺口數統計 =====================
    def count_gaps_from_skeleton(self, skel, img_shape):
        """找端點 → 合併 → 計算缺口數"""
        # 找端點
        endpoints = self.find_endpoints(skel)

        # 合併端點
        H, W = img_shape[:2]
        diag = math.hypot(W, H)
        eps = max(self.MERGE_EPS_PX, int(0.030 * diag))
        endpoints = self.merge_points(endpoints, eps=eps)

        # 過濾邊界端點
        endpoints = [(x, y) for x, y in endpoints if 1 <= x < W - 1 and 1 <= y < H - 1]

        # 計算缺口數
        gaps = len(endpoints) // 2

        return endpoints, gaps

    # ===================== 角度計算（輪廓逼近法）=====================
    def get_angles_from_skeleton(self, skel, img_shape):
        """用輪廓逼近找四個角點並計算內角"""

        # 建立 kernel，3x3 稍微膨脹
        kernel = np.ones((3, 3), np.uint8)

        # 膨脹 (讓線條變粗)
        skel = cv2.dilate(skel, kernel, iterations=1)

        # 1. 找輪廓
        contours, _ = cv2.findContours(skel, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return dict(ok=False, reason="no contour")

        # 2. 取最大輪廓
        cnt = max(contours, key=cv2.contourArea)

        # 檢查面積
        H, W = img_shape[:2]
        if cv2.contourArea(cnt) < self.AREA_MIN_RATIO * (H * W):
            return dict(ok=False, reason="contour too small")

        # 3. 凸包 + 逼近成四邊形
        hull = cv2.convexHull(cnt)
        peri = cv2.arcLength(hull, True)

        # 嘗試不同的 epsilon 值
        approx = None
        for eps in [0.01, 0.02, 0.03, 0.04, 0.05]:
            temp = cv2.approxPolyDP(hull, eps * peri, True)
            if len(temp) == 4:
                approx = temp
                break

        if approx is None or len(approx) != 4:
            return dict(ok=False, reason="cannot approximate to quad")

        # 4. 排序角點（逆時針）
        corners = approx.reshape(-1, 2).astype(float)
        corners = self.cyclic(corners)

        # 5. 計算四個內角
        angles = []
        for i in range(4):
            p_prev = corners[(i - 1) % 4]
            p_curr = corners[i]
            p_next = corners[(i + 1) % 4]
            angle = self.interior_angle(p_prev, p_curr, p_next)
            angles.append(angle)

        # 檢查角度是否合理
        if any(not np.isfinite(a) or a < 30 or a > 150 for a in angles):
            return dict(ok=False, reason="angles out of range")

        # 6. 計算最大偏差
        max_deviation = max(abs(a - 90) for a in angles)

        return dict(
            ok=True,
            corners=corners,
            thetas=angles,
            dev=max_deviation,
            reason="contour_approx",
        )

    # ===================== 可視化 =====================
    def draw_gap_image(self, skel, endpoints, pairs, gaps, out_path):
        vis = cv2.cvtColor(skel, cv2.COLOR_GRAY2BGR)
        for x, y in endpoints:
            cv2.circle(vis, (x, y), 4, (0, 0, 255), -1)
        cv2.putText(
            vis,
            f"Endpoints: {len(endpoints)}  Gaps: {gaps}",
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.25,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
        cv2.imwrite(out_path, vis)

    def draw_score_image(self, img, score, reason, thetas, corners, gaps, out_path):
        vis = img.copy()
        H, W = vis.shape[:2]
        L = max(H, W)
        fs = float(np.clip(L * self.PANEL_FS_COEF, 0.25, 1.0)) * 1.5
        th = max(1, int(1 + fs * 1.2))
        step = int(18 + fs * 26)
        y = int(12 + fs * 22)

        panel = [f"Score: {score}", f"Reason: {reason}", f"Gaps: {gaps}"]
        if thetas is not None:
            mx = max(abs(t - 90) for t in thetas)
            panel += [
                f"Angles: {' | '.join(f'{t:.1f}' for t in thetas)}",
                f"Max dev: {mx:.1f} deg",
            ]
        else:
            panel += ["Angles: -", "Max dev: -"]

        for t in panel:
            cv2.putText(
                vis,
                t,
                (10, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                fs,
                (0, 0, 0),
                th,
                cv2.LINE_AA,
            )
            y += step

        if corners is not None and thetas is not None and len(corners) == 4:
            fs_c = float(np.clip(L * self.CORNER_FS_COEF, 0.45, 1.0))
            th_c = max(1, int(1 + fs_c * 1.1))
            r = max(2, int(L * 0.004))
            P = np.asarray(corners, float)
            for i in range(4):
                x, y = int(round(P[i][0])), int(round(P[i][1]))
                cv2.circle(vis, (x, y), r, (0, 255, 0), 1)
                cv2.putText(
                    vis,
                    f"{thetas[i]:.1f}",
                    (x + 6, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    fs_c,
                    (0, 255, 0),
                    th_c,
                    cv2.LINE_AA,
                )
        cv2.imwrite(out_path, vis)
        return vis

    # ===================== 評分 =====================
    def score_from_gaps_and_angles(self, gaps, thetas):
        if gaps >= 2:
            return 0, ">=2 gaps"

        if thetas is None:
            if gaps == 1:
                return 1, "1 gap (angles not found → default 1)"
            return 0, f"{gaps} gap(s) but angles not found"

        mx = max(abs(t - 90) for t in thetas)

        if gaps == 1:
            if mx <= 30:
                return 1, "1 gap & max dev <= 30"
            else:
                return 0, "1 gap & max dev > 30"

        if mx <= self.DEV_GOOD:
            return 2, f"0 gap & max dev <= {self.DEV_GOOD}"
        if mx <= self.DEV_OK:
            return 1, f"0 gap & max dev {self.DEV_GOOD+1}–{self.DEV_OK}"
        return 0, f"0 gap & max dev > {self.DEV_OK}"

    # ===================== 單張處理 =====================
    def process_image(self, img_path: str):
        SCORE = 0

        # 讀不到圖片直接回傳 0
        img = cv2.imread(img_path)
        if img is None:
            return dict(ok=False, error=f"read fail: {img_path}", score=SCORE)

        # 1) 二值化與骨架
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        blur = cv2.GaussianBlur(img, (3, 3), 0)
        _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 保險機制：紙面亮度不均 (中央亮、邊角暗) 時，全域 Otsu 會把「較亮的紙」和
        # 「較暗的紙」切成兩類，半張紙被誤判成筆跡。正常照片的筆跡覆蓋率約 1~2%，
        # 一旦超過 INK_RATIO_MAX 就代表二值化整個壞掉，改用背景除法打光校正重做。
        # 正常照片不會進到這裡，所以既有分數不受影響。
        INK_RATIO_MAX = 0.05
        if (binary > 0).mean() > INK_RATIO_MAX:
            h_, w_ = img.shape[:2]
            k_ = max(31, (min(h_, w_) // 8) | 1)
            background = cv2.morphologyEx(
                img, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_, k_))
            )
            flat = cv2.divide(img, background, scale=255)
            blur = cv2.GaussianBlur(flat, (3, 3), 0)
            _, binary = cv2.threshold(
                blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )
            print(f"[SquareGapAnalyzer] 偵測到打光不均，已改用背景除法重新二值化: {img_path}")

        # cv2.imshow('ori', img)
        # cv2.imshow('binary', binary)

        # cv2.imshow 顯示灰階時是把 0 視為黑、255 視為白
        skel_bool = skeletonize(binary > 0)  # True/False
        skel = skel_bool.astype(np.uint8) * 255  # 0/255，便於顯示

        # cv2.imshow('skel', skel)
        # cv2.waitKey(0)

        base = os.path.basename(img_path)
        out_skel = os.path.join(self.OUT_DIR, f"skeleton_{base}")
        cv2.imwrite(out_skel, skel)

        # 2) 數缺口
        endpoints, gaps = self.count_gaps_from_skeleton(skel, img.shape)

        # 3) ★ 早退：>=2 個缺口 -> 直接 0 分
        if gaps >= 2:
            score, reason = 0, ">=2 gaps"
            out_gap = os.path.join(self.OUT_DIR, f"gap_{base}")
            out_score = os.path.join(self.OUT_DIR, f"score_{base}")

            self.draw_gap_image(
                skel, endpoints, self.pair_greedy(endpoints), gaps, out_gap
            )
            result_img = self.draw_score_image(
                img, score, reason, None, None, gaps, out_score
            )

            return (
                dict(
                    ok=True,
                    gaps=gaps,
                    score=score,
                    reason=reason,
                    thetas=None,
                    corners=None,
                    out_skeleton=out_skel,
                    out_gap=out_gap,
                    out_score=out_score,
                ),
                result_img,
            )

        # 4) 只有 <2 缺口才去算角度
        angle_res = self.get_angles_from_skeleton(skel, img.shape)
        thetas = angle_res.get("thetas")
        corners = angle_res.get("corners")
        reason_tag = angle_res.get("reason", "unknown")

        score, base_reason = self.score_from_gaps_and_angles(gaps, thetas)
        reason = f"{base_reason} | method: {reason_tag}"

        out_gap = os.path.join(self.OUT_DIR, f"gap_{base}")
        out_score = os.path.join(self.OUT_DIR, f"score_{base}")
        self.draw_gap_image(skel, endpoints, self.pair_greedy(endpoints), gaps, out_gap)
        result_img = self.draw_score_image(
            img, score, reason, thetas, corners, gaps, out_score
        )

        return (
            dict(
                ok=True,
                gaps=gaps,
                score=score,
                reason=reason,
                thetas=thetas,
                corners=corners,
                out_skeleton=out_skel,
                out_gap=out_gap,
                out_score=out_score,
            ),
            result_img,
        )


# ===================== 最底下跑流程（示例） =====================
if __name__ == "__main__":
    image_path = r"cropped_a4\S__75472904_0_a4_cropped.jpg"
    analyzer = SquareGapAnalyzer(out_dir=str(BASE_DIR / "output"))
    res = analyzer.process_image(image_path)

    if not res.get("ok", False):
        print("[Err]", res.get("error", "unknown error"))
    else:
        print(f"[Score] score={res['score']} gaps={res['gaps']} reason={res['reason']}")
        print(
            "thetas:",
            None if res["thetas"] is None else [round(t, 1) for t in res["thetas"]],
        )
        print("saved:", res["out_skeleton"], res["out_gap"], res["out_score"])
