import cv2, glob, os, math, numpy as np
from skimage.morphology import skeletonize
from collections import deque

class CrossScorer:
    def __init__(
        self,
        *,
        cm_per_pixel=None,  # None=用像素；填 0.02079 之類就用公分
        angle_min=70.0,
        angle_max=110.0,
        max_spread_cm=0.6,  # 只有在 cm_per_pixel 有值時才會使用
        out_dir=os.path.join("ch2-t3", "output"),
        output_jpg_quality=95,
    ):
        self.cm_per_pixel = cm_per_pixel
        self.ANGLE_MIN = angle_min
        self.ANGLE_MAX = angle_max
        self.MAX_SPREAD_CM = max_spread_cm
        self.OUT_DIR = out_dir
        self.OUTPUT_JPG_QUALITY = output_jpg_quality
        os.makedirs(self.OUT_DIR, exist_ok=True)

    # ---------- UI ----------
    def put_panel_top_left_autofit(
        self,
        img,
        lines,
        org=(10, 10),
        k=0.0022,
        max_wf=0.72,
        max_hf=0.55,
        bg_alpha=0.65,
    ):
        H, W = img.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX
        fs = max(0.35, min(2.0, H * k))
        for _ in range(20):
            thick = max(1, int(1 + fs * 1.3))
            pad = max(6, int(8 + fs * 6))
            vgap = max(2, int(4 + fs * 4))
            sizes = [cv2.getTextSize(t, font, fs, thick)[0] for t in lines]
            box_w = (max((s[0] for s in sizes), default=0)) + 2 * pad
            line_h = (max((s[1] for s in sizes), default=0)) + vgap
            box_h = line_h * len(lines) + 2 * pad
            if box_w <= W * max_wf and box_h <= H * max_hf:
                break
            fs *= 0.9
        x1, y1 = org
        x2, y2 = int(x1 + box_w), int(y1 + box_h)
        overlay = img.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 0), -1)
        cv2.addWeighted(overlay, bg_alpha, img, 1 - bg_alpha, 0, img)
        y = y1 + pad
        for t in lines:
            (w, h), _ = cv2.getTextSize(t, font, fs, thick)
            p = (x1 + pad, y + h)
            cv2.putText(img, t, p, font, fs, (0, 0, 0), thick + 2, cv2.LINE_AA)
            cv2.putText(img, t, p, font, fs, (255, 255, 255), thick, cv2.LINE_AA)
            y += h + vgap

    # ---------- 幾何小工具 ----------
    @staticmethod
    def calculate_distance_numpy(point1, point2):
        return math.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)

    @staticmethod
    def angle_between(v1, v2):
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 < 1e-9 or n2 < 1e-9:
            return None
        c = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1, 1))
        return math.degrees(math.acos(c))  # 0~180°

    @staticmethod
    def endpoints_junctions_center(S):
        """
        修改版：明確檢查每個骨架點的 8 鄰域。
        如果 8 個方向只有 1 個方向有點 -> 端點 (Endpoint)
        如果 8 個方向有 >=3 個方向有點 -> 交叉點 (Junction)
        """
        # S 預期是 0 或 255 (或大於0的值)
        # 找出所有骨架點的座標
        ys, xs = np.where(S > 0)
        
        if len(xs) == 0:
            return [], [], None

        ends = []
        junc = []
        
        H, W = S.shape
        
        # 遍歷每一個骨架點
        for x, y in zip(xs, ys):
            # 檢查 8 鄰域
            nb_count = 0
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    
                    # 邊界檢查與是否有骨架點
                    if 0 <= nx < W and 0 <= ny < H:
                        if S[ny, nx] > 0:
                            nb_count += 1
            
            # 判斷邏輯
            if nb_count == 1:
                ends.append((int(x), int(y)))
            elif nb_count >= 3:
                junc.append((int(x), int(y)))
        
        # 計算骨架中心 (用來排序端點遠近用)
        C = (float(xs.mean()), float(ys.mean()))
        
        return ends, junc, C

    @staticmethod
    def get_neighbors(skel, point):
        """
        UI/Path finding 用的鄰域查找
        """
        x, y = point
        neighbors = []
        H, W = skel.shape
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H:
                    if skel[ny, nx]: 
                        neighbors.append((nx, ny))
        return neighbors

    @classmethod
    def get_path_on_skeleton(cls, skel, start_pt, end_pt):
        start_node = (int(start_pt[0]), int(start_pt[1]))
        end_node = (int(end_pt[0]), int(end_pt[1]))

        queue = deque([[start_node]])
        visited = {start_node}
        found_path = None
        
        while queue:
            path = queue.popleft()
            curr = path[-1]

            if curr == end_node:
                found_path = path
                break
            
            # 容許一點點誤差
            if (curr[0]-end_node[0])**2 + (curr[1]-end_node[1])**2 <= 2:
                path.append(end_node)
                found_path = path
                break

            for nb in cls.get_neighbors(skel, curr):
                if nb not in visited:
                    visited.add(nb)
                    new_path = list(path)
                    new_path.append(nb)
                    queue.append(new_path)
        
        if found_path:
            return np.array(found_path, dtype=float)
        else:
            return None

    @staticmethod
    def fit_line_pca(pts):
        if pts is None or pts.shape[0] < 5:
            return None, None
        m = pts.mean(0)
        _, _, Vt = np.linalg.svd(pts - m, full_matrices=False)
        d = Vt[0]
        n = np.linalg.norm(d)
        return (m, d / n) if n >= 1e-9 else (None, None)

    @staticmethod
    def line_intersection(P0, d0, P1, d1):
        c = float(np.clip(d0.dot(d1), -1, 1))
        ang = math.degrees(math.acos(abs(c)))
        if ang < 10:
            return None
        A = np.stack([d0, -d1], 1)
        b = P1 - P0
        try:
            s, _ = np.linalg.lstsq(A, b, rcond=None)[0]
        except np.linalg.LinAlgError:
            return None
        return (float(P0[0] + s * d0[0]), float(P0[1] + s * d0[1]))

    # ---------- 骨架找十字 ----------
    def robust_cross_from_skeleton(self, skeleton):
        S = (skeleton > 0).astype(np.uint8) * 255 
        
        # 使用修改後的端點查找邏輯
        ends, junc, C = self.endpoints_junctions_center(S)
        
        if len(ends) < 4:
            if junc:
                P = min(junc, key=lambda p: (p[0] - C[0]) ** 2 + (p[1] - C[1]) ** 2)
            else:
                return False, "need 4 endpoints", None, None, None, None, ends
            return False, "too few endpoints", P, None, None, None, ends

        # 取離中心最遠的四端點
        ends = sorted(
            ends, key=lambda p: (p[0] - C[0]) ** 2 + (p[1] - C[1]) ** 2, reverse=True
        )[:4]
        
        pairings = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]

        best = None
        best_score = -1e18
        for (a, b), (c, d) in pairings:
            A, B = ends[a], ends[b]
            C2, D = ends[c], ends[d]
            
            # 使用路徑搜尋
            pts1 = self.get_path_on_skeleton(S, A, B)
            pts2 = self.get_path_on_skeleton(S, C2, D)

            if pts1 is None: pts1 = np.empty((0, 2))
            if pts2 is None: pts2 = np.empty((0, 2))

            P0, d0 = self.fit_line_pca(pts1)
            P1, d1 = self.fit_line_pca(pts2)
            
            if P0 is None:
                v0 = np.array([B[0] - A[0], B[1] - A[1]], float)
                v0 /= np.linalg.norm(v0) + 1e-9
                P0, d0 = np.array(A, float), v0
            if P1 is None:
                v1 = np.array([D[0] - C2[0], D[1] - C2[1]], float)
                v1 /= np.linalg.norm(v1) + 1e-9
                P1, d1 = np.array(C2, float), v1
            
            Pint = self.line_intersection(P0, d0, P1, d1)
            if Pint is None:
                continue
            
            theta = self.angle_between(d0, d1)
            n1p, n2p = len(pts1), len(pts2)
            c90 = -abs((theta or 0) - 90)
            cC = -math.hypot(Pint[0] - C[0], Pint[1] - C[1])
            pair_score = 2.0 * c90 + 0.01 * (n1p + n2p) + 0.002 * cC
            
            if pair_score > best_score:
                best_score = pair_score
                best = (Pint, (A, B), (C2, D), theta)

        if best is None:
            if junc:
                P = min(junc, key=lambda p: (p[0] - C[0]) ** 2 + (p[1] - C[1]) ** 2)
                return False, "two lines do not intersect", P, None, None, None, ends
            return False, "two lines do not intersect", None, None, None, None, ends

        P, pair1, pair2, theta = best
        return True, "", P, pair1, pair2, theta, ends

    # ---------- 單張處理 ----------
    def score_image(self, img_path):
        result = {
            "path": img_path,
            "score": 0,
            "reason": "init",
            "theta_deg": None,
            "arms_px": None,
            "arms_cm": None,
            "spread_px": None,
            "spread_cm": None,
        }

        # ---- 前處理 ----
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            result["reason"] = "cannot read image"
            return result, None, None, None

        blur = cv2.GaussianBlur(img, (3, 3), 0)
        # 把 INV 拿掉，維持黑底白線！
        _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        skel_bool = skeletonize(binary > 0)
        skel = skel_bool.astype(np.uint8) * 255

        ok, reason, P, p1, p2, theta, ends = self.robust_cross_from_skeleton(skel)

        vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        skel_vis = cv2.dilate(
            skel, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), 1
        )
        overlay = vis.copy()
        overlay[skel_vis > 0] = [0, 0, 255]
        vis = cv2.addWeighted(vis, 0.7, overlay, 0.3, 0)

        score = 0
        shown_reason = "no intersection"
        dists_vals, spread_val = None, None

        if ok and P is not None and theta is not None and p1 and p2:
            pts = [p1[0], p1[1], p2[0], p2[1]]
            d_px = [
                self.calculate_distance_numpy(P, (x, y)) for (x, y) in pts
            ]

            if self.cm_per_pixel is None:
                result["arms_px"] = [float(d) for d in d_px]
                result["spread_px"] = float(max(d_px) - min(d_px)) if d_px else None
                dists_vals = result["arms_px"]
                spread_val = result["spread_px"]
                spread_ok = True
            else:
                d_cm = [d * self.cm_per_pixel for d in d_px]
                result["arms_px"] = [float(d) for d in d_px]
                result["arms_cm"] = [float(d) for d in d_cm]
                result["spread_px"] = float(max(d_px) - min(d_px)) if d_px else None
                result["spread_cm"] = float(max(d_cm) - min(d_cm)) if d_cm else None
                dists_vals = result["arms_cm"]
                spread_val = result["spread_cm"]
                spread_ok = spread_val is not None and spread_val <= self.MAX_SPREAD_CM

            angle_ok = self.ANGLE_MIN <= theta <= self.ANGLE_MAX

            if angle_ok and spread_ok:
                score = 2
                shown_reason = (
                    "angle ok"
                    if self.cm_per_pixel is None
                    else f"angle ok & spread<={self.MAX_SPREAD_CM:.2f}cm"
                )
            else:
                score = 1
                fails = []
                if not angle_ok:
                    fails.append(
                        f"angle {theta:.2f} not in [{self.ANGLE_MIN:.0f},{self.ANGLE_MAX:.0f}]"
                    )
                if self.cm_per_pixel is not None and not spread_ok:
                    fails.append(
                        f"spread {spread_val:.2f}cm > {self.MAX_SPREAD_CM:.2f}cm"
                    )
                shown_reason = "; ".join(fails) if fails else "partial"

            cv2.line(vis, p1[0], p1[1], (0, 255, 0), 2)
            cv2.line(vis, p2[0], p2[1], (255, 0, 0), 2)
            cv2.circle(vis, (int(round(P[0])), int(round(P[1]))), 5, (0, 0, 255), -1)

            result["theta_deg"] = float(theta)

        else:
            score = 0
            shown_reason = reason or "no intersection"

        for pt in ends[:4] if ends else []:
            cv2.circle(vis, (int(pt[0]), int(pt[1])), 5, (0, 255, 0), -1)

        theta_str = (
            "-" if result["theta_deg"] is None else f'{result["theta_deg"]:.2f} deg'
        )
        arms_px_str = (
            "-"
            if result["arms_px"] is None
            else ", ".join(f"{d:.2f}" for d in result["arms_px"])
        )
        panel = [
            f"Score: {score}",
            f"Reason: {shown_reason}",
            f"Theta: {theta_str}",
            f"Arms(px): {arms_px_str}",
        ]
        if self.cm_per_pixel is not None:
            arms_cm_str = (
                "-"
                if result["arms_cm"] is None
                else ", ".join(f"{d:.2f}" for d in result["arms_cm"])
            )
            spread_cm_str = (
                "-" if result["spread_cm"] is None else f"{result['spread_cm']:.2f} cm"
            )
            panel.append(f"Arms(cm): {arms_cm_str}")
            panel.append(f"Spread: {spread_cm_str}")
        else:
            spread_px_str = (
                "-" if result["spread_px"] is None else f"{result['spread_px']:.2f} px"
            )
            panel.append(f"Spread: {spread_px_str}")

        self.put_panel_top_left_autofit(vis, panel, org=(8, 8), k=0.0022, bg_alpha=0.65)

        result["score"] = int(score)
        result["reason"] = shown_reason

        base = os.path.basename(img_path)
        img_path_out = os.path.join(self.OUT_DIR, f"img_path_{base}")
        bin_path = os.path.join(self.OUT_DIR, f"binary_{base}")
        skel_path = os.path.join(self.OUT_DIR, f"skeleton_{base}")
        vis_path = os.path.join(self.OUT_DIR, f"processed_{base}")

        cv2.imwrite(img_path_out, img)
        cv2.imwrite(bin_path, binary)
        cv2.imwrite(skel_path, skel)
        cv2.imwrite(vis_path, vis, [cv2.IMWRITE_JPEG_QUALITY, self.OUTPUT_JPG_QUALITY])

        return result, vis, bin_path, skel_path, vis_path

    # ---------- 批次處理 ----------
    def score_folder(self, image_folder, pattern):
        paths = sorted(glob.glob(os.path.join(image_folder, pattern)))
        print("找到圖片檔案:", paths)
        results = []
        for p in paths:
            print("\n處理圖片:", os.path.basename(p))
            res, b, s, v = self.score_image(p)
            print("Saved:", v)
            results.append(res)
        return results


if __name__ == "__main__":
    scorer = CrossScorer(
        cm_per_pixel=0.02079, angle_min=70.0, angle_max=110.0, max_spread_cm=0.6
    )

    try:
        results = scorer.score_image(r"2.jpg")
        print("所有結果:", results[0])
    except Exception as e:
        print(f"測試執行失敗: {e}")