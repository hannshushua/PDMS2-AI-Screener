"""
ch1-t1 校正：桌上放「完整的繩子 + 6 顆積木 (放旁邊、不要穿、不要壓到繩子)」，
自動量出 繩子長度 / 面積 / 繩寬、積木邊長、積木數、長度抖動，存成 plan_ch1_t1.json (放在 main.py 旁邊)。
main.py 評分時會讀這個檔。

鏡頭、解析度、裁切都跟網頁拍照一樣 (讀 PDMS2_web/.env 的 PDMS2_TOP_CAMERA_INDEX / PDMS2_ROI_*，1280x720)，
所以量到的像素大小跟小朋友的照片一致。鏡頭高度、ROI、繩子換了都要重跑。

用法 (在 PDMS2_web 底下或任何地方都可以):
    python ch1-t1/plan_ch1_t1.py                 # 開鏡頭，SPACE / b 校正，q 離開
    python ch1-t1/plan_ch1_t1.py --cam 1         # 指定鏡頭
    python ch1-t1/plan_ch1_t1.py --image a.jpg   # 用已經拍好的照片校正 (要是網頁裁切後的照片)
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))

import cv2
import numpy as np

import main as ch1   # 跟評分用同一套偵測 / 量測 (會順便載入模型)

PLAN_PATH = ch1.PLAN_PATH
ENV_PATH = ROOT / ".env"
CAMERA_W, CAMERA_H = 1280, 720               # 跟 run.py LIVE_CAMERA_WIDTH / HEIGHT 一樣
FALLBACK_ROI = (164, 95, 1166, 909)          # 跟 run.py crop_center 沒設 ROI 時一樣


def read_env(path=ENV_PATH):
    env = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        print(f"[WARN] 找不到 {path}，鏡頭用 0、ROI 用預設值")
    return env


def env_int(env, key, default):
    try:
        return int(env.get(key, default))
    except ValueError:
        return default


def parse_args(env):
    p = argparse.ArgumentParser()
    p.add_argument("--cam", type=int, default=env_int(env, "PDMS2_TOP_CAMERA_INDEX", 0), help="鏡頭編號 (預設讀 .env)")
    p.add_argument("--image", nargs="+", help="用照片校正 (網頁裁切後的照片)，可給多張")
    p.add_argument("--blocks", type=int, default=6, help="桌上應該有幾顆積木")
    p.add_argument("--frames", type=int, default=3, help="鏡頭模式連拍幾張取中位數")
    p.add_argument("--out", default=str(PLAN_PATH), help="輸出 json 路徑")
    return p.parse_args()


def get_roi(env):
    roi = tuple(env_int(env, f"PDMS2_ROI_{k}", 0) for k in ("X", "Y", "W", "H"))
    return roi if roi[2] > 0 and roi[3] > 0 else None


def crop(frame, roi):
    """跟 run.py crop_center 一樣的裁切"""
    h, w = frame.shape[:2]
    if roi:
        x, y, rw, rh = roi
        x1, y1, x2, y2 = max(0, x), max(0, y), min(w, x + rw), min(h, y + rh)
        if x2 > x1 and y2 > y1:
            return frame[y1:y2, x1:x2]
    x, y, rw, rh = FALLBACK_ROI
    return frame[y:y + rh, x:x + rw]


def open_camera(idx):
    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
    cap = cv2.VideoCapture(idx, backend)
    if not cap.isOpened():
        cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        sys.exit(f"[ERROR] 無法開啟攝影機 {idx}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_H)
    return cap


# ================== 校正 ==================

def measure(img):
    """量一張: 回傳 dict 和結果圖"""
    _, masks, rope = ch1.analyze(img)
    m = ch1.rope_measure(rope)
    on_rope, infos = ch1.judge_strung(masks, rope, m["skel"], m["width"], chain=False)
    vis = ch1.draw_block_markers(img, masks, on_rope, infos, m["skel"])
    return {"n_blocks": len(masks), "side": ch1.block_side(masks), "length": m["length"],
            "area": m["area"], "width": m["width"], "segs": m["segs"], "on_rope": int(sum(on_rope))}, vis


def calibrate(images, args, source):
    """多張照片 -> plan dict；失敗回傳 (None, 結果圖)"""
    rows, vis = [], None
    for i, img in enumerate(images):
        r, vis = measure(img)
        print(f"  [{i + 1}/{len(images)}] 積木={r['n_blocks']}  邊長={r['side']:.1f}  繩長={r['length']:.0f}  "
              f"面積={r['area']}  段數={r['segs']}  繩寬={r['width']:.1f}")
        if r["on_rope"]:
            print(f"  [WARN] 有 {r['on_rope']} 顆積木壓在繩子上 / 靠太近 (結果圖上綠色的)，繩長會被低估，請把積木移開一點")
        if r["segs"] > 1:
            print(f"  [WARN] 繩子斷成 {r['segs']} 段，可能有東西擋住或繩子沒偵測完整")
        rows.append(r)

    lengths = [r["length"] for r in rows if r["length"]]
    sides = [r["side"] for r in rows if r["side"]]
    if not lengths:
        print("[ERROR] 沒偵測到繩子，校正失敗")
        return None, vis
    if not sides:
        print("[ERROR] 沒偵測到積木，校正失敗 (請放完整繩子 + 積木)")
        return None, vis

    n_blocks = int(np.median([r["n_blocks"] for r in rows]))
    if n_blocks != args.blocks:
        print(f"[WARN] 偵測到 {n_blocks} 顆積木，預期 {args.blocks} 顆 (--blocks)")
    L0 = float(np.median(lengths))
    A0 = float(np.median([r["area"] for r in rows if r["length"]]))
    side = float(np.median(sides))
    width = A0 / L0
    h, w = images[0].shape[:2]
    plan = {
        "task": "ch1-t1",
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "image_size": [w, h],                   # main.py 會檢查照片大小一不一樣
        "frames": len(images),
        "rope_len": round(L0, 1),               # 繩子原始長度 (中心線像素)
        "rope_area": round(A0, 1),              # 繩子原始面積 (像素)
        "rope_width": round(width, 2),          # 繩寬 = 面積 / 長度
        "len_spread": round(float(max(lengths) - min(lengths)), 1),   # 幾張之間長度抖多少
        "block_side": round(side, 1),           # 積木邊長 (像素)
        "n_blocks": n_blocks,
        "per_block_len": round(side + width, 1),        # 每顆積木擋掉的繩長 (估計 = 邊長 + 繩寬)
        "per_block_area": round(side * width, 1),
        "thresholds": {                         # 參考用，main.py 每顆積木會依角度重算
            "strung_min_px": round(side * 0.6 + width, 1),      # 正放: 半弦長 邊長/2 + 繩寬 + 0.1 邊長
            "strung_max_px": round(side * 0.81 + width, 1),     # 斜放: 半弦長 邊長x0.71 + 繩寬 + 0.1 邊長
            "touch_px": round(2 * width + 2, 1),                # 貼在一起
        },
    }
    return plan, vis


def save_plan(plan, out, vis, img):
    out = Path(out)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    cv2.imwrite(str(out.with_suffix(".jpg")), img)
    cv2.imwrite(str(out.with_name(out.stem + "_result.jpg")), vis)
    print(f"[PLAN] 已存: {out}")
    print(f"       繩子 長度 L0={plan['rope_len']:.0f}px (幾張差 {plan['len_spread'] / plan['rope_len'] * 100:.1f}%)  "
          f"面積 A0={plan['rope_area']:.0f}  繩寬={plan['rope_width']:.1f}px")
    print(f"       積木 {plan['n_blocks']} 顆  邊長={plan['block_side']:.1f}px  每顆擋掉 l≈{plan['per_block_len']:.0f}px")
    t = plan["thresholds"]
    print(f"       穿上門檻 正放 {t['strung_min_px']:.0f}px ~ 斜放 {t['strung_max_px']:.0f}px  貼在一起 <= {t['touch_px']:.0f}px")


def put_status(img, lines):
    for i, txt in enumerate(lines):
        y = 30 + i * 30
        cv2.putText(img, txt, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
        cv2.putText(img, txt, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


def run_images(args):
    images = []
    for p in args.image:
        img = cv2.imread(p)
        if img is None:
            sys.exit(f"[ERROR] 讀不到圖片: {p}")
        images.append(img)
    sizes = {im.shape[:2] for im in images}
    if len(sizes) > 1:
        sys.exit(f"[ERROR] 照片大小不一樣: {sizes}")
    print(f"[PLAN] 用 {len(images)} 張照片校正")
    plan, vis = calibrate(images, args, source=[str(Path(p).resolve()) for p in args.image])
    if plan:
        save_plan(plan, args.out, vis, images[0])


def run_camera(args, env):
    roi = get_roi(env)
    cap = open_camera(args.cam)
    print(f"[PLAN] 鏡頭 {args.cam}  解析度 {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}  "
          f"ROI={roi or ('預設', FALLBACK_ROI)}")
    print(f"[PLAN] 桌上放「完整的繩子 + {args.blocks} 顆積木 (放旁邊、不要穿、不要壓到繩子)」，按 SPACE 或 b 校正，q 離開")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("[ERROR] 讀取影像失敗")
            break
        shot = crop(frame, roi)
        disp = shot.copy()
        put_status(disp, [f"rope + {args.blocks} blocks (not strung)", "[SPACE/b] calibrate  [q] quit"])
        cv2.imshow("plan_ch1_t1", disp)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key in (ord(" "), ord("b")):
            images = [shot.copy()]
            for _ in range(args.frames - 1):
                ok, frame = cap.read()
                if ok:
                    images.append(crop(frame, roi).copy())
            plan, vis = calibrate(images, args, source=f"camera {args.cam}")
            if plan:
                plan["camera_index"] = args.cam
                plan["roi"] = list(roi) if roi else None
                save_plan(plan, args.out, vis, images[0])
            if vis is not None:
                cv2.imshow("plan_ch1_t1 result", vis)
    cap.release()
    cv2.destroyAllWindows()


def main():
    env = read_env()
    args = parse_args(env)
    if args.image:
        run_images(args)
    else:
        run_camera(args, env)


if __name__ == "__main__":
    main()
