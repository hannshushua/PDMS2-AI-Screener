#include "HX711.h"

const int DT_PIN = 2;
const int SCK_PIN = 3;
HX711 scale;

const float CALIBRATION_FACTOR = 326.0; 
const float BEAN_WEIGHT = 0.240;    
const float NOISE_THRESHOLD = 0.12; 
const unsigned long GAME_TIME = 60000; 
const int TARGET_BEANS = 10;       
int candidateBeans = 0;   // 暫存最新算出的顆數
int stableCount = 0;      // 記錄該顆數連續出現的次數
const int REQUIRE_STABLE_LOOPS = 5; // 門檻：連續 3 次讀取都一樣才算數
int lastTotalBeans = 0;
unsigned long startTime = 0;
bool isGameOver = true;   
bool isStarted = false;   
String endReason = ""; 
int lastSecond = -1;

void setup() {
  Serial.begin(9600); 
  scale.begin(DT_PIN, SCK_PIN);
  scale.set_scale(CALIBRATION_FACTOR); 
  
  // 這裡只印一次，代表硬體準備好了
  Serial.println(">>> [系統] Arduino 就緒，等待 Python 啟動指令...");
}

void loop() {
  // --- 1. 監聽 Python 指令 ---
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    
    if (cmd == 'R') {  
      // --- 重點修改：把原本在 setup 的儀式感移到這裡 ---
      Serial.println(">>> [指令接收] 準備開始測驗...");
      Serial.println(">>> 請放上空瓶，3秒後自動歸零...");
      delay(3000); // 這裡給一點時間讓使用者放瓶子
      
      scale.tare(); // 執行歸零
      Serial.println(">>> 歸零完成！");
      
      // 初始化遊戲數值
      lastTotalBeans = 0;
      startTime = millis();   
      isGameOver = false;     
      isStarted = true;       
      lastSecond = -1;
      endReason = "";
      
      Serial.println(">>> [GO!] 計時開始！目標 10 顆！");
    }
  }

  if (!isStarted || isGameOver) return; 

  // --- 2. 秤重與倒數邏輯 (保持不變) ---
  unsigned long currentTime = millis();
  unsigned long elapsedTime = currentTime - startTime;
  int remainingSec = (int)((GAME_TIME - elapsedTime) / 1000);

  if (elapsedTime >= GAME_TIME) {
    isGameOver = true;
    isStarted = false; 
    endReason = "時間到！";
    remainingSec = 0; 
  }

  if (scale.is_ready()) {
    float currentWeight = scale.get_units(1); 
    if (currentWeight < 0) currentWeight = 0;

    float rawBeans = currentWeight / BEAN_WEIGHT;
    int currentBeans = lastTotalBeans; 
    
    // 1. 先初步算出「當下」的顆數
    // 1. 先初步算出「當下」的顆數
    if (currentWeight < NOISE_THRESHOLD) {
      currentBeans = 0;
    } 
    else {
      // 直接使用標準的四捨五入 (+0.5 取整數)
      currentBeans = (int)(rawBeans + 0.5); 
    }

    // --- 新增：軟體濾波防彈跳邏輯 ---
    // 2. 檢查這次算出的顆數，跟上一次迴圈算出的有沒有一樣
    if (currentBeans != candidateBeans) {
      // 如果不一樣（可能是在撞擊震盪中），重新計數
      candidateBeans = currentBeans;
      stableCount = 1; 
    } else {
      // 如果一樣，穩定次數 + 1
      stableCount++; 
    }

    // 3. 只有當這個顆數「連續出現」達到我們要求的次數，且確實有變化時，才進入計分/違規判定
    if (stableCount >= REQUIRE_STABLE_LOOPS && candidateBeans != lastTotalBeans) {
      
      int addedBeans = candidateBeans - lastTotalBeans; // 計算增加了幾顆
      
      // 違規判定邏輯（一次增加 2 顆或以上）
      // 違規判定邏輯（一次增加 2 顆或以上）
      if (addedBeans >= 2) {
        isGameOver = true;
        isStarted = false;
        endReason = "違規：一次放入超過一顆！";
        lastTotalBeans = 0; // 違規直接歸零
      } 
      // 正常情況：嚴格限制【一次只能增加 1 顆】
      else if (addedBeans == 1) {
        lastTotalBeans = candidateBeans;
        if (candidateBeans >= TARGET_BEANS) {
          isGameOver = true;
          isStarted = false;
          endReason = "達成目標 10 顆！";
        }
      }
      // 【最強防護】：如果 addedBeans < 0 (重量變輕)
      // 我們什麼都不寫，程式會直接忽略這次的減少！
      // 這樣就能完美抵禦「幽靈掉磅」造成的失憶誤判。
    }
    if (remainingSec != lastSecond && !isGameOver) {
      Serial.print("剩餘: "); Serial.print(remainingSec);
      Serial.print("s | 重量: "); Serial.print(currentWeight, 2);
      Serial.print("g | 進度: "); Serial.print(lastTotalBeans);
      Serial.println("/10");
      lastSecond = remainingSec;
    }
  }

  // --- 3. 遊戲結束輸出 ---
  // --- 3. 遊戲結束輸出 ---
  if (isGameOver && endReason != "") {
    int score = 0;
    if (lastTotalBeans >= 10 && remainingSec >= 30) score = 2;
    else if (lastTotalBeans >= 5) score = 1;
    else score = 0;

    // ========================================
    // 請覆蓋這段：確保【先印原因，再印得分】
    // ========================================
    Serial.println("\n================================");
    
    Serial.print("遊戲結束原因："); 
    Serial.println(endReason);
    
    Serial.print("最終得分等級：[ "); 
    Serial.print(score); 
    Serial.println(" ]"); 
    
    Serial.println("================================");
    endReason = ""; 
  }
  delay(30); 
}