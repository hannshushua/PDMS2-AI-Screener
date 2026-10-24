"""
track_11.py - ch1-t1 (串積木) 影片追蹤版 (作法 2)

從整段影片判斷每顆積木有沒有「真的被穿過去」，而不是只看最後一張的位置。

每顆積木的判定流程:
    在桌上 → 被手拿起 (手碰到積木，而且積木有移動或被手遮住)
          → 拿著的時候繩頭(金屬頭)貼在積木旁邊累積夠久 → 算穿進去

    - 從沒被手拿起過的積木 (例如本來就壓在繩上、底座積木) 不會被算
    - 拿起來但繩頭沒靠近過 (直接擺到繩上) 也不會被算

偵測方式 (不用額外模型):
    積木   : cube_top.pt (YOLO seg)，用顏色 + 位置做追蹤；沒被手碰的積木不准瞬移
    手     : YCrCb 膚色遮罩 (黑色板子上很穩)，扣掉積木遮罩
    繩頭   : 板子上亮、幾乎沒飽和度、細長的小區塊，且要靠近手；
             整段影片常出現在同一位置的 (另一端的固定頭、邊框、標記) 會排除

用法:
    python track_11.py                          # 開鏡頭錄影，按 q 停止後自動分析
    python track_11.py videos/vid_0001_mixed.mp4
    python track_11.py videos/                  # 整個資料夾
    python track_11.py video.mp4 --show         # 分析時顯示畫面
    python track_11.py videos/ --no-video       # 不輸出標註影片 (比較快)
輸出:
    out/<影片名>_track.mp4   標註影片
    終端機印出每顆積木的事件與最後分數
"""
import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from take import open_camera


def load_yolo():
    """torch / ultralytics 放到要分析時才載入，只錄影的話不需要裝"""
    import torch
    _original_torch_load = torch.load
    def safe_load(*args, **kwargs):
        kwargs.setdefault('weights_only', False)
        return _original_torch_load(*args, **kwargs)
    torch.load = safe_load
    from ultralytics import YOLO
    return YOLO(str(MODEL_PATH))

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "cube_top.pt"
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv"}
HAND_SCALE = 4          # 手部遮罩縮小倍率 (省記憶體)

# ================== 參數 ==================
CONF = 0.5
INIT_CONF = 0.8         # 建立積木清單時用的信心值 (避免把雜訊當積木)
COLOR_GATE = 40.0       # Lab 顏色距離超過這個就不配對
POS_WEIGHT = 200.0      # 配對時位置距離 (除以對角線) 的權重
STILL_JUMP = 1.0        # 沒被手碰的積木，一幀最多移動幾個積木邊長
MOVE_FRAC = 0.5         # 手碰到後移動超過幾個邊長才算「拿起」
HOLD_ON = 3             # 拿起計數到多少算拿著
TIP_NEAR = 1.3          # 繩頭距離積木中心 < 邊長 * 這個值 才算貼著
TIP_MIN_FRAMES = 6      # 拿著時繩頭貼著累積幾幀算穿進去


@dataclass
class Block:
    bid: int
    color: np.ndarray            # 平均 Lab
    size: float                  # 邊長 (px)
    pos: np.ndarray
    seen: bool = True
    touching: bool = False
    anchor: Optional[np.ndarray] = None   # 手剛碰到時的位置
    hold_cnt: int = 0
    held_now: bool = False
    tip_frames: int = 0
    strung: bool = False
    events: list = field(default_factory=list)


@dataclass
class FrameObs:
    dets: list          # [(center, size, lab, conf, touching)]
    hand: np.ndarray    # 縮小的手部遮罩 (bool)
    tips: list          # [(center, near_hand)]


# ================== 偵測 ==================
def find_board(frame, margin=15):
    """黑色板子的遮罩 (uint8 0/1)：最大暗色區塊的外接旋轉矩形，往內縮 margin"""
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    dark = (hsv[..., 2] < 80).astype(np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((15, 15), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(dark)
    board = np.zeros((h, w), np.uint8)
    if n < 2 or stats[1:, cv2.CC_STAT_AREA].max() < 0.2 * w * h:
        board[:] = 1
        return board
    ys, xs = np.where(labels == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    (cx, cy), (bw, bh), ang = cv2.minAreaRect(np.column_stack([xs, ys]).astype(np.float32))
    box = cv2.boxPoints(((cx, cy), (bw - 2 * margin, bh - 2 * margin), ang)).astype(np.int32)
    cv2.fillPoly(board, [box], 1)
    return board


def detect_blocks(model, frame, conf):
    """回傳 list[(center, size, mask, lab_color, conf)]"""
    r = model.predict(frame, conf=conf, verbose=False)[0]
    if r.masks is None:
        return []
    h, w = frame.shape[:2]
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    dets = []
    for m, box, cf in zip(r.masks.data.cpu().numpy(), r.boxes.xyxy.cpu().numpy(),
                          r.boxes.conf.cpu().numpy()):
        mask = cv2.resize(m.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
        core = cv2.erode(mask, np.ones((5, 5), np.uint8))
        if core.sum() < 20:
            core = mask
        color = lab[core > 0].mean(axis=0)
        x0, y0, x1, y1 = box
        center = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
        size = float(np.sqrt(mask.sum()))
        dets.append((center, size, mask, color, float(cf)))
    return dets


def skin_mask(frame, board, block_masks):
    ycc = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
    skin = cv2.inRange(ycc, (60, 135, 85), (255, 180, 135))
    for m in block_masks:
        skin[m > 0] = 0
    skin[board == 0] = 0
    return cv2.morphologyEx(skin, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))


def tip_candidates(frame, board, block_masks, hand):
    """亮、不飽和、細長的小區塊 → list[(中心, 是否靠近手)]"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # 金屬頭幾乎沒有飽和度 (S < 10)，皮膚亮處 S 約 55~70
    m = ((hsv[..., 2] > 100) & (hsv[..., 1] < 35)).astype(np.uint8)
    for bm in block_masks:
        m[bm > 0] = 0
    m[board == 0] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))  # 金屬頭有條紋，先接起來
    near_hand = cv2.dilate(hand, np.ones((31, 31), np.uint8))
    n, labels, stats, cents = cv2.connectedComponentsWithStats(m)
    out = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if not (10 <= area <= 300):
            continue
        ys, xs = np.where(labels == i)
        _, (rw, rh), _ = cv2.minAreaRect(np.column_stack([xs, ys]).astype(np.float32))
        length, width = max(rw, rh), max(1.0, min(rw, rh))
        # 繩頭是細長條；ArUco、反光、皮膚亮點都是塊狀
        if not (10 <= length <= 60 and width <= 9 and length / width >= 2.5):
            continue
        out.append((cents[i], bool(near_hand[int(cents[i][1]), int(cents[i][0])])))
    return out


def observe(model, frame, board, conf):
    """一幀的觀測：積木 (含是否碰到手)、縮小手部遮罩、繩頭候選"""
    raw = detect_blocks(model, frame, conf)
    masks = [d[2] for d in raw]
    hand = skin_mask(frame, board, masks)
    dets = []
    for center, size, mask, color, cf in raw:
        region = cv2.dilate(mask, np.ones((15, 15), np.uint8))
        dets.append((center, size, color, cf, bool(np.any(hand[region > 0]))))
    h, w = hand.shape
    small = cv2.resize(hand, (w // HAND_SCALE, h // HAND_SCALE), interpolation=cv2.INTER_AREA) > 0
    return FrameObs(dets, small, tip_candidates(frame, board, masks, hand))


def static_tip_mask(all_tips, shape, n_frames, radius=12, ratio=0.15):
    """整段影片中常常在同一位置出現的繩頭候選 → 固定物 (另一端、標記、邊框)"""
    h, w = shape
    acc = np.zeros((h // 4 + 1, w // 4 + 1), np.int32)
    for tips in all_tips:
        seen = np.zeros_like(acc, dtype=bool)
        for (x, y), _ in tips:
            seen[int(y) // 4, int(x) // 4] = True
        acc += seen
    static = (acc > ratio * n_frames).astype(np.uint8)
    return cv2.dilate(static, np.ones((2 * radius // 4 + 1,) * 2, np.uint8))


def pick_tip(tips, static, prev):
    """排除固定物，只留靠近手的；多個就選離上一幀最近的"""
    tips = [t for t, near in tips if near and not static[int(t[1]) // 4, int(t[0]) // 4]]
    if not tips:
        return None
    if prev is None:
        return tips[0]
    return min(tips, key=lambda t: np.linalg.norm(t - prev))


# ================== 追蹤 + 判定 ==================
def match_blocks(blocks, dets, diag):
    if not blocks or not dets:
        return {}
    cost = np.full((len(blocks), len(dets)), 1e6)
    for i, b in enumerate(blocks):
        for j, (c, _, col, _, _) in enumerate(dets):
            cdist = np.linalg.norm(b.color - col)
            jump = np.linalg.norm(b.pos - c)
            if cdist > COLOR_GATE:
                continue
            if not b.touching and jump > STILL_JUMP * b.size:
                continue    # 沒人碰的積木不會自己跑走
            cost[i, j] = cdist + POS_WEIGHT * jump / diag
    from scipy.optimize import linear_sum_assignment
    rows, cols = linear_sum_assignment(cost)
    return {r: c for r, c in zip(rows, cols) if cost[r, c] < 1e6}


def hand_near(hand_small, pos, r):
    x, y = (pos / HAND_SCALE).astype(int)
    r = max(1, int(r / HAND_SCALE))
    h, w = hand_small.shape
    return bool(np.any(hand_small[max(0, y - r):min(h, y + r), max(0, x - r):min(w, x + r)]))


def update_hold(b, det, hand_small, k):
    if det is not None:
        b.pos, b.seen, touching = det[0], True, det[4]
    else:
        # 沒偵測到：原本位置被手蓋住 → 當作在手上
        b.seen = False
        touching = hand_near(hand_small, b.pos, b.size)

    if touching and not b.touching:
        b.anchor = b.pos.copy()
    b.touching = touching
    in_hand = touching and (not b.seen or np.linalg.norm(b.pos - b.anchor) > MOVE_FRAC * b.size)

    b.hold_cnt = min(b.hold_cnt + 1, 10) if in_hand else max(0, b.hold_cnt - 2)
    was = b.held_now
    b.held_now = b.hold_cnt >= HOLD_ON if not was else b.hold_cnt > 0
    if b.held_now and not was:
        b.events.append((k, "拿起"))
    elif was and not b.held_now:
        b.events.append((k, "放下"))


def run_tracker(obs, init_idx, static, shape, conf_init=INIT_CONF):
    h, w = shape
    diag = float(np.hypot(w, h))
    blocks = [Block(i, d[2], d[1], d[0].copy())
              for i, d in enumerate(d for d in obs[init_idx].dets if d[3] >= conf_init)]
    states, tip = [], None
    for k, o in enumerate(obs):
        assign = match_blocks(blocks, o.dets, diag)
        for i, b in enumerate(blocks):
            update_hold(b, o.dets[assign[i]] if i in assign else None, o.hand, k)

        tip = pick_tip(o.tips, static, tip)
        if tip is not None:
            near = [(np.linalg.norm(tip - b.pos) / b.size, b) for b in blocks
                    if b.held_now and not b.strung]
            near = [x for x in near if x[0] < TIP_NEAR]
            if near:
                b = min(near, key=lambda x: x[0])[1]   # 一幀只算給最近的那顆
                if b.tip_frames == 0:
                    b.events.append((k, "繩頭貼近"))
                b.tip_frames += 1
                if b.tip_frames >= TIP_MIN_FRAMES:
                    b.strung = True
                    b.events.append((k, "→ 穿進去"))
        states.append(([(b.pos.copy(), b.seen, b.held_now, b.strung) for b in blocks], tip))
    return blocks, states


# ================== 主流程 ==================
def score_from_count(n):
    return 2 if n >= 4 else 1 if n == 3 else 0


def draw(frame, state, sizes, hand_small, board, k, fps):
    vis = frame.copy()
    hand = cv2.resize(hand_small.astype(np.uint8), frame.shape[1::-1], interpolation=cv2.INTER_NEAREST)
    vis[hand > 0] = (vis[hand > 0] * 0.6 + np.array([0, 200, 255]) * 0.4).astype(np.uint8)
    cnts, _ = cv2.findContours(board, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(vis, cnts, -1, (80, 80, 80), 1)
    blocks, tip = state
    for bid, ((pos, seen, held, strung), size) in enumerate(zip(blocks, sizes)):
        x, y = pos.astype(int)
        r = int(size / 2)
        color = (0, 255, 0) if strung else (0, 200, 255) if held else (200, 200, 200)
        cv2.rectangle(vis, (x - r, y - r), (x + r, y + r), color, 2 if seen else 1)
        cv2.putText(vis, f"#{bid}{' OK' if strung else ''}", (x - r, y - r - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    if tip is not None:
        cv2.circle(vis, tuple(int(v) for v in tip), 6, (255, 0, 255), 2)
    n = sum(s[3] for s in blocks)
    cv2.putText(vis, f"t={k / fps:5.1f}s  strung={n}  score={score_from_count(n)}",
                (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return vis


def extract(model, video_path, conf):
    """讀影片並做完所有偵測。回傳 (frames, fps, board, obs, static, init_idx)"""
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    if not frames:
        return None
    board = find_board(frames[0])
    obs = [observe(model, f, board, conf) for f in frames]
    static = static_tip_mask([o.tips for o in obs], frames[0].shape[:2], len(frames))
    # 前 2 秒內，積木最多、手最少的那幀用來建立積木清單
    init_idx = max(range(min(len(obs), int(fps * 2))),
                   key=lambda i: (sum(d[3] >= INIT_CONF for d in obs[i].dets), -int(obs[i].hand.sum())))
    return frames, fps, board, obs, static, init_idx


def analyze(model, video_path, out_dir, conf, show, write_video=True):
    print(f"[{video_path.name}] 偵測中...", flush=True)
    data = extract(model, video_path, conf)
    if data is None:
        print(f"[ERROR] 讀不到影片：{video_path}")
        return None
    frames, fps, board, obs, static, init_idx = data
    blocks, states = run_tracker(obs, init_idx, static, frames[0].shape[:2])

    out_path = out_dir / f"{video_path.stem}_track.mp4"
    if write_video or show:
        h, w = frames[0].shape[:2]
        writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h)) \
            if write_video else None
        sizes = [b.size for b in blocks]
        for k, (f, st, o) in enumerate(zip(frames, states, obs)):
            vis = draw(f, st, sizes, o.hand, board, k, fps)
            if writer:
                writer.write(vis)
            if show:
                cv2.imshow("track", vis)
                if cv2.waitKey(int(1000 / fps)) & 0xFF in (ord("q"), 27):
                    show = False
                    cv2.destroyWindow("track")
        if writer:
            writer.release()

    n = sum(b.strung for b in blocks)
    score = score_from_count(n)
    print(f"[{video_path.name}] 積木 {len(blocks)} 顆，穿進去 {n} 顆，score={score}"
          + (f"  -> {out_path}" if write_video else ""))
    for b in blocks:
        ev = ", ".join(f"{fr / fps:.1f}s {e}" for fr, e in b.events) or "沒動過"
        print(f"   #{b.bid}{' [穿進去]' if b.strung else ''}: {ev}")
    return n, score


def record(args):
    cap_dir = Path(args.capture)
    cap_dir.mkdir(parents=True, exist_ok=True)
    path = cap_dir / f"ch1-t1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    cap = open_camera(args.cam, args.width, args.height)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    writer = None
    print("SPACE: 開始/暫停錄影   q/ESC: 結束並分析")
    recording = False
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if writer is None:
            h, w = frame.shape[:2]
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        if recording:
            writer.write(frame)
        disp = frame.copy()
        cv2.putText(disp, "REC" if recording else "PAUSE  [SPACE] start  [q] stop",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 0, 255) if recording else (0, 255, 0), 2)
        cv2.imshow("Camera", disp)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(" "):
            recording = not recording
        elif key in (ord("q"), 27):
            break
    cap.release()
    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()
    print(f"[存檔] {path}")
    return path


def collect_videos(paths):
    vids = []
    for p in map(Path, paths):
        if p.is_dir():
            vids += sorted(f for f in p.iterdir() if f.suffix.lower() in VIDEO_EXTS)
        elif p.is_file():
            vids.append(p)
        else:
            print(f"[WARN] 找不到：{p}")
    return vids


def main():
    p = argparse.ArgumentParser(description="ch1-t1 串積木 影片追蹤")
    p.add_argument("inputs", nargs="*", help="影片或資料夾；不給就開鏡頭錄影")
    p.add_argument("--out", default="out")
    p.add_argument("--conf", type=float, default=CONF)
    p.add_argument("--show", action="store_true", help="分析完播放標註畫面")
    p.add_argument("--no-video", action="store_true", help="不輸出標註影片")
    p.add_argument("--cam", type=int, default=0)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--capture", default="capture", help="錄影存檔資料夾")
    args = p.parse_args()

    vids = collect_videos(args.inputs) if args.inputs else [record(args)]
    if not vids:
        sys.exit("沒有可分析的影片")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        model = load_yolo()
    except ImportError as e:
        sys.exit(f"缺少分析用的套件 ({e.name})，無法分析 (有錄影的話影片已經存好)。"
                 f"裝好後再執行 python track_11.py <影片>")

    results = []
    for v in vids:
        r = analyze(model, v, out_dir, args.conf, args.show, not args.no_video)
        if r:
            results.append((v.name, *r))
    cv2.destroyAllWindows()

    print("\n===== 總結 =====")
    for name, n, score in results:
        print(f"{name:40s} 穿進去={n}  score={score}")


if __name__ == "__main__":
    main()
