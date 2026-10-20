"""
PDMS-2 項目 24：扣上鈕扣（跨機器後端計時 + 雙 YOLO 模型，單檔獨立執行，不依賴根目錄任何檔案）

    python main.py start    <uid>             按下「開始測驗」→ 約 2 秒後開始計時（寫入共享計時表）
    python main.py stop     <uid>             按下「拍照」→ 立即停止計時並算出總秒數（寫入共享計時表）
    python main.py evaluate <uid> <img_id>    讀共享計時表的秒數 + 照片 kid/<uid>/<img_id>.jpg → 評分
    python main.py <uid> <img_id>             同 evaluate（MacWeb /api/analysis/submit 的呼叫格式）

評分：布料內偵測到「扣上」的鈕扣 N ≥ 3 且 ≤ 75 秒 = 2 分；> 75 秒 = 1 分；N < 3 = 0 分。
推論：models/cloth.pt 找布料框（外擴 padding）→ models/button.pt（conf 0.25）以整張原圖抓 button / tape，
      只保留中心點在布料框內的框 → 同類別 NMS 去除重疊框 → 依扣上的鈕扣數量 + 共享計時表的秒數給分。
成果圖：kid/<uid>/<img_id>_result.jpg（MacWeb write_remote_results 會依檔名抓去當 result_img_path）。

結束碼（沿用 MacWeb 慣例：0/1/2 = 分數，其他 = 分析失敗 -1）：
    start / stop 成功 = 0；evaluate 成功 = 分數 0 / 1 / 2；任何錯誤 = 3（錯誤訊息印到 stderr）。
共享計時表：MySQL `ch5_button_timer`（主鍵 uid + task_id，Ch5-t2 / Ch5-t3 共用，第一次執行自動建立）。
DB 連線：環境變數 DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME 優先，否則讀 PDMS2_web/.env。
計時一律用 DB 伺服器時鐘（UNIX_TIMESTAMP(NOW(3))），start / stop 在哪台機器呼叫都不受本機時鐘誤差影響。
evaluate 時 DB 連不上、或沒有本輪計時紀錄（未 start / 已評分過）不中斷評分：完成給 1 分，判定寫明「無計時紀錄，無法確認是否在 75 秒內」。
run.py 可用子行程呼叫 start / stop / evaluate，或 import 後直接呼叫 run_start / run_stop / run_evaluate。
"""
from __future__ import annotations

import json
import os
import re
import sys
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

EXIT_ERROR = 3  # 不可用 1 / 2：MacWeb 會把結束碼 0/1/2 直接當分數

try:  # 套件 import 失敗也要以 EXIT_ERROR 結束，不能讓 Python 預設以 1 退出
    import cv2
    import numpy as np
    _IMPORT_ERROR: Optional[BaseException] = None
except BaseException as _e:  # noqa: BLE001
    cv2 = np = None
    _IMPORT_ERROR = _e

# ============================================================
# 1. 關卡設定
# ============================================================
TASK_ID = "Ch5-t3"                 # 與 run.py / MacWeb TASK_MAP 的 key 相同
ITEM = 24
TITLE = "PDMS-2 項目 24：扣上鈕扣"
TIME_LIMIT = 75.0                  # 秒數 <= TIME_LIMIT → 2 分；超過 → 1 分
DONE_LABEL = "3 顆鈕扣皆已扣上"     # 最終狀態達成時的判定文字

LEVEL_DIR = Path(__file__).resolve().parent
PROJECT_DIR = LEVEL_DIR.parent                                   # PDMS2_web
MODEL_DIRS = (LEVEL_DIR / "models", PROJECT_DIR / "models")      # 依序尋找模型檔
CLOTH_MODEL_NAME = "cloth.pt"      # 模型 A：布料
OBJECT_MODEL_NAME = "button.pt"    # 模型 B：button、tape
CLOTH_CONF = 0.5
OBJECT_CONF = 0.25
YOLO_IMGSZ = 640
YOLO_DEVICE: Optional[str] = None  # None = 自動（有 GPU 用 GPU）；可設 "cpu"、"0"

CLOTH_CLASS_NAMES: Optional[Tuple[str, ...]] = None   # None = 接受模型 A 的任何類別
BUTTON_CLASS_NAMES = ("button",)                      # 鈕扣扣進洞眼才會露出在布條上 → 計為「扣上」（計分依據）
TAPE_CLASS_NAMES = ("tape",)                          # tape 代表洞眼（僅繪圖 / 輸出參考，不計分）

NMS_IOU = 0.45                    # 同類別兩框 IoU ≥ 此值 → 視為同一物件，只留信心較高者
NMS_CONTAIN = 0.7                 # 小框有 ≥ 此比例面積落在大框內（巢狀重疊框）→ 也視為同一物件
CLOTH_PAD_RATIO = 0.05            # 布料框外擴比例，避免邊緣的鈕扣 / 膠帶被排除
CLOTH_FALLBACK_FULL_IMAGE = True  # 沒抓到布料時：True = 改用全圖繼續評分；False = 直接 0 分
NUM_BUTTONS = 3                   # 需扣上的鈕扣數量

START_DELAY = 2.0                 # 按下「開始測驗」後幾秒才開始計時（已寫進 start_at，duration 已扣除，不可重扣）
FALLBACK_ELAPSED: Optional[float] = None   # 沒有本輪計時紀錄時的秒數；None = 無法確認 ≦ 限時 → 完成給 1 分
NO_TIMER_REASON = f"無計時紀錄，無法確認是否在 {TIME_LIMIT:.0f} 秒內"
IMAGE_ROOTS = (PROJECT_DIR / "kid", Path.cwd() / "kid")   # 照片 kid/<uid>/<img_id>.<ext>
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")

ENV_PATHS = (PROJECT_DIR / ".env",)
TIMER_TABLE = "ch5_button_timer"


def score_task(button_count: int, tape_count: int, elapsed: Optional[float]) -> Tuple[int, bool, str]:
    """回傳 (分數, 最終狀態是否達成, 判定說明)。
    扣上數 < NUM_BUTTONS → 0 分；達成且 <= 限時 → 2 分；超過限時 → 1 分（以「超過限時」判 1 分，避免整數秒之間的空窗）。
    秒數先四捨五入到小數兩位，判定與顯示一致；elapsed 為 None（沒有本輪計時紀錄）→ 達成也只給 1 分。
    """
    if button_count < NUM_BUTTONS:
        return 0, False, f"未完成：扣上的鈕扣 {button_count}/{NUM_BUTTONS} 個"
    state = f"扣上的鈕扣 {button_count} 個 ≧ {NUM_BUTTONS}，{DONE_LABEL}"
    if elapsed is None:
        return 1, True, f"{state}；{NO_TIMER_REASON}"
    elapsed = round(elapsed, 2)
    if elapsed <= TIME_LIMIT:
        return 2, True, f"{state}；{elapsed:.2f} 秒 ≦ {TIME_LIMIT:.0f} 秒"
    return 1, True, f"{state}；{elapsed:.2f} 秒 > {TIME_LIMIT:.0f} 秒"


# ============================================================
# 2. 共享計時表（MySQL；start / stop / evaluate 可在不同機器、不同行程呼叫）
# ============================================================
_UID_RE = re.compile(r"^[A-Za-z0-9_-]{1,50}$")      # 只允許安全字元，避免路徑穿越；長度配合 DB varchar(50)
_IMG_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

CREATE_TIMER_SQL = f"""
CREATE TABLE IF NOT EXISTS `{TIMER_TABLE}` (
  `uid` varchar(50) NOT NULL,
  `task_id` varchar(20) NOT NULL,
  `pressed_at` double NOT NULL,
  `start_at` double NOT NULL,
  `stop_at` double DEFAULT NULL,
  `duration` double DEFAULT NULL,
  `status` varchar(16) NOT NULL,
  `score` int(11) DEFAULT NULL,
  `button_count` int(11) DEFAULT NULL,
  `tape_count` int(11) DEFAULT NULL,
  `cloth_detected` tinyint(1) DEFAULT NULL,
  `img_id` varchar(64) DEFAULT NULL,
  `result_img_path` varchar(255) DEFAULT NULL,
  `result_json` text DEFAULT NULL,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`uid`,`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
"""


def _check_id(value: str, pattern: re.Pattern, name: str) -> str:
    if not pattern.match(str(value)):
        raise ValueError(f"{name} 只能包含英數、底線、連字號：{value!r}")
    return value


def _read_env_files() -> Dict[str, str]:
    env: Dict[str, str] = {}
    for path in ENV_PATHS:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env.setdefault(key.strip(), value.strip().strip("'\""))
    return env


def _db_config() -> dict:
    file_env = _read_env_files()
    get = lambda k, d="": os.environ.get(k) or file_env.get(k) or d  # noqa: E731
    if not get("DB_USER"):
        raise RuntimeError(f"未設定資料庫連線（DB_USER），請設定環境變數或 {ENV_PATHS[0]}")
    return dict(host=get("DB_HOST", "127.0.0.1"), port=int(get("DB_PORT", "3306")), user=get("DB_USER"),
                password=get("DB_PASSWORD"), database=get("DB_NAME", "testPDMS"))


class TimerStore:
    """共享計時表的存取；時間戳記一律取 DB 伺服器時鐘，避免各機器時鐘不同步。"""

    def __init__(self):
        import pymysql  # 延遲匯入：import 失敗由主程式統一轉成 EXIT_ERROR
        self.conn = pymysql.connect(**_db_config(), charset="utf8mb4", autocommit=True, connect_timeout=10,
                                    cursorclass=pymysql.cursors.DictCursor)
        self._exec(CREATE_TIMER_SQL)

    def __enter__(self) -> "TimerStore":
        return self

    def __exit__(self, *exc) -> None:
        self.conn.close()

    def _exec(self, sql: str, params=None) -> int:
        with self.conn.cursor() as cur:
            return cur.execute(sql, params)

    def _get(self, uid: str) -> Optional[dict]:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT * FROM `{TIMER_TABLE}` WHERE uid=%s AND task_id=%s", (uid, TASK_ID))
            return cur.fetchone()

    def start(self, uid: str) -> dict:
        """按下「開始測驗」：計時從 START_DELAY 秒後開始。重複呼叫 = 重新開始（清掉上一輪的結果）。"""
        self._exec(
            f"""INSERT INTO `{TIMER_TABLE}` (uid, task_id, pressed_at, start_at, status)
                VALUES (%s, %s, UNIX_TIMESTAMP(NOW(3)), UNIX_TIMESTAMP(NOW(3)) + %s, 'started')
                ON DUPLICATE KEY UPDATE pressed_at=VALUES(pressed_at), start_at=VALUES(start_at),
                    stop_at=NULL, duration=NULL, status='started', score=NULL, button_count=NULL,
                    tape_count=NULL, cloth_detected=NULL, img_id=NULL, result_img_path=NULL, result_json=NULL""",
            (uid, TASK_ID, START_DELAY))
        return self._get(uid)

    def stop(self, uid: str) -> dict:
        """按下「拍照」：立即停止計時並算出總秒數。重複呼叫以第一次為準；延遲期間內按下 → 0 秒。"""
        if self._get(uid) is None:
            raise ValueError(f"找不到 uid={uid} 的 {TASK_ID} 計時紀錄，請先按「開始測驗」")
        self._exec(
            f"""UPDATE `{TIMER_TABLE}` SET stop_at=UNIX_TIMESTAMP(NOW(3)),
                    duration=ROUND(GREATEST(0, UNIX_TIMESTAMP(NOW(3)) - start_at), 2), status='stopped'
                WHERE uid=%s AND task_id=%s AND stop_at IS NULL""",
            (uid, TASK_ID))
        return self._get(uid)

    def duration(self, uid: str) -> Optional[float]:
        """evaluate 用：讀取 stop 時算好的秒數（start_at 已含 START_DELAY，此處不再重扣）。
        沒有紀錄、或紀錄已評分過（重測沒按「開始測驗」，不可沿用舊的 start_at）→ None，由呼叫端改用 fallback。
        前端漏呼叫 stop 時以此刻停止（秒數會含拍照 / 上傳時間）。"""
        row = self._get(uid)
        if row is None or row["status"] not in ("started", "stopped"):
            return None
        if row["duration"] is None:
            print("[警告] 尚未呼叫 stop，以評分當下停止計時", file=sys.stderr)
            row = self.stop(uid)
        return float(row["duration"])

    def save_result(self, uid: str, img_id: str, res: "EvalResult") -> None:
        result_img = (Path(res.result_image).relative_to(PROJECT_DIR).as_posix()
                      if res.result_image and Path(res.result_image).is_relative_to(PROJECT_DIR)
                      else res.result_image)
        n = self._exec(
            f"""UPDATE `{TIMER_TABLE}` SET status='evaluated', score=%s, button_count=%s, tape_count=%s,
                    cloth_detected=%s, img_id=%s, result_img_path=%s, result_json=%s
                WHERE uid=%s AND task_id=%s""",
            (res.score, res.button_count, res.tape_count, int(res.cloth_detected), img_id, result_img,
             json.dumps(res.to_dict(), ensure_ascii=False), uid, TASK_ID))
        if n == 0 and self._get(uid) is None:
            raise RuntimeError(f"寫入評分結果失敗：計時紀錄已不存在（uid={uid}）")


# ============================================================
# 3. 影像讀寫（cv2.imread / imwrite 在 Windows 讀不到中文路徑，改用 imdecode / imencode）
# ============================================================
def find_image(uid: str, img_id: str) -> Path:
    """依序在 PDMS2_web/kid/<uid>/ 與 CWD/kid/<uid>/ 找 <img_id>.<ext>（容許 ch5-t2 / Ch5-t2 大小寫差異）。"""
    names = dict.fromkeys((img_id, img_id.lower(), img_id[:1].upper() + img_id[1:]))
    for root in dict.fromkeys(IMAGE_ROOTS):
        for name in names:
            for ext in IMAGE_EXTS:
                p = root / uid / f"{name}{ext}"
                if p.is_file():
                    return p
    raise FileNotFoundError(f"找不到照片：kid/{uid}/{img_id}.*（已搜尋 {', '.join(str(r) for r in IMAGE_ROOTS)}）")


def find_model(name: str) -> Path:
    for d in MODEL_DIRS:
        if (d / name).is_file():
            return d / name
    raise FileNotFoundError(f"找不到 YOLO 模型 {name}（已搜尋 {', '.join(str(d) for d in MODEL_DIRS)}）")


def imread_unicode(path: str) -> Optional[np.ndarray]:
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None


def imwrite_unicode(path: str, img: np.ndarray) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    ok, buf = cv2.imencode(os.path.splitext(path)[1] or ".jpg", img)
    if not ok:
        raise RuntimeError(f"影像編碼失敗：{path}")
    buf.tofile(path)
    return path


# ============================================================
# 4. YOLO 兩階段推論
# ============================================================
@dataclass
class Detection:
    cls_name: str
    conf: float
    box: Tuple[float, float, float, float]   # x1, y1, x2, y2（原圖座標）


class YoloModel:
    """包裝 Ultralytics YOLO；模型檔不存在時直接報錯（不應在缺模型時默默給分）。"""

    def __init__(self, model_path: Path, conf: float):
        from ultralytics import YOLO  # 延遲匯入：start / stop 不需要載入 torch
        self.model = YOLO(str(model_path))
        self.conf = conf

    def detect(self, img: np.ndarray) -> List[Detection]:
        kwargs = dict(conf=self.conf, imgsz=YOLO_IMGSZ, verbose=False)
        if YOLO_DEVICE is not None:
            kwargs["device"] = YOLO_DEVICE
        r = self.model.predict(img, **kwargs)[0]
        if r.boxes is None or len(r.boxes) == 0:
            return []
        return [Detection(r.names[int(c)], float(cf), tuple(float(v) for v in b))
                for b, cf, c in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy(),
                                    r.boxes.cls.cpu().numpy().astype(int))]


def pad_box(img: np.ndarray, box) -> Tuple[int, int, int, int]:
    """布料框外擴 CLOTH_PAD_RATIO 並夾在影像範圍內，回傳 x1, y1, x2, y2。"""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    px, py = (x2 - x1) * CLOTH_PAD_RATIO, (y2 - y1) * CLOTH_PAD_RATIO
    return max(0, int(x1 - px)), max(0, int(y1 - py)), min(w, int(np.ceil(x2 + px))), min(h, int(np.ceil(y2 + py)))


def _overlap(a, b) -> Tuple[float, float]:
    """回傳 (IoU, 交集 / 較小框面積)。"""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return (inter / union if union > 0 else 0.0), (inter / min(area_a, area_b) if min(area_a, area_b) > 0 else 0.0)


def dedupe_detections(dets: List[Detection]) -> List[Detection]:
    """同類別 NMS：依信心由高到低保留，與已保留框重疊（IoU ≥ NMS_IOU 或巢狀 ≥ NMS_CONTAIN）者捨棄，
    避免低信心門檻下同一個鈕扣 / 膠帶被重複計數。"""
    def same_object(a: Detection, b: Detection) -> bool:
        iou, contain = _overlap(a.box, b.box)
        return a.cls_name == b.cls_name and (iou >= NMS_IOU or contain >= NMS_CONTAIN)

    kept: List[Detection] = []
    for d in sorted(dets, key=lambda d: d.conf, reverse=True):
        if not any(same_object(k, d) for k in kept):
            kept.append(d)
    return kept


@dataclass
class EvalResult:
    image_path: str
    task_id: str
    item: int
    elapsed_seconds: Optional[float]        # None = 沒有本輪計時紀錄
    time_limit: float
    score: int
    passed_state: bool                      # 最終狀態是否達成（扣上的鈕扣數足夠）
    button_count: int                       # N：布料內扣上的鈕扣數（計分依據）
    tape_count: int
    cloth_detected: bool
    cloth_box: Optional[List[int]]          # 布料範圍（含外擴），原圖座標
    message: str
    result_image: Optional[str] = None
    cloth: Optional[Detection] = field(default=None, repr=False)
    objects: List[Detection] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("cloth")
        d.pop("objects")
        return d


def evaluate_image(image_path: Path, elapsed: Optional[float]) -> EvalResult:
    """照片 → cloth.pt 找布料框 → button.pt 以整張原圖抓 button / tape（只留布料框內）→ NMS 去重 → 給分 → 成果圖。
    不裁切放大：button.pt 以整張照片訓練，裁切後物件尺度與訓練不符會抓不到。
    成果圖存在原圖旁：kid/<uid>/<img_id>.jpg → kid/<uid>/<img_id>_result.jpg"""
    path = os.path.abspath(image_path)
    img = imread_unicode(path)
    if img is None:
        raise ValueError(f"無法解碼圖片：{image_path}")
    cloth_model_path, object_model_path = find_model(CLOTH_MODEL_NAME), find_model(OBJECT_MODEL_NAME)

    # 模型 A：布料（取信心最高者）
    cands = [d for d in YoloModel(cloth_model_path, CLOTH_CONF).detect(img)
             if CLOTH_CLASS_NAMES is None or d.cls_name in CLOTH_CLASS_NAMES]
    cloth = max(cands, key=lambda d: d.conf) if cands else None
    region = pad_box(img, cloth.box) if cloth is not None else None
    usable = region is not None or CLOTH_FALLBACK_FULL_IMAGE

    # 模型 B：整張原圖偵測 button / tape，只保留中心點落在布料框內的框（排除背景、衣服上的扣子等雜訊）
    objects: List[Detection] = []
    if usable:
        wanted = BUTTON_CLASS_NAMES + TAPE_CLASS_NAMES
        objects = [d for d in YoloModel(object_model_path, OBJECT_CONF).detect(img) if d.cls_name in wanted]
        if region is not None:
            objects = [d for d in objects
                       if region[0] <= (d.box[0] + d.box[2]) / 2 <= region[2]
                       and region[1] <= (d.box[1] + d.box[3]) / 2 <= region[3]]
        objects = dedupe_detections(objects)
    n_button = sum(d.cls_name in BUTTON_CLASS_NAMES for d in objects)
    n_tape = sum(d.cls_name in TAPE_CLASS_NAMES for d in objects)

    if not usable:
        score, passed, msg = 0, False, "未偵測到布料，無法評分"
    else:
        score, passed, msg = score_task(n_button, n_tape, elapsed)
        if cloth is None:
            msg += "（未偵測到布料，改用全圖）"

    res = EvalResult(path, TASK_ID, ITEM, elapsed, TIME_LIMIT, score, passed, n_button, n_tape,
                     cloth is not None, list(region) if region else None, msg, None, cloth, objects)
    out_path = str(Path(path).with_name(Path(path).stem + "_result.jpg"))
    try:  # 成果圖存檔失敗不影響分數
        res.result_image = imwrite_unicode(out_path, render_result_image(res, img))
    except Exception as e:
        print(f"[警告] 成果圖儲存失敗：{e}", file=sys.stderr)
    return res


# ============================================================
# 5. 成果圖
# ============================================================
COLOR_CLOTH = (0, 220, 0)
COLOR_BUTTON = (0, 165, 255)
COLOR_TAPE = (255, 255, 0)
SCORE_COLOR = {2: (0, 220, 0), 1: (0, 165, 255), 0: (0, 0, 255)}

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msjh.ttc",                                # Windows 微軟正黑體
    "C:/Windows/Fonts/mingliu.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",   # Linux：sudo apt install fonts-noto-cjk
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]


def draw_texts(img: np.ndarray, items) -> None:
    """中文字繪製（cv2.putText 不支援中文，改用 Pillow）。items：[(文字, (x, y) 左上角, BGR, 字級), ...]"""
    font_path = next((p for p in FONT_CANDIDATES if os.path.isfile(p)), None)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        font_path = None
    if font_path is None:  # 無 Pillow 或中文字型：退回 cv2（中文會顯示為 ?）
        for text, (x, y), color, size in items:
            cv2.putText(img, text, (x, y + size), cv2.FONT_HERSHEY_SIMPLEX, size / 32, color, 1, cv2.LINE_AA)
        return
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    fonts = {}
    for text, (x, y), (b, g, r), size in items:
        if size not in fonts:
            fonts[size] = ImageFont.truetype(font_path, size)
        draw.text((x, y), text, font=fonts[size], fill=(r, g, b), stroke_width=2, stroke_fill=(0, 0, 0))
    img[:] = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)


def _draw_box(img: np.ndarray, box, color, label: str, thickness: int = 2) -> None:
    x1, y1, x2, y2 = (int(v) for v in box)
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
    org = (x1, max(14, y1 - 6))
    cv2.putText(img, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, label, org, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def fmt_elapsed(seconds: Optional[float]) -> str:
    return "無計時紀錄" if seconds is None else f"{seconds:.2f} 秒"


def render_result_image(res: EvalResult, img: np.ndarray) -> np.ndarray:
    """成果圖：上方資訊面板（項目、秒數、得分、判定、偵測數量）+ 下方原圖（布料範圍 + 物件框 + 圖例）。"""
    vis = img.copy()
    if res.cloth_box is not None:
        _draw_box(vis, res.cloth_box, COLOR_CLOTH, f"cloth {res.cloth.conf:.2f}", 3)
    for d in res.objects:
        color = COLOR_BUTTON if d.cls_name in BUTTON_CLASS_NAMES else COLOR_TAPE
        _draw_box(vis, d.box, color, f"{d.cls_name} {d.conf:.2f}")
    h, w = vis.shape[:2]
    for k, (name, color) in enumerate((("cloth", COLOR_CLOTH), ("button", COLOR_BUTTON), ("tape", COLOR_TAPE))):
        y = h - 12 - 22 * k
        cv2.rectangle(vis, (w - 130, y - 12), (w - 114, y + 2), color, -1)
        cv2.putText(vis, name, (w - 106, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(vis, name, (w - 106, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    cloth_text = f"布料：已偵測（{res.cloth.conf:.2f}）" if res.cloth is not None else \
        ("布料：未偵測到，改用全圖" if CLOTH_FALLBACK_FULL_IMAGE else "布料：未偵測到")
    fs = max(18, w // 40)
    lines = [
        (f"{TITLE}　｜　{os.path.basename(res.image_path)}", (255, 255, 255), fs),
        (f"總秒數：{fmt_elapsed(res.elapsed_seconds)}（限時 {TIME_LIMIT:.0f} 秒）", (255, 255, 255), fs),
        (f"得分：{res.score} 分", SCORE_COLOR[res.score], int(fs * 1.6)),
        (f"判定：{res.message}", (255, 230, 150), fs),
        (f"{cloth_text}　｜　扣上鈕扣 {res.button_count} 個、膠帶 {res.tape_count} 個", (200, 200, 200), fs),
    ]
    pad = fs // 2
    header = np.full((pad * 2 + sum(int(sz * 1.35) for *_, sz in lines), w, 3), 40, np.uint8)
    items, y = [], pad
    for text, color, sz in lines:
        items.append((text, (pad, y), color, sz))
        y += int(sz * 1.35)
    draw_texts(header, items)
    return np.vstack([header, vis])  # 資訊面板放在照片上方，不遮住偵測框


# ============================================================
# 6. 命令列進入點
# ============================================================
USAGE = ("使用方式: python main.py start <uid> | stop <uid> | evaluate <uid> <img_id>"
         " | <uid> <img_id>（同 evaluate）")
ACTIONS = {"start": 1, "stop": 1, "evaluate": 2}   # 動作 → 參數個數


def parse_args(argv: List[str]) -> Tuple[str, str, Optional[str]]:
    if argv and argv[0].lower() in ACTIONS:
        action, rest = argv[0].lower(), argv[1:]
    elif len(argv) == 2:  # MacWeb run_remote_analysis：main.py <uid> <img_id>
        action, rest = "evaluate", argv
    else:
        raise ValueError(f"未知的動作或參數錯誤，{USAGE}")
    if len(rest) != ACTIONS[action]:
        raise ValueError(f"缺少或多餘參數，{USAGE}")
    uid = _check_id(rest[0], _UID_RE, "uid")
    img_id = _check_id(rest[1], _IMG_ID_RE, "img_id") if action == "evaluate" else None
    return action, uid, img_id


def _timer_json(row: dict) -> str:
    keys = ("uid", "task_id", "pressed_at", "start_at", "stop_at", "duration", "status")
    return json.dumps({k: row.get(k) for k in keys}, ensure_ascii=False)


def open_timer_for_evaluate(uid: str) -> Tuple[Optional[TimerStore], Optional[float]]:
    """evaluate 用：回傳 (計時表連線, 秒數)。DB 連不上或沒有本輪計時紀錄都不中斷評分，
    改回傳 (None, FALLBACK_ELAPSED)，也不把結果寫回計時表（避免新分數和舊秒數混在同一筆）。"""
    store = None
    try:
        store = TimerStore()
        elapsed = store.duration(uid)
        if elapsed is not None:
            return store, elapsed
        print(f"[警告] uid={uid} 沒有本輪的 {TASK_ID} 計時紀錄（未按「開始測驗」或已評分過），"
              f"秒數改用 fallback：{FALLBACK_ELAPSED}", file=sys.stderr)
    except Exception as e:
        print(f"[警告] 讀取計時紀錄失敗，秒數改用 fallback：{FALLBACK_ELAPSED}（{type(e).__name__}: {e}）",
              file=sys.stderr)
    if store is not None:
        store.conn.close()
    return None, FALLBACK_ELAPSED


def run_start(uid: str) -> dict:
    """「開始測驗」按鈕：後端以 DB 伺服器時鐘記下開始時間，不收前端傳來的任何時間。"""
    with TimerStore() as store:
        row = store.start(uid)
    print(f"[開始] uid={uid}，{START_DELAY:.0f} 秒後開始計時")
    print(_timer_json(row))
    return row


def run_stop(uid: str) -> dict:
    """「拍照 / 結束」按鈕：後端以 DB 伺服器時鐘記下結束時間並算出時間差（duration）。"""
    with TimerStore() as store:
        row = store.stop(uid)
    print(f"[停止] uid={uid}，總秒數 {row['duration']:.2f}")
    print(_timer_json(row))
    return row


def run_evaluate(uid: str, img_id: str) -> EvalResult:
    """讀計時表的秒數 + 照片評分；沒有計時紀錄時不中斷（完成給 1 分，判定寫明 NO_TIMER_REASON）。"""
    image_path = find_image(uid, img_id)   # 先確認照片存在，再動 DB（避免無照片時誤停計時）
    store, elapsed = open_timer_for_evaluate(uid)
    try:
        res = evaluate_image(image_path, elapsed)
        if res.score not in (0, 1, 2):
            raise RuntimeError(f"分數異常：{res.score}")
        if store is not None:
            try:  # 寫入後 status='evaluated'，下次重測沒按「開始測驗」就不會沿用這筆 start_at
                store.save_result(uid, img_id, res)
            except Exception as e:
                print(f"[警告] 評分結果寫入計時表失敗（分數照常回傳）：{e}", file=sys.stderr)
    finally:
        if store is not None:
            store.conn.close()
    print(f"[結果] 項目 {ITEM}｜{res.message}｜總秒數 {fmt_elapsed(res.elapsed_seconds)}｜score = {res.score}")
    print(f"成果圖已儲存: {res.result_image}")
    print(json.dumps(res.to_dict(), ensure_ascii=False))
    return res


def main(argv: List[str]) -> int:
    """回傳結束碼：start / stop = 0；evaluate = 分數 0 / 1 / 2。任何錯誤直接丟例外，由進入點轉成 EXIT_ERROR。"""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR
    action, uid, img_id = parse_args(argv)
    if action == "start":
        run_start(uid)
        return 0
    if action == "stop":
        run_stop(uid)
        return 0
    return run_evaluate(uid, img_id).score


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):   # 主控台不是 UTF-8 時，印中文不可讓程式崩潰
        try:
            _stream.reconfigure(errors="replace")
        except Exception:
            pass
    try:
        exit_code = main(sys.argv[1:])
    except BaseException as e:  # noqa: BLE001  任何失敗（含 KeyboardInterrupt）都不可落到結束碼 1 / 2
        print(f"[錯誤] {TASK_ID} 執行失敗：{type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        exit_code = EXIT_ERROR
    sys.exit(exit_code)
