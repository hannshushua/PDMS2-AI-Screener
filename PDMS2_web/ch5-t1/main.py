import serial
import cv2
import time
import sys
import json
import re
from pathlib import Path

# ==========================================
# 全域變數與初始狀態
# ==========================================
game_started = False
start_time = None
video_writer = None
recording = False

game_state = {
    "running": False,
    "bean_count": 0,
    "remaining_time": 60,
    "target_bean_count": 10,
    "warning": False,
    "game_over": False,
    "score": -1
}

def return_score(score):
    """流程完全一致：回傳 Exit Code 給 run.py"""
    sys.exit(int(score))

def save_game_state(uid, state_data):
    """流程完全一致：儲存遊戲狀態到檔案"""
    state_file = Path(__file__).parent.parent / "kid" / uid / "Ch5-t1_state.json"
    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, ensure_ascii=False)
    except Exception as e:
        print(f"儲存狀態失敗: {e}")

def main(CAMERA_INDEX, VIDEO_PATH, UID):
    global video_writer, recording, game_started, start_time, game_state

    # 1. 重置與初始化狀態
    game_state["running"] = False
    game_state["bean_count"] = 0
    game_state["remaining_time"] = 60
    game_state["target_bean_count"] = 10
    game_state["warning"] = False
    game_state["game_over"] = False
    game_state["score"] = -1
    save_game_state(UID, game_state)
    print("遊戲狀態已初始化並儲存")

    # 2. 初始化 Arduino 連線
    try:
        ser = serial.Serial('COM3', 9600, timeout=0.1)
        time.sleep(2) # 等待 Arduino Reset
        print("✅ Arduino 連線成功！")
    except Exception as e:
        print(f"❌ 無法連線至 Arduino: {e}")
        return -1

    # 3. 嘗試開啟相機 (保留你的重試機制)
    max_retries = 3
    retry_delay = 1
    cap = None
    for attempt in range(max_retries):
        print(f"嘗試開啟相機 (索引 {CAMERA_INDEX})，第 {attempt + 1}/{max_retries} 次...")
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        if cap.isOpened():
            print("相機開啟成功！")
            break
        cap.release()
        time.sleep(retry_delay)
    else:
        print(f"錯誤：無法開啟相機索引 {CAMERA_INDEX}")
        ser.close()
        return -1

    # 4. 遊戲流程控制變數
    game_duration = 60
    has_triggered_arduino = False
    SCORE = -1
    
    cv2.namedWindow('Arduino Monitor - Press Q to Quit', cv2.WINDOW_NORMAL)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("無法讀取畫面")
                break
            
            # 移除手動裁切，改由 run.py 的 ROI 處理
            display_frame = frame.copy()

            # 流程一致：初始化 VideoWriter
            if video_writer is None:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_writer = cv2.VideoWriter(str(VIDEO_PATH), fourcc, 20.0, (frame.shape[1], frame.shape[0]))
                print(f"開始錄影: {VIDEO_PATH}")

            # --- 核心：監聽 Arduino 數據 ---
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(line) # 除錯用印出

                    # A. 啟動指令邏輯
                    if "等待" in line and "Python" in line and not has_triggered_arduino:
                        ser.write(b'R')
                        ser.flush()
                        has_triggered_arduino = True
                        game_started = True
                        start_time = time.time()
                        game_state["running"] = True
                        print("遊戲正式開始！")

                    # B. 解析進度與警告
                    if "進度:" in line:
                        count_match = re.search(r"進度:\s*(\d+)", line)
                        time_match = re.search(r"剩餘:\s*(\d+)s", line)
                        if count_match: game_state["bean_count"] = int(count_match.group(1))
                        if time_match: game_state["remaining_time"] = int(time_match.group(1))
                    
                    if "違規" in line:
                        game_state["warning"] = True

                    # C. 解析得分 (結束判定)
                    if "最終得分等級" in line and "[" in line:
                        score_match = re.search(r"\[\s*(\d+)\s*\]", line)
                        if score_match:
                            SCORE = int(score_match.group(1))
                            game_state["score"] = SCORE
                            game_state["game_over"] = True
                            game_state["running"] = False
                            save_game_state(UID, game_state)
                            
                            # 流程一致：顯示結束畫面與分數
                            cv2.putText(display_frame, f'GAME OVER - Score: {SCORE}', 
                                       (display_frame.shape[1]//2 - 200, display_frame.shape[0]//2),
                                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)
                            cv2.imshow('Arduino Monitor - Press Q to Quit', display_frame)
                            cv2.waitKey(2000)
                            break

            # 流程一致：即時顯示資訊於畫面上
            if game_started:
                info_y = 30
                cv2.putText(display_frame, f'Bean Count: {game_state["bean_count"]}', (10, info_y),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                cv2.putText(display_frame, f'Time: {game_state["remaining_time"]}s', (10, info_y + 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                if game_state["warning"]:
                    cv2.putText(display_frame, 'WARNING!', (10, info_y + 80),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

            # 流程一致：定期儲存 JSON
            save_game_state(UID, game_state)

            # 流程一致：顯示畫面與錄影
            cv2.imshow('Arduino Monitor - Press Q to Quit', display_frame)
            video_writer.write(frame)

            if cv2.waitKey(1) & 0xFF in [ord('q'), ord('Q')]:
                break

    except KeyboardInterrupt:
        print("中斷")
    finally:
        # 清理資源
        if video_writer: video_writer.release()
        cap.release()
        cv2.destroyAllWindows()
        ser.close()

    return SCORE

if __name__ == "__main__":
    # 流程完全一致：接收參數
    UID = None
    CAMERA_INDEX = 0
    if len(sys.argv) >= 3:
        UID = sys.argv[1]
        CAMERA_INDEX = int(sys.argv[2])
    else:
        sys.exit(-1)

    # 流程完全一致：建立輸出路徑
    BASE_DIR = Path(__file__).parent.parent
    OUTPUT_DIR = BASE_DIR / "kid" / UID
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_PATH = OUTPUT_DIR / "Ch5-t1_result.mp4"

    # 啟動主程式並回傳分數
    score = main(CAMERA_INDEX, VIDEO_PATH, UID)
    return_score(score)