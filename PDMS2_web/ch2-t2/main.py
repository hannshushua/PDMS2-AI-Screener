# ch2-t2：YOLO+SAM2 找紙張 -> 該範圍內 CV 圈出圖形 -> 4類分類(square) -> SquareGapAnalyzer 評分
import os
import sys
import cv2
import numpy as np
import socket
import uuid
from pathlib import Path
from square_detect import SquareGapAnalyzer

try:
    import pymysql
except ImportError:
    pymysql = None

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"
target_dir = BASE_DIR
# 共用模組：prepare(分類前) + classify(分類)
sys.path.insert(0, str(BASE_DIR.parent))
from prepare import Preparer
from classify import Classifier


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


def return_score(score):
    sys.exit(int(score))


def get_pixel_per_cm_from_a4(
    image_path,
    real_width_cm=29.7,
    show_debug=False,
    save_cropped=True,
    output_folder=target_dir / "cropped_a4",
):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("圖片讀取失敗，請確認路徑正確")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(blur, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    a4_contour = max(contours, key=cv2.contourArea)
    epsilon = 0.02 * cv2.arcLength(a4_contour, True)
    approx = cv2.approxPolyDP(a4_contour, epsilon, True)

    if len(approx) != 4:
        raise ValueError("無法偵測 A4 紙四邊形輪廓")

    if show_debug:
        debug_img = img.copy()
        cv2.drawContours(debug_img, [approx], -1, (0, 0, 255), 3)
        cv2.imshow("Detected A4 Contour", cv2.resize(debug_img, (800, 600)))
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    # 整理四個角點
    pts = approx.reshape(4, 2).astype(np.float32)
    pts = sorted(pts, key=lambda p: p[0])  # 先左右
    left = sorted(pts[0:2], key=lambda p: p[1])
    right = sorted(pts[2:4], key=lambda p: p[1])
    tl, bl = left
    tr, br = right

    # 計算像素/公分比例
    a4_pixel_width = np.linalg.norm(tr - tl)
    pixel_per_cm = float(a4_pixel_width / real_width_cm)  # 轉換為 Python 原生 float

    # 儲存裁切後的A4區域
    cropped_path = None
    if save_cropped:
        # 建立輸出資料夾
        os.makedirs(output_folder, exist_ok=True)

        # 計算原始A4區域的實際尺寸
        width1 = np.linalg.norm(tr - tl)  # 上邊長度
        width2 = np.linalg.norm(br - bl)  # 下邊長度
        height1 = np.linalg.norm(tl - bl)  # 左邊長度
        height2 = np.linalg.norm(tr - br)  # 右邊長度

        # 取平均值作為目標尺寸，保持原始比例
        target_width = int((width1 + width2) / 2)
        target_height = int((height1 + height2) / 2)

        # 原始四個角點（順序：左上、右上、右下、左下）
        src_pts = np.array([tl, tr, br, bl], dtype=np.float32)

        # 目標四個角點
        dst_pts = np.array(
            [
                [0, 0],
                [target_width, 0],
                [target_width, target_height],
                [0, target_height],
            ],
            dtype=np.float32,
        )

        # 計算透視變換矩陣
        transform_matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)

        # 進行透視變換
        warped = cv2.warpPerspective(
            img, transform_matrix, (target_width, target_height)
        )

        # 儲存裁切後的圖片
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        cropped_filename = f"{image_name}_a4_cropped.jpg"
        cropped_path = os.path.join(output_folder, cropped_filename)
        cv2.imwrite(cropped_path, warped)

        print(f"A4區域已儲存至: {cropped_path}")

    return pixel_per_cm, None, cropped_path


def main(img_path):
    # ==參數==#
    real_width_cm = 29.7
    SCALE = 2
    SCORE = -1
    TARGET = "square"  # ch2-t2 目標形狀
    # ==參數==#

    print(f"\n=== 處理 {img_path} ===\n")

    # 得出 px->cm 與 warped A4（評分尺度，維持原本 A4 量測不變）
    try:
        _, _, cropped_path = get_pixel_per_cm_from_a4(
            img_path,
            show_debug=False,  # 關掉視覺化避免卡住
            save_cropped=True,
            output_folder=target_dir / "cropped_a4",
        )
        pixel_per_cm = _read_db_config("PDMS2_PX2CM", 47.4416628993705)
        print(f"{img_path} pixel_per_cm = {pixel_per_cm}")
    except ValueError as e:
        print(f"⚠️ 跳過 {img_path}：{e}")
        return -1, cv2.imread(img_path)

    # prepare：找紙張 + CV 圈選 + binary
    print("\n==prepare 前處理==")
    prep = Preparer()
    stem = os.path.splitext(os.path.basename(img_path))[0]
    r = prep.prepare(img_path, target_dir / "ready", stem)
    if not r["ok"]:
        print(f"未圈到圖形（{r['reason']}）")
        return -1, r.get("vis")

    # classify：4 類分類（僅作為閘門）
    print("\n==classify 分類==")
    clf = Classifier()
    label, conf = clf.classify(r["binary_bgr"])
    print(f"{img_path} → {label} ({conf*100:.2f}%)")

    # 非目標形狀 -> 0 分
    if label != TARGET:
        img = cv2.imread(r["color_path"])
        cv2.putText(img, "Other !", (30, 50), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 255), 2)
        print(f"{img_path} is {label}!")
        return 0, img

    # 方形 -> 交給 SquareGapAnalyzer 評分（評分邏輯不變，仍吃 warped A4）
    SGA = SquareGapAnalyzer()
    res, result_img = SGA.process_image(cropped_path)
    return res["score"], result_img


if __name__ == "__main__":
    # 測試模式：python main.py --img 照片路徑
    if len(sys.argv) > 2 and sys.argv[1] == "--img":
        image_path = sys.argv[2]
        score, result_img = main(image_path)
        if result_img is None:
            result_img = cv2.imread(image_path)
        out = os.path.splitext(image_path)[0] + "_result.jpg"
        if result_img is not None:
            cv2.imwrite(out, result_img)
        print(f"score = {score}  (結果圖: {out})")
        sys.exit(0)

    if len(sys.argv) > 2:
        # 使用傳入的 uid 和 id 作為圖片路徑
        uid = sys.argv[1]
        img_id = sys.argv[2]
        # uid = "lull222"
        # img_id = "ch3-t1"
        image_path = os.path.join("kid", uid, f"{img_id}.jpg")
    else:
        return_score(-1)
    # image_path = r"ch2-t2.jpg"
    try:
        score, result_img = main(image_path)
        if result_img is None:
            result_img = cv2.imread(image_path)
        cv2.imwrite(os.path.join("kid", uid, f"{img_id}_result.jpg"), result_img)
        print(f"score = {score}")
        return_score(score)
    except Exception as e:
        print(f"[ERROR] ch2-t2 執行失敗: {e}")
        return_score(-1)
