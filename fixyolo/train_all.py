"""
train_all.py - 形狀分類一鍵訓練：依序跑完並比較結果

依序:
  1. quickdraw_pretrain.py   Quick, Draw! 預訓練 -> runs/classify/quickdraw_pre
  2. train_cls.py --rebuild  照目前 shape_result 重建 train/val，用預訓練權重微調 -> runs/classify/shape_cls_qd
  3. train_cls.py            對照組：ImageNet yolo11n-cls 直接訓練 (同一份 train/val) -> runs/classify/shape_cls_base
  4. 印出兩個模型的 val 比較表
每步都是獨立的子程序 (GPU 記憶體會釋放)，任一步失敗就停。

用法:
    python train_all.py                    # 全部跑
    python train_all.py --skip-base        # 不跑對照組
    python train_all.py --skip-pretrain    # 已經有 quickdraw_pre 的權重，直接微調
    python train_all.py --epochs 150 --pre-epochs 20 --model yolo11s-cls.pt
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from train_cls import BASE_DIR, CLASSES

RUNS = BASE_DIR / "runs" / "classify"


def parse_args():
    p = argparse.ArgumentParser(description="Quick, Draw! 預訓練 + 微調 + 對照組，依序跑完並比較")
    p.add_argument("--model", default="yolo11n-cls.pt", help="起始模型 (預訓練和對照組都用它)")
    p.add_argument("--pre-epochs", type=int, default=15, help="Quick, Draw! 預訓練 epoch")
    p.add_argument("--per-class", type=int, default=6000, help="Quick, Draw! 每類幾張")
    p.add_argument("--epochs", type=int, default=100, help="微調 / 對照組 epoch (有 early stop)")
    p.add_argument("--device", default=None, help="例: 0 / cpu (預設自動)")
    p.add_argument("--skip-pretrain", action="store_true", help="沿用已有的 runs/classify/quickdraw_pre")
    p.add_argument("--skip-base", action="store_true", help="不跑對照組")
    return p.parse_args()


def run(step, cmd):
    print(f"\n{'=' * 70}\n[{step}] {' '.join(cmd)}\n{'=' * 70}", flush=True)
    t = time.time()
    r = subprocess.run([sys.executable] + cmd, cwd=BASE_DIR)
    if r.returncode != 0:
        sys.exit(f"[{step}] 失敗 (exit {r.returncode})，停止")
    print(f"[{step}] 完成，{(time.time() - t) / 60:.1f} 分鐘", flush=True)


def main():
    args = parse_args()
    dev = ["--device", args.device] if args.device else []
    pre_best = RUNS / "quickdraw_pre" / "weights" / "best.pt"
    t0 = time.time()

    if args.skip_pretrain:
        if not pre_best.exists():
            sys.exit(f"--skip-pretrain 但找不到 {pre_best}")
    else:
        run("1/3 Quick, Draw! 預訓練",
            ["quickdraw_pretrain.py", "--model", args.model, "--epochs", str(args.pre_epochs),
             "--per-class", str(args.per_class)] + dev)

    run("2/3 微調 (Quick, Draw! 底)",
        ["train_cls.py", "--rebuild", "--model", str(pre_best), "--name", "shape_cls_qd",
         "--epochs", str(args.epochs)] + dev)

    names = ["shape_cls_qd"]
    if not args.skip_base:
        run("3/3 對照組 (ImageNet 底)",
            ["train_cls.py", "--model", args.model, "--name", "shape_cls_base",
             "--epochs", str(args.epochs)] + dev)
        names.append("shape_cls_base")

    # 比較表
    print(f"\n{'=' * 70}\n全部完成，共 {(time.time() - t0) / 60:.1f} 分鐘\n")
    print(f"{'模型':<16}{'準確率':>8}" + "".join(f"{c:>9}" for c in CLASSES) + "   (各類 recall)")
    for n in names:
        m = json.load(open(RUNS / n / "val_metrics.json", encoding="utf-8"))
        print(f"{n:<16}{m['acc']:>9.3f}" + "".join(f"{m['recall'][c]:>9.3f}" for c in CLASSES))
    print("\n※ val 只有約 60 張不同照片，差 1~2% 可能只是隨機差異，請一起看各類 recall 和 val_errors/")
    for n in names:
        print(f"  {n}: {RUNS / n / 'weights' / 'best.pt'}   分錯的圖: {RUNS / n / 'val_errors'}")


if __name__ == "__main__":
    main()
