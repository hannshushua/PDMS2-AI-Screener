import serial
import serial.tools.list_ports
import cv2
import time
import sys
import os
import json
import re
import traceback
from datetime import datetime
from pathlib import Path

# ==========================================
# 全域變數與初始狀態
# ==========================================
game_started = False
start_time = None
video_writer = None
recording = False

# 遊戲紀錄不再各自存檔；main.py 只負責把每行 log 印到 stdout，
# 由 run.py 收集後統一寫進 kid/ch5-t1_records.json（所有人的紀錄都在同一個大 JSON）。
RESULT_MARKER = "##CH5T1_RESULT##"

game_state = {
    "running": False,
    "started": False,      # Arduino 回報 [GO!] 之後為 True，前端用來顯示「開始了！」
    "bean_count": 0,
    "remaining_time": 60,
    "target_bean_count": 10,
    "warning": False,
    "game_over": False,
    "score": -1
}


def log(message):
    """輸出到 stdout，run.py 會即時讀走並收進大 JSON 的 log 陣列。"""
    print(str(message), flush=True)


def emit_result(score, end_reason, started_at):
    """在最後印一行結構化摘要，run.py 靠這行組出這次的紀錄。"""
    summary = {
        "score": int(score),
        "bean_count": game_state["bean_count"],
        "target_bean_count": game_state["target_bean_count"],
        "remaining_time": game_state["remaining_time"],
        "warning": bool(game_state["warning"]),
        "end_reason": end_reason or "",
        "started_at": started_at,
        "ended_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    print(RESULT_MARKER + json.dumps(summary, ensure_ascii=False), flush=True)


def find_arduino_port():
    """自動尋找 Arduino 序列埠：優先環境變數，其次自動偵測 USB 裝置。"""
    override = os.environ.get("ARDUINO_PORT")
    if override:
        return override

    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if p.vid is not None:  # 實體 USB 裝置（排除藍牙與 debug console）
            return p.device
    for p in ports:
        name = p.device.lower()
        if "usb" in name or name.startswith("com"):
            return p.device
    return None


def open_camera_capture(camera_index):
    """依平台選擇相機後端（與 run.py 的處理方式一致）。"""
    if sys.platform == "win32":
        capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(camera_index)
        return capture

    if sys.platform == "darwin":
        avfoundation = getattr(cv2, "CAP_AVFOUNDATION", None)
        if avfoundation is not None:
            return cv2.VideoCapture(camera_index, avfoundation)

    return cv2.VideoCapture(camera_index)


def return_score(score):
    """流程完全一致：回傳 Exit Code 給 run.py"""
    sys.exit(int(score))


_last_state_save = 0.0


def save_game_state(uid, state_data, force=False):
    """流程完全一致：儲存遊戲狀態到檔案（原子寫入，前端輪詢才不會讀到半個檔）"""
    global _last_state_save
    now = time.time()
    if not force and (now - _last_state_save) < 0.1:
        return
    _last_state_save = now

    state_file = Path(__file__).parent.parent / "kid" / uid / "Ch5-t1_state.json"
    tmp_file = state_file.parent / (state_file.name + ".tmp")
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, ensure_ascii=False)

        # Windows 上只要前端正在讀這個檔，os.replace 就會丟 WinError 5，
        # 對方放掉 handle 之後就能成功，所以短暫重試幾次。
        last_error = None
        for attempt in range(6):
            try:
                os.replace(tmp_file, state_file)
                return
            except PermissionError as e:
                last_error = e
                time.sleep(0.02 * (attempt + 1))

        # 重試仍失敗：這次狀態放掉就好（下一個 tick 會再寫），但要清掉暫存檔
        print(f"儲存狀態失敗（重試後仍被佔用）: {last_error}", flush=True)
    except Exception as e:
        print(f"儲存狀態失敗: {e}", flush=True)
    finally:
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass


def main(CAMERA_INDEX, UID):
    """回傳 (score, end_reason, started_at)，由 __main__ 交給 emit_result()。"""
    global video_writer, recording, game_started, start_time, game_state

    end_reason = ""
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. 重置與初始化狀態
    game_state["running"] = False
    game_state["bean_count"] = 0
    game_state["remaining_time"] = 60
    game_state["target_bean_count"] = 10
    game_state["warning"] = False
    game_state["game_over"] = False
    game_state["score"] = -1
    save_game_state(UID, game_state, force=True)
    log("遊戲狀態已初始化並儲存")

    # 2. 初始化 Arduino 連線
    port = find_arduino_port()
    if port is None:
        log("❌ 無法連線至 Arduino: 找不到可用的序列埠")
        return -1, "無法連線至 Arduino（找不到序列埠）", started_at
    try:
        ser = serial.Serial(port, 9600, timeout=0.1)
        time.sleep(2) # 等待 Arduino Reset
        log(f"✅ Arduino 連線成功！({port})")
    except Exception as e:
        log(f"❌ 無法連線至 Arduino: {e}")
        return -1, f"無法連線至 Arduino（{e}）", started_at

    # 3. 嘗試開啟相機 (保留你的重試機制)
    # === 暫時停用相機與錄影（僅跑 Arduino 流程）===
    # max_retries = 3
    # retry_delay = 1
    # cap = None
    # for attempt in range(max_retries):
    #     print(f"嘗試開啟相機 (索引 {CAMERA_INDEX})，第 {attempt + 1}/{max_retries} 次...")
    #     cap = open_camera_capture(CAMERA_INDEX)
    #     if cap.isOpened():
    #         print("相機開啟成功！")
    #         break
    #     cap.release()
    #     time.sleep(retry_delay)
    # else:
    #     print(f"錯誤：無法開啟相機索引 {CAMERA_INDEX}")
    #     ser.close()
    #     return -1
    cap = None
    log("（已停用相機與錄影）")

    # 4. 遊戲流程控制變數
    game_duration = 60
    has_triggered_arduino = False
    SCORE = -1

    # Arduino 每秒才回報一次剩餘秒數，這兩個變數用來在兩次回報之間自行推算，
    # 讓網頁上的秒數看起來是連續倒數的。
    arduino_remaining = None
    arduino_remaining_at = None

    # cv2.namedWindow('Arduino Monitor - Press Q to Quit', cv2.WINDOW_NORMAL)

    try:
        while True:
            # ret, frame = cap.read()
            # if not ret:
            #     print("無法讀取畫面")
            #     break
            #
            # # 移除手動裁切，改由 run.py 的 ROI 處理
            # display_frame = frame.copy()
            #
            # # 流程一致：初始化 VideoWriter
            # if video_writer is None:
            #     fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            #     video_writer = cv2.VideoWriter(str(VIDEO_PATH), fourcc, 20.0, (frame.shape[1], frame.shape[0]))
            #     print(f"開始錄影: {VIDEO_PATH}")

            # --- 核心：監聽 Arduino 數據 ---
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    log(line) # 除錯用印出（同時寫入紀錄檔）

                    # A. 啟動指令邏輯
                    if "等待" in line and "Python" in line and not has_triggered_arduino:
                        ser.write(b'R')
                        ser.flush()
                        has_triggered_arduino = True
                        game_started = True
                        start_time = time.time()
                        game_state["running"] = True
                        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        save_game_state(UID, game_state, force=True)
                        log("遊戲正式開始！")

                    # A-2. Arduino 回報 [GO!] 才是真正開始計時，通知前端顯示「開始了！」
                    if "[GO!]" in line:
                        game_state["started"] = True
                        target_match = re.search(r"目標\s*(\d+)\s*顆", line)
                        if target_match:
                            game_state["target_bean_count"] = int(target_match.group(1))
                        save_game_state(UID, game_state, force=True)

                    # B. 解析進度與警告
                    if "進度:" in line:
                        count_match = re.search(r"進度:\s*(\d+)(?:\s*/\s*(\d+))?", line)
                        time_match = re.search(r"剩餘:\s*(\d+)s", line)
                        if count_match:
                            game_state["bean_count"] = int(count_match.group(1))
                            if count_match.group(2):
                                game_state["target_bean_count"] = int(count_match.group(2))
                        if time_match:
                            game_state["remaining_time"] = int(time_match.group(1))
                            arduino_remaining = game_state["remaining_time"]
                            arduino_remaining_at = time.time()
                        # 每次進度更新都立刻寫檔，前端才看得到即時顆數與秒數
                        save_game_state(UID, game_state, force=True)

                    if "違規" in line:
                        game_state["warning"] = True
                        save_game_state(UID, game_state, force=True)

                    # 記下結束原因（時間到 / 達成目標 / 違規），寫進紀錄
                    if "遊戲結束原因" in line:
                        reason_match = re.search(r"遊戲結束原因[：:]\s*(.+)", line)
                        if reason_match:
                            end_reason = reason_match.group(1).strip()

                    # C. 解析得分 (結束判定)
                    if "最終得分等級" in line and "[" in line:
                        score_match = re.search(r"\[\s*(\d+)\s*\]", line)
                        if score_match:
                            SCORE = int(score_match.group(1))
                            game_state["score"] = SCORE
                            game_state["game_over"] = True
                            game_state["running"] = False
                            save_game_state(UID, game_state, force=True)

                            # 流程一致：顯示結束畫面與分數
                            # cv2.putText(display_frame, f'GAME OVER - Score: {SCORE}',
                            #            (display_frame.shape[1]//2 - 200, display_frame.shape[0]//2),
                            #            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)
                            # cv2.imshow('Arduino Monitor - Press Q to Quit', display_frame)
                            # cv2.waitKey(2000)
                            log(f"GAME OVER - Score: {SCORE}")
                            break

            # 流程一致：即時顯示資訊於畫面上
            # if game_started:
            #     info_y = 30
            #     cv2.putText(display_frame, f'Bean Count: {game_state["bean_count"]}', (10, info_y),
            #                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
            #     cv2.putText(display_frame, f'Time: {game_state["remaining_time"]}s', (10, info_y + 40),
            #                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
            #     if game_state["warning"]:
            #         cv2.putText(display_frame, 'WARNING!', (10, info_y + 80),
            #                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

            # 兩次 Arduino 回報之間自行推算秒數，維持畫面上的連續倒數
            if game_state["running"] and arduino_remaining is not None:
                elapsed = int(time.time() - arduino_remaining_at)
                game_state["remaining_time"] = max(0, arduino_remaining - elapsed)

            # 流程一致：定期儲存 JSON
            save_game_state(UID, game_state)

            # 流程一致：顯示畫面與錄影
            # cv2.imshow('Arduino Monitor - Press Q to Quit', display_frame)
            # video_writer.write(frame)
            #
            # if cv2.waitKey(1) & 0xFF in [ord('q'), ord('Q')]:
            #     break
            time.sleep(0.01)  # 取代 cv2.waitKey 的節流，避免空轉吃滿 CPU

    except KeyboardInterrupt:
        log("中斷")
        if not end_reason:
            end_reason = "使用者中斷"
    finally:
        # 清理資源
        # if video_writer: video_writer.release()
        # cap.release()
        # cv2.destroyAllWindows()
        ser.close()

    return SCORE, end_reason, started_at

if __name__ == "__main__":
    # 流程完全一致：接收參數
    UID = None
    CAMERA_INDEX = 0
    if len(sys.argv) >= 3:
        UID = sys.argv[1]
        CAMERA_INDEX = int(sys.argv[2])
    else:
        sys.exit(-1)

    # 狀態檔仍需要 kid/<uid> 資料夾
    BASE_DIR = Path(__file__).parent.parent
    (BASE_DIR / "kid" / UID).mkdir(parents=True, exist_ok=True)

    # 啟動主程式；log 走 stdout，最後印一行摘要給 run.py 收進大 JSON
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        score, end_reason, started_at = main(CAMERA_INDEX, UID)
    except Exception as e:
        # 任何未預期的錯誤也要留下 -1 的摘要，run.py 才知道這次是失敗而不是 0 分
        score, end_reason = -1, f"程式異常：{e}"
        traceback.print_exc()

    if score < 0:
        game_state["score"] = -1
        game_state["game_over"] = True
        save_game_state(
            UID, {**game_state, "error": end_reason or "執行失敗"}, force=True
        )

    emit_result(score, end_reason, started_at)
    return_score(score)
