import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO


_MODEL_CACHE = {}


def resolve_weights_path(weights_path=None):
    if weights_path is not None:
        candidate = Path(weights_path)
        if candidate.exists():
            return candidate

    current_dir = Path(__file__).resolve().parent
    candidates = [
        current_dir.parent / "models" / "crop_paper.pt",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _load_model(weights_path=None):
    resolved = resolve_weights_path(weights_path)
    if resolved is None:
        raise FileNotFoundError("找不到紙張輪廓模型權重 models/crop_paper.pt")

    key = str(resolved)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = YOLO(key)

    return _MODEL_CACHE[key], resolved


def detect_paper_contour_by_model(image, conf=0.5, device=None, weights_path=None):
    if image is None:
        return None, None, 0, None
    model, resolved_path = _load_model(weights_path)
    # ultralytics YOLO / segmentation model APIs may vary between versions.
    # 對 predict/detect 的呼叫做多種回退策略，並在失敗時記錄詳細除錯資訊。
    import traceback
    results = None
    call_attempts = []
    try:
        # 1) 優先使用 predict()（多數 ultralytics 版本支援）
        if hasattr(model, "predict"):
            call_attempts.append("predict(source=image, conf=conf, device=device)")
            results = model.predict(source=image, conf=conf, device=device, verbose=False)

        # 2) 嘗試直接呼叫 model(image)
        if results is None and callable(model):
            call_attempts.append("callable(model)(image)")
            try:
                results = model(image)
            except TypeError:
                # 有些 model() 需要參數形式不同，改用 keyword
                results = model(source=image)

        # 3) 嘗試 detect()（某些舊 API）
        if results is None and hasattr(model, "detect"):
            call_attempts.append("detect(image)")
            results = model.detect(image, conf=conf)

        # 最後仍失敗時，拋出錯誤並記錄
        if results is None:
            raise RuntimeError(f"無法呼叫模型進行推論；嘗試的呼叫: {call_attempts}")

    except Exception as exc:
        # 記錄詳細的 model 資訊與 traceback 到 /tmp 以便診斷
        try:
            from datetime import datetime as _dt
            with open("/tmp/paper_contour_model_debug.log", "a") as fh:
                fh.write("=== %s ===\n" % (_dt.now().isoformat()))
                fh.write(f"Model type: {type(model)}\n")
                try:
                    fh.write(f"Model repr: {repr(model)}\n")
                except Exception:
                    pass
                try:
                    fh.write(f"Has predict: {hasattr(model, 'predict')}, has detect: {hasattr(model, 'detect')}, callable: {callable(model)}\n")
                except Exception:
                    pass
                fh.write("Attempted calls: %s\n" % (call_attempts,))
                fh.write("Exception:\n")
                fh.write(traceback.format_exc())
                fh.write("\n\n")
        except Exception:
            pass

        # 嘗試使用 OpenCV-based 的回退偵測（不依賴模型），找尋最大外輪廓作為 paper
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            def _find_mask_and_contour(bin_img):
                cnts, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not cnts:
                    return None, 0, None
                c = max(cnts, key=cv2.contourArea)
                mask = np.zeros(gray.shape, dtype=np.uint8)
                cv2.drawContours(mask, [c], -1, 255, -1)
                return c, int(np.count_nonzero(mask)), mask

            c1, area1, mask1 = _find_mask_and_contour(th)
            c2, area2, mask2 = _find_mask_and_contour(cv2.bitwise_not(th))

            if area1 >= area2 and area1 > 0:
                try:
                    with open("/tmp/paper_contour_model_debug.log", "a") as fh:
                        fh.write("Used OpenCV fallback (binary). area=%d\n" % area1)
                except Exception:
                    pass
                return c1, mask1, area1, None
            elif area2 > 0:
                try:
                    with open("/tmp/paper_contour_model_debug.log", "a") as fh:
                        fh.write("Used OpenCV fallback (inverted). area=%d\n" % area2)
                except Exception:
                    pass
                return c2, mask2, area2, None
        except Exception:
            try:
                with open("/tmp/paper_contour_model_debug.log", "a") as fh:
                    fh.write("OpenCV fallback failed:\n")
                    fh.write(traceback.format_exc())
            except Exception:
                pass

        # 回退也失敗，向上拋出
        raise RuntimeError(f"模型推論失敗: {exc} (model type={type(model)})")

    if not results:
        return None, None, 0, resolved_path

    result = results[0]
    if result.masks is None or len(result.masks.data) == 0:
        return None, None, 0, resolved_path

    if result.boxes is not None and len(result.boxes) > 0:
        mask_idx = int(np.argmax(result.boxes.conf.cpu().numpy()))
    else:
        mask_areas = result.masks.data.cpu().numpy().sum(axis=(1, 2))
        mask_idx = int(np.argmax(mask_areas))

    mask = result.masks.data[mask_idx].cpu().numpy()
    mask = (mask > 0.5).astype(np.uint8) * 255

    if mask.shape[:2] != image.shape[:2]:
        mask = cv2.resize(mask, (image.shape[1], image.shape[0]), cv2.INTER_NEAREST)

    # 直接用 mask 白色像素數計算面積，避免輪廓近似造成誤差
    mask_area = int(np.count_nonzero(mask))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, mask, mask_area, resolved_path

    paper_contour = max(contours, key=cv2.contourArea)
    return paper_contour, mask, mask_area, resolved_path
