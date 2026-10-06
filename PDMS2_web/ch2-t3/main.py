# ch2-t3：YOLO+SAM2 找紙張 -> 該範圍內 CV 圈出圖形 -> 4類分類(cross) -> CrossScorer 評分
import os
import sys
import glob
import cv2
import numpy as np
from pathlib import Path
from cross_detect import CrossScorer

BASE_DIR = Path(__file__).resolve().parent
target_dir = os.path.join(BASE_DIR.parent, "ch2-t3")
ENV_PATH = BASE_DIR.parent / ".env"
# 共用模組：prepare(分類前) + classify(分類)
sys.path.insert(0, str(BASE_DIR.parent))
from prepare import Preparer
from classify import Classifier

def _read_env_float(key):
    if not ENV_PATH.exists():
        raise FileNotFoundError(f"找不到 .env 檔案")
    try:
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            current_key, value = raw_line.split("=", 1)
            if current_key.strip() == key:
                parsed = float(value.strip())
                if parsed <= 0:
                    raise ValueError(f"{key} 必須大於 0")
                return parsed
    except Exception as e:
        raise ValueError(f"解析 .env 時發生錯誤: {e}")
    raise ValueError(f"在 .env 中找不到 {key}")

def return_score(score):
    sys.exit(int(score))


def get_pixel_per_cm_from_a4(
    image_path,
    real_width_cm=29.7,
    show_debug=False,
    save_cropped=True,
    output_folder=os.path.join(target_dir, "cropped_a4"),
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
    SCORE = -1

    TARGET = "cross"  # ch2-t3 目標形狀
    # ==參數==#

    # 得出 px->cm
    try:
        pixel_per_cm, _, cropped_path = get_pixel_per_cm_from_a4(
            img_path,
            show_debug=False,  # 關掉視覺化避免卡住
            save_cropped=True,
            output_folder=os.path.join(target_dir, "cropped_a4"),
        )
        print(f"{img_path} 動態計算比例 pixel_per_cm = {pixel_per_cm}")
    except ValueError as e:
        print(f"⚠️ 動態計算比例失敗 ({e})，準備改用 .env 備用比例")
        try:
            pixel_per_cm = _read_env_float("PDMS2_PX2CM")
        except Exception as env_e:
            img = cv2.imread(img_path)
            print(f"❌ 嚴重錯誤: 動態計算與 .env 備案皆失敗 -> {env_e}")
            return -1, img
        cropped_path = img_path  # 若裁切失敗，直接使用原圖路徑
        print(f"{img_path} 備用比例 pixel_per_cm = {pixel_per_cm}")

    
    # 參數要改
    # 注意：CrossScorer 要的是「每像素幾公分」，這裡算出來的是「每公分幾像素」，必須取倒數
    cs = CrossScorer(
        cm_per_pixel=1.0 / pixel_per_cm,
        angle_min=70.0,
        angle_max=110.0,
        max_spread_cm=0.6,
    )
    
    # prepare：找紙張 + CV 圈選 + binary
    print(f"\n=== 處理 {img_path} ===\n")
    print("\n==prepare 前處理==")
    prep = Preparer()
    stem = os.path.splitext(os.path.basename(img_path))[0]
    r = prep.prepare(img_path, os.path.join(target_dir, "ready"), stem)
    if not r["ok"]:
        print(f"未圈到圖形（{r['reason']}）")
        return SCORE, r.get("vis")

    # classify：4 類分類
    print("\n==classify 分類==")
    clf = Classifier()
    label, conf = clf.classify(r["binary_bgr"])
    print(f"{img_path} → {label} ({conf*100:.2f}%)")

    # 十字 -> CrossScorer 評分（評分邏輯不變，吃 binary crop）
    if label == TARGET:
        results, result_img, _, _, _ = cs.score_image(r["binary_path"])
        return results["score"], result_img

    # 非目標形狀 -> 0 分
    img = cv2.imread(r["color_path"])
    cv2.putText(img, "Other !", (30, 50), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (0, 0, 255), 2)
    print(f"{img_path} is {label}!")
    return 0, img


def test_folder(folder=None, show=False):
    """單張／整個資料夾的離線測試模式，不呼叫 sys.exit，方便直接看分數與結果圖。

    用法:
        python main.py --test                      # 測 0821fix 資料夾
        python main.py --test 0821fix              # 指定資料夾
        python main.py --test 0821fix/xxx.jpg      # 指定單張圖片
        python main.py --test 0821fix --show       # 順便開視窗顯示結果圖
    """
    if folder is None:
        folder = os.path.join(BASE_DIR, "0821fix")

    if os.path.isfile(folder):
        images = [folder]
        out_dir = os.path.join(os.path.dirname(folder), "test_result")
    else:
        exts = ("jpg", "jpeg", "png", "bmp")
        images = []
        for ext in exts:
            images.extend(glob.glob(os.path.join(folder, f"*.{ext}")))
            images.extend(glob.glob(os.path.join(folder, f"*.{ext.upper()}")))
        # 去重 + 排除先前產生的 _result 圖
        images = sorted(
            {p for p in images if "_result" not in os.path.basename(p)}
        )
        out_dir = os.path.join(folder, "test_result")

    os.makedirs(out_dir, exist_ok=True)
    print(f"[TEST] 來源: {folder}")
    print(f"[TEST] 共 {len(images)} 張待測圖片")

    summary = []
    for image_path in images:
        name = os.path.basename(image_path)
        print("")
        print("=" * 60)
        print(f"[TEST] 處理: {name}")
        print("=" * 60)
        try:
            score, result_img = main(image_path)
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"[TEST][ERROR] {name}: {e}")
            summary.append((name, "EXCEPTION", str(e)))
            continue

        if result_img is None:
            result_img = cv2.imread(image_path)

        save_path = os.path.join(out_dir, f"{os.path.splitext(name)[0]}_result.jpg")
        if result_img is not None:
            cv2.imwrite(save_path, result_img)
            print(f"[TEST] 結果圖已存: {save_path}")
            if show:
                cv2.imshow(name, result_img)
                cv2.waitKey(0)
                cv2.destroyAllWindows()

        print(f"[TEST] score = {score}")
        summary.append((name, score, save_path))

    print("")
    print("#" * 60)
    print("[TEST] 總結")
    print("#" * 60)
    for name, score, extra in summary:
        print(f"  {name:<45} score={score}")
    return summary


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

    # ===== 測試模式: python main.py --test [資料夾或圖片路徑] [--show] =====
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "-t"):
        args = sys.argv[2:]
        show = "--show" in args
        args = [a for a in args if not a.startswith("-")]
        target = args[0] if args else None
        test_folder(target, show=show)
        sys.exit(0)
    # ===== 正式模式 (由後端以 uid / id 呼叫) =====
    if len(sys.argv) > 2:
        # 使用傳入的 uid 和 id 作為圖片路徑
        uid = sys.argv[1]
        img_id = sys.argv[2]
        # image_path = rf"kid\{uid}\{img_id}.jpg"
        image_path = os.path.join('kid',uid, f"{img_id}.jpg")
    else:
        return_score(-1)
    # img_path = r'S__75628564.jpg'
    # image_path = r'ch2-t3.jpg'
    try:
        score, result_img = main(image_path)

        result_path = os.path.join('kid',uid, f"{img_id}_result.jpg")
        if result_img is None:
            result_img = cv2.imread(image_path)
        cv2.imwrite(result_path, result_img)
        print(score)
        return_score(score)
    except Exception as e:
        print(f"[ERROR] ch2-t3 執行失敗: {e}")
        return_score(-1)
