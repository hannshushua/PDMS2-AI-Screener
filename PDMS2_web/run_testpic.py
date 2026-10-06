# run_testpic.py
# -*- coding: utf-8 -*-
"""
離線批次分析 + 計時工具（不開相機、不開網頁、不寫 DB 成績）。

用途：量測論文要填的 "Mean analysis time per task = [X] s"。
做法：把 testpic/ 底下的照片依關卡餵給各關的 main.py，記錄每一次
      「影像輸入完成 → 分數產出」的牆鐘時間，整個過程與統計寫進
      testpic/console.txt。

放照片的方式（兩種都支援，可混用）：
  1) 資料夾分關卡（建議）
       testpic/Ch1-t1/a.jpg
       testpic/Ch1-t2/a-side.jpg + testpic/Ch1-t2/a-top.jpg
       testpic/Ch2-t1/kid01.jpg
  2) 直接平放，檔名以關卡代號開頭
       testpic/Ch2-t1_kid01.jpg
       testpic/Ch1-t3-side.jpg + testpic/Ch1-t3-top.jpg

同一個樣本的 -side / -top（或 _side / _top）會自動配成一組。
Ch1-t2 / Ch1-t3 / Ch1-t4 需要 side + top 兩張，缺一張會跳過並記錄原因。
Ch5-t1 是 Arduino 即時計數的關卡，沒有照片可重跑，預設略過（見報告備註）。

用法：
    python run_testpic.py                # 跑 testpic/ 全部，每個樣本跑 1 次
    python run_testpic.py --repeat 3     # 每個樣本重跑 3 次（取平均較穩）
    python run_testpic.py --only Ch2     # 只跑 Ch2 開頭的關卡
    python run_testpic.py --only Ch1-t1,Ch3-t4
    python run_testpic.py --keep-warmup  # 重跑時把第 1 次（含模型載入）也算進平均
"""
import argparse
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
TESTPIC_DIR = ROOT / "testpic"
CONSOLE_PATH = TESTPIC_DIR / "console.txt"
KID_DIR = ROOT / "kid"

# 設計目標：單一任務分析時間 <= 15 秒
TARGET_SECONDS = 15.0
RUN_TIMEOUT = 600

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

# 17 個項目，依章節排序；後兩欄是寫進報告用的說明
TASKS = [
    ("Ch1-t1", "串積木 string_blocks", "YOLO + SAM"),
    ("Ch1-t2", "金字塔 pyramid", "YOLO + SAM（側視＋俯視）"),
    ("Ch1-t3", "階梯 stair", "YOLO + SAM（側視＋俯視）"),
    ("Ch1-t4", "疊牆 build_wall", "YOLO + SAM（側視＋俯視）"),
    ("Ch2-t1", "畫圓 draw_circle", "YOLO + CNN + 骨架分析"),
    ("Ch2-t2", "畫方 draw_square", "YOLO + CNN + 骨架分析"),
    ("Ch2-t3", "畫十字 draw_cross", "YOLO + CNN + 骨架分析"),
    ("Ch2-t4", "畫直線 draw_line", "紙張分割 + 骨架分析"),
    ("Ch2-t5", "著色 color", "紙張分割 + 範圍比對"),
    ("Ch2-t6", "連點 connect_dots", "紙張分割 + 骨架分析"),
    ("Ch3-t1", "剪圓 cut_circle", "YOLO 分割 + ArUco + 輪廓"),
    ("Ch3-t2", "剪方 cut_square", "YOLO 分割 + ArUco + 輪廓"),
    ("Ch3-t3", "剪紙 cut_paper", "YOLO 分割 + ArUco + 輪廓"),
    ("Ch3-t4", "剪線 cut_line", "紙張輪廓模型 + 面積比"),
    ("Ch4-t1", "單摺 one_fold", "YOLO + 幾何運算"),
    ("Ch4-t2", "雙摺 two_fold", "邊緣偵測 + 幾何運算"),
    ("Ch5-t1", "撿豆子 collect_raisins", "Arduino 即時計數（無照片可離線重跑）"),
]
TASK_CODES = [t[0] for t in TASKS]
TASK_INFO = {code: (name, pipeline) for code, name, pipeline in TASKS}

# 需要 side + top 兩張圖的關卡
MULTI_VIEW_TASKS = {"Ch1-t2", "Ch1-t3", "Ch1-t4"}
# 不吃照片、無法離線重跑的關卡
SENSOR_TASKS = {"Ch5-t1"}

VIEW_SUFFIX_RE = re.compile(r"[-_](side|top)$", re.IGNORECASE)
TASK_PREFIX_RE = re.compile(r"^(ch\s*\d+\s*[-_]\s*t\s*\d+)", re.IGNORECASE)


# =========================
# 輸出：同時印到螢幕與 console.txt
# =========================
class Console:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "w", encoding="utf-8", newline="\n")
        # Windows 終端預設 cp950，遇到 ≤ ✓ ─ 之類字元會丟 UnicodeEncodeError，
        # 那會把整支量測程式帶倒，所以先把 stdout 轉成可容錯的輸出。
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    def write(self, msg: str = ""):
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            enc = sys.stdout.encoding or "utf-8"
            print(msg.encode(enc, "replace").decode(enc, "replace"), flush=True)
        self.fh.write(msg + "\n")
        self.fh.flush()

    def rule(self, char: str = "=", width: int = 78):
        self.write(char * width)

    def close(self):
        self.fh.close()


def fmt_secs(v) -> str:
    return "n/a" if v is None else f"{v:.3f}"


def canon_task(raw: str):
    """把 ch1t1 / CH1-T1 / ch1_t1 之類正規化成 Ch1-t1；認不出來回 None。"""
    s = re.sub(r"[\s_]+", "-", raw.strip())
    m = re.match(r"^ch-?(\d+)-?t-?(\d+)$", s, re.IGNORECASE)
    if not m:
        return None
    code = f"Ch{int(m.group(1))}-t{int(m.group(2))}"
    return code if code in TASK_INFO else None


def safe_name(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "_", s).strip("_") or "sample"


# =========================
# 掃描 testpic/
# =========================
def collect_samples() -> dict:
    """回傳 {task_code: [ {name, side, top, main}, ... ]}，依關卡與樣本名排序。"""
    buckets = {code: {} for code in TASK_CODES}

    def add(task_code: str, sample_name: str, view: str, path: Path):
        group = buckets[task_code].setdefault(
            sample_name, {"name": sample_name, "side": None, "top": None, "main": None}
        )
        # 同名同視角重複出現時（例如副檔名不同）保留先掃到的
        if group.get(view) is None:
            group[view] = path

    def classify(stem: str):
        """回傳 (樣本名, 視角)。視角為 side / top / main。"""
        m = VIEW_SUFFIX_RE.search(stem)
        if m:
            return (stem[: m.start()].strip("-_ ") or "sample"), m.group(1).lower()
        return stem, "main"

    if not TESTPIC_DIR.exists():
        return {}

    # 1) 關卡子資料夾
    for sub in sorted(p for p in TESTPIC_DIR.iterdir() if p.is_dir()):
        code = canon_task(sub.name)
        if not code:
            continue
        for f in sorted(sub.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
                continue
            sample, view = classify(f.stem)
            add(code, sample, view, f)

    # 2) 平放在 testpic/ 根目錄、檔名以關卡代號開頭的檔案
    for f in sorted(p for p in TESTPIC_DIR.iterdir() if p.is_file()):
        if f.suffix.lower() not in IMAGE_EXTS:
            continue
        m = TASK_PREFIX_RE.match(f.stem)
        if not m:
            continue
        code = canon_task(m.group(1))
        if not code:
            continue
        rest = f.stem[m.end():].strip("-_ ")
        if not rest:
            # 檔名就只有關卡代號，例如 ch2-t1.jpg
            sample, view = code, "main"
        elif rest.lower() in ("side", "top"):
            # 代號後面直接接視角，例如 ch1-t2-side.jpg，視為同一個樣本
            sample, view = code, rest.lower()
        else:
            sample, view = classify(rest)
        add(code, sample, view, f)

    return {
        code: [groups[k] for k in sorted(groups)]
        for code, groups in buckets.items()
        if groups
    }


# =========================
# 執行單一樣本
# =========================
def stage_inputs(task_code: str, sample: dict, uid: str):
    """把測試照片複製到 kid/<uid>/，回傳 (img_id, [已複製的檔案]) 或 (None, 原因字串)。"""
    uid_dir = KID_DIR / uid
    if uid_dir.exists():
        shutil.rmtree(uid_dir, ignore_errors=True)
    uid_dir.mkdir(parents=True, exist_ok=True)

    img_id = task_code  # main.py 讀的是 kid/<uid>/<img_id>.jpg
    staged = []

    if task_code in MULTI_VIEW_TASKS:
        if not sample.get("side") or not sample.get("top"):
            missing = "side" if not sample.get("side") else "top"
            return None, f"缺少 {missing} 視角照片（此關卡需要 -side 與 -top 各一張）"
        for view in ("side", "top"):
            dst = uid_dir / f"{img_id}-{view}.jpg"
            shutil.copyfile(sample[view], dst)
            staged.append(dst)
    else:
        src = sample.get("main") or sample.get("top") or sample.get("side")
        if not src:
            return None, "找不到可用的照片"
        dst = uid_dir / f"{img_id}.jpg"
        shutil.copyfile(src, dst)
        staged.append(dst)

    return img_id, staged


def run_once(task_code: str, img_id: str, uid: str, con: Console, indent: str = "    ") -> dict:
    """跑一次 main.py，回傳 {score, returncode, elapsed, timeout, lines}。"""
    script = ROOT / task_code.lower() / "main.py"
    if not script.exists():
        script = ROOT / task_code / "main.py"

    cmd = [sys.executable, "-u", str(script), uid, img_id]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    # 這支腳本只做離線量測，不要跳出任何 OpenCV 視窗卡住流程
    env["PDMS2_ENABLE_OPENCV_ROI_GUI"] = "0"
    env["MPLBACKEND"] = "Agg"

    con.write(f"{indent}$ {' '.join(cmd)}")

    # t_start：影像已就位，開始分析
    t_start = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    lines = []
    timed_out = False
    deadline = t_start + RUN_TIMEOUT
    try:
        for raw in proc.stdout:
            line = raw.rstrip("\r\n")
            if line:
                dt = time.perf_counter() - t_start
                lines.append((dt, line))
                con.write(f"{indent}  [+{dt:6.2f}s] {line}")
            if time.perf_counter() > deadline:
                timed_out = True
                proc.kill()
                break
        returncode = proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
        if proc.stdout:
            proc.stdout.close()

    # t_end：分數產出（main.py 以 exit code 回傳分數）
    elapsed = time.perf_counter() - t_start

    score = returncode if returncode in (0, 1, 2) else -1
    return {
        "score": score,
        "returncode": returncode,
        "elapsed": elapsed,
        "timeout": timed_out,
        "lines": lines,
    }


def measure_startup_overhead(n: int = 3) -> float:
    """空跑 python 直譯器的時間，用來估算「扣掉行程啟動」的淨分析時間。"""
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        subprocess.run([sys.executable, "-c", "pass"], capture_output=True)
        samples.append(time.perf_counter() - t0)
    return min(samples)


# =========================
# 報告
# =========================
def describe_env(con: Console, overhead: float):
    con.rule()
    con.write("PDMS-2 AI 分析時間量測報告（離線批次，只讀照片）")
    con.rule()
    con.write(f"產生時間        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    con.write(f"專案根目錄      : {ROOT}")
    con.write(f"測試照片目錄    : {TESTPIC_DIR}")
    con.write(f"Python          : {sys.version.split()[0]}  ({sys.executable})")
    con.write(f"作業系統        : {platform.platform()}")
    con.write(f"CPU             : {platform.processor() or platform.machine()}"
              f"  (邏輯核心 {os.cpu_count()})")

    gpu = "未偵測到 torch"
    try:
        import torch  # type: ignore

        con.write(f"PyTorch         : {torch.__version__}")
        if torch.cuda.is_available():
            gpu = f"CUDA {torch.version.cuda} / {torch.cuda.get_device_name(0)}"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            gpu = "Apple MPS"
        else:
            gpu = "CPU only（torch 未偵測到 GPU）"
    except Exception as e:
        gpu = f"未偵測到 torch（{e}）"
    con.write(f"加速裝置        : {gpu}")

    try:
        import cv2  # type: ignore

        con.write(f"OpenCV          : {cv2.__version__}")
    except Exception:
        pass

    # Git LFS 指標檔只有 100 多 bytes，torch.load 會噴 "invalid load key" 之類的怪訊息，
    # 先在報告開頭點名，免得被誤判成分析邏輯壞掉。
    pointers = []
    for pat in ("*.pth", "*.pt"):
        for f in sorted(ROOT.glob(f"*/{pat}")):
            try:
                if f.stat().st_size < 1000 and f.read_bytes()[:7] == b"version":
                    pointers.append(f.relative_to(ROOT))
            except OSError:
                continue
    if pointers:
        con.write("模型權重        : 下列檔案還是 Git LFS 指標（未下載），相關關卡必定失敗：")
        for p in pointers:
            con.write(f"                  - {p}")
        con.write("                  解法：在專案根目錄執行 git lfs pull")
    else:
        con.write("模型權重        : 皆已下載（無 Git LFS 指標檔）")

    con.write(f"直譯器啟動開銷  : {overhead:.3f} s（每次量測都含這段，統計會另列扣除值）")
    con.write(f"設計目標        : 單一任務分析時間 <= {TARGET_SECONDS:.0f} s")
    con.write("")
    con.write("量測定義：t_start = 照片已就位、呼叫分析程式的瞬間；"
              "t_end = 分析程式回傳分數的瞬間。")
    con.write("          含模型載入與行程啟動，等同臨床現場實際等待時間。")
    con.write("")


def summarize(con: Console, results: list, overhead: float, warmup_excluded: bool):
    ok = [r for r in results if r["ok"]]

    con.rule()
    con.write("逐次結果")
    con.rule()
    con.write(f"{'關卡':<8} {'樣本':<22} {'次序':<5} {'分數':>4} {'耗時(s)':>9}  備註")
    con.write("-" * 78)
    for r in results:
        note = "" if r["ok"] else (r.get("error") or "失敗")
        score_txt = str(r["score"]) if r["ok"] else "-"
        con.write(
            f"{r['task']:<8} {r['sample'][:22]:<22} {r['run_idx']:<5} "
            f"{score_txt:>4} {fmt_secs(r['elapsed']):>9}  {note}"
        )
    con.write("")

    con.rule()
    con.write("各關卡統計" + ("（已排除每關第 1 次暖機）" if warmup_excluded else ""))
    con.rule()
    con.write(f"{'關卡':<8} {'項目':<26} {'n':>3} {'平均':>8} {'標準差':>8} "
              f"{'最小':>8} {'最大':>8}  {'≤15s'}")
    con.write("-" * 78)

    chapter_pool = {}
    task_means = []
    for code in TASK_CODES:
        name, _pipeline = TASK_INFO[code]
        vals = [r["elapsed"] for r in ok if r["task"] == code]
        if not vals:
            reason = "感測器關卡，無照片" if code in SENSOR_TASKS else "無測試照片"
            con.write(f"{code:<8} {name[:26]:<26} {'-':>3} {'-':>8} {'-':>8} "
                      f"{'-':>8} {'-':>8}  ({reason})")
            continue
        mean = statistics.fmean(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        task_means.append((code, mean))
        chapter_pool.setdefault(code.split("-")[0], []).extend(vals)
        flag = "OK" if mean <= TARGET_SECONDS else "超標"
        con.write(
            f"{code:<8} {name[:26]:<26} {len(vals):>3} {mean:>8.3f} {sd:>8.3f} "
            f"{min(vals):>8.3f} {max(vals):>8.3f}  {flag}"
        )
    con.write("")

    con.rule()
    con.write("各章節統計（同章節所有樣本合併）")
    con.rule()
    con.write(f"{'章節':<8} {'n':>4} {'平均':>9} {'標準差':>9} {'最小':>9} {'最大':>9}")
    con.write("-" * 78)
    for ch in sorted(chapter_pool):
        vals = chapter_pool[ch]
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        con.write(f"{ch:<8} {len(vals):>4} {statistics.fmean(vals):>9.3f} {sd:>9.3f} "
                  f"{min(vals):>9.3f} {max(vals):>9.3f}")
    con.write("")

    con.rule()
    con.write("總結")
    con.rule()
    if not ok:
        con.write("沒有任何成功的量測，無法計算平均值。")
        con.write("請確認 testpic/ 內有照片，且檔名符合關卡命名規則。")
        return

    all_vals = [r["elapsed"] for r in ok]
    grand_mean = statistics.fmean(all_vals)
    macro = statistics.fmean([m for _, m in task_means])
    net = grand_mean - overhead

    con.write(f"成功樣本次數                : {len(ok)} / {len(results)}")
    con.write(f"涵蓋項目數                  : {len(task_means)} / {len(TASKS)}")
    con.write(f"所有量測平均 (micro)        : {grand_mean:.3f} s")
    con.write(f"各項目平均再平均 (macro)    : {macro:.3f} s"
              "   ← 論文 Mean analysis time per task 建議填這個")
    con.write(f"標準差 (所有量測)           : "
              f"{statistics.stdev(all_vals) if len(all_vals) > 1 else 0.0:.3f} s")
    con.write(f"範圍                        : {min(all_vals):.3f} ~ {max(all_vals):.3f} s")
    con.write(f"扣除直譯器啟動後的平均      : {net:.3f} s")
    over = [(r["task"], r["sample"], r["elapsed"]) for r in ok if r["elapsed"] > TARGET_SECONDS]
    con.write(f"超過 {TARGET_SECONDS:.0f} s 的次數           : {len(over)} / {len(ok)}")
    for t, s, v in over:
        con.write(f"    - {t} / {s}: {v:.3f} s")
    con.write("")
    con.write(f"可填入論文：Mean analysis time per task = {macro:.1f} s "
              f"(range {min(all_vals):.1f}-{max(all_vals):.1f} s, n = {len(ok)})")
    con.write("")
    con.write("備註：")
    con.write("  1. Ch5-t1（撿豆子）以 Arduino 即時計數，分數在動作當下產生，")
    con.write("     無照片可離線重跑；其分析時間視為近乎即時（<1 s），未納入上表統計。")
    con.write("  2. 每次量測皆包含 Python 行程啟動與模型載入時間，")
    con.write("     為現場實際等待時間；如需純推論時間請看「扣除直譯器啟動後的平均」。")
    con.write("  3. 重現實驗時請一併記錄本報告開頭的硬體規格。")


# =========================
# main
# =========================
def parse_args():
    ap = argparse.ArgumentParser(description="離線讀 testpic/ 照片並量測各關卡分析時間")
    ap.add_argument("--repeat", type=int, default=1, help="每個樣本重複跑幾次（預設 1）")
    ap.add_argument("--only", default="", help="只跑指定關卡，逗號分隔，可用 Ch2 或 Ch2-t1")
    ap.add_argument("--keep-warmup", action="store_true",
                    help="repeat>1 時，把每個關卡第 1 次（含模型載入）也算進統計")
    ap.add_argument("--keep-staged", action="store_true",
                    help="保留 kid/ 底下暫存的輸入圖（預設只留結果圖）")
    return ap.parse_args()


def main():
    args = parse_args()
    TESTPIC_DIR.mkdir(parents=True, exist_ok=True)

    only = set()
    for token in (t.strip() for t in args.only.split(",") if t.strip()):
        code = canon_task(token)
        if code:
            only.add(code)
        else:
            only.update(c for c in TASK_CODES if c.lower().startswith(token.lower()))

    samples = collect_samples()
    if only:
        samples = {k: v for k, v in samples.items() if k in only}

    con = Console(CONSOLE_PATH)
    try:
        overhead = measure_startup_overhead()
        describe_env(con, overhead)

        if not samples:
            con.write("testpic/ 內沒有找到符合命名規則的照片。")
            con.write("")
            con.write("請這樣放（兩種擇一或混用）：")
            con.write("  testpic/Ch2-t1/kid01.jpg")
            con.write("  testpic/Ch1-t2/kid01-side.jpg + testpic/Ch1-t2/kid01-top.jpg")
            con.write("  testpic/Ch2-t1_kid01.jpg")
            return 1

        sample_count = sum(len(v) for v in samples.values())
        total = sample_count * max(1, args.repeat)
        con.write(f"找到 {sample_count} 個樣本，每個跑 {args.repeat} 次，共 {total} 次量測。")
        con.write("")

        results = []
        counter = 0
        for code in TASK_CODES:
            if code not in samples:
                continue
            name, pipeline = TASK_INFO[code]

            con.rule()
            con.write(f"{code}  {name}   pipeline: {pipeline}")
            con.rule()

            if code in SENSOR_TASKS:
                con.write("  此關卡由 Arduino 即時計數，無法用照片離線重跑，略過。")
                con.write("")
                continue

            for sample in samples[code]:
                uid = f"_testpic_{safe_name(code)}_{safe_name(sample['name'])}"
                con.write(f"  樣本: {sample['name']}")
                for view in ("main", "side", "top"):
                    if sample.get(view):
                        con.write(f"    輸入: {sample[view]}")

                img_id, staged = stage_inputs(code, sample, uid)
                if img_id is None:
                    con.write(f"    略過：{staged}")
                    con.write("")
                    results.append({
                        "task": code, "sample": sample["name"], "run_idx": 1,
                        "ok": False, "score": None, "elapsed": None, "error": staged,
                    })
                    continue

                for i in range(1, args.repeat + 1):
                    counter += 1
                    con.write(f"    -- 第 {i}/{args.repeat} 次（整體 {counter}/{total}）")
                    try:
                        r = run_once(code, img_id, uid, con)
                    except Exception as e:
                        con.write(f"    執行例外：{e}")
                        results.append({
                            "task": code, "sample": sample["name"], "run_idx": i,
                            "ok": False, "score": None, "elapsed": None, "error": str(e),
                        })
                        continue

                    if r["timeout"]:
                        con.write(f"    逾時（>{RUN_TIMEOUT}s），已中止")
                        ok, err = False, "逾時"
                    elif r["score"] < 0:
                        con.write(f"    分析失敗（exit code={r['returncode']}），"
                                  f"耗時 {r['elapsed']:.3f} s")
                        ok, err = False, f"分析失敗 exit={r['returncode']}"
                    else:
                        con.write(f"    分數 = {r['score']}，耗時 {r['elapsed']:.3f} s"
                                  f"（{'OK' if r['elapsed'] <= TARGET_SECONDS else '超過 15s'}）")
                        ok, err = True, ""

                    results.append({
                        "task": code, "sample": sample["name"], "run_idx": i,
                        "ok": ok, "score": r["score"], "elapsed": r["elapsed"],
                        "error": err,
                    })

                # 結果圖留在 kid/<uid>/ 方便肉眼核對；輸入圖刪掉省空間
                if not args.keep_staged:
                    for p in staged:
                        try:
                            p.unlink()
                        except OSError:
                            pass
                con.write(f"    結果圖: {KID_DIR / uid}")
                con.write("")

        # 排除暖機：每個關卡第一個樣本的第 1 次（含模型首次載入）
        warmup_excluded = False
        stats_results = results
        if args.repeat > 1 and not args.keep_warmup:
            seen = set()
            filtered = []
            for r in results:
                if r["run_idx"] == 1 and r["task"] not in seen:
                    seen.add(r["task"])
                    continue
                filtered.append(r)
            if any(r["ok"] for r in filtered):
                stats_results = filtered
                warmup_excluded = True

        summarize(con, stats_results, overhead, warmup_excluded)
        con.write("")
        con.write(f"完整紀錄已寫入：{CONSOLE_PATH}")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
