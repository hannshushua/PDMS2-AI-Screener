import cv2
import json

def camera_roi_selector(json_path="crop_config.json", cam_index=0):
    cap = cv2.VideoCapture(cam_index)
    
    if not cap.isOpened():
        print("錯誤：無法開啟攝影機")
        return

    # 設定解析度為 1920x1080
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    # 確認實際設定的解析度
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"實際解析度：{actual_w} x {actual_h}")

    print("--- 操作說明 ---")
    print("1. 在畫面上找好位置後，按下 's' 鍵進行框選")
    print("2. 按下 'q' 鍵退出程式")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display_frame = frame.copy()
        cv2.putText(display_frame, "Press 's' to Select ROI / 'q' to Quit", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.imshow("Camera Preview", display_frame)

        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('s'):
            print("暫停畫面中，請開始框選範圍...")
            roi = cv2.selectROI("Camera Preview", frame, showCrosshair=True, fromCenter=False)
            
            x, y, w, h = roi
            if w > 0 and h > 0:
                crop_data = {
                    "start_x": int(x),
                    "start_y": int(y),
                    "crop_w": int(w),
                    "crop_h": int(h)
                }
                
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(crop_data, f, indent=4)
                
                print(f"\n✅ 座標已儲存至 {json_path}")
                print(f"語法建議：cropped = frame[{y}:{y+h}, {x}:{x+w}]")
                
                crop_img = frame[y:y+h, x:x+w]
                cv2.imshow("Crop Result", crop_img)
                cv2.imwrite('crop_img.jpg', crop_img)
                print("按下任意鍵回到相機預覽...")
                cv2.waitKey(0)
                cv2.destroyWindow("Crop Result")
            else:
                print("未選取有效範圍。")

        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    camera_roi_selector(cam_index=1)    