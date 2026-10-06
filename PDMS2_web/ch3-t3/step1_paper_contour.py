import cv2
import numpy as np
import os
from pathlib import Path
from ultralytics import YOLO


_MODEL_CACHE = {}


def _resolve_weights_path(weights_path=None):
    if weights_path is not None:
        candidate = Path(weights_path)
        if candidate.exists():
            return candidate

    current_dir = Path(__file__).resolve().parent
    local_model = current_dir.parent / "models" / "crop_paper.pt"
    if local_model.exists():
        return local_model

    return None


def _load_model(weights_path=None):
    resolved = _resolve_weights_path(weights_path)
    if resolved is None:
        raise FileNotFoundError("找不到紙張輪廓模型權重 models/crop_paper.pt")

    key = str(resolved)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = YOLO(key)

    return _MODEL_CACHE[key], resolved


def detect_paper_contour(
    image_path, output_path=None, conf=0.5, device=None, weights_path=None
):
    """
    檢測紙張輪廓並用藍線畫出
    """
    # 讀取圖片
    image = cv2.imread(image_path)
    if image is None:
        print(f"無法讀取圖片: {image_path}")
        return None, None

    result_image = image.copy()

    try:
        model, resolved_path = _load_model(weights_path)
    except FileNotFoundError as e:
        print(str(e))
        return None, result_image

    results = model.predict(source=image, conf=conf, device=device, verbose=False)
    if not results:
        print("模型未返回偵測結果")
        return None, result_image

    result = results[0]
    if result.masks is None or len(result.masks.data) == 0:
        print("模型未檢測到 paper mask")
        return None, result_image

    if result.boxes is not None and len(result.boxes) > 0:
        mask_idx = int(np.argmax(result.boxes.conf.cpu().numpy()))
    else:
        mask_areas = result.masks.data.cpu().numpy().sum(axis=(1, 2))
        mask_idx = int(np.argmax(mask_areas))

    mask = result.masks.data[mask_idx].cpu().numpy()
    mask = (mask > 0.5).astype(np.uint8) * 255

    if mask.shape[:2] != image.shape[:2]:
        mask = cv2.resize(mask, (image.shape[1], image.shape[0]), cv2.INTER_NEAREST)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        print("paper mask 無法轉換為輪廓")
        return None, result_image

    paper_contour = max(contours, key=cv2.contourArea)
    cv2.drawContours(result_image, [paper_contour], -1, (255, 0, 0), 1)

    print(
        f"檢測到 paper mask 輪廓，包含 {len(paper_contour)} 個輪廓點，模型: {resolved_path}"
    )

    if output_path:
        cv2.imwrite(output_path, result_image)
        print(f"結果已保存到: {output_path}")

    return paper_contour, result_image


def main():
    """測試函數"""
    input_dir = "img"
    output_dir = "result"

    # 確保輸出目錄存在
    os.makedirs(output_dir, exist_ok=True)

    # 處理所有圖片
    for filename in os.listdir(input_dir):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, f"step1_{filename}")

            print(f"\n處理圖片: {filename}")
            contour, result = detect_paper_contour(input_path, output_path)

            if contour is not None:
                print(f"✓ 成功檢測紙張輪廓")
            else:
                print("✗ 未能檢測到紙張輪廓")


if __name__ == "__main__":
    main()
