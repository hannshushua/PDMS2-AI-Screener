#include "HX711.h"

const int DT_PIN = 2;
const int SCK_PIN = 3;
HX711 scale;

const float CALIBRATION_FACTOR = 326.0; 
const float BEAN_WEIGHT = 0.270;    // 2026-10-06 實測：每顆約 0.20~0.37g，取 0.27g 當一顆的標準
const float STABLE_TOLERANCE = 0.15; // 歸零前判定「秤已穩定」的容許晃動（克）

// 尖峰觸發數豆子（2026-10-06 用兩輪真實原始讀數調出來的參數；HX711 約每 0.09 秒一筆）
// 豆子落下時第一筆會比前幾筆高出 0.3g 以上（撞擊尖峰），秤的低頻漂移則慢慢晃、單筆跳不到 0.2g
const float SPIKE_JUMP = 0.25;  // 這筆比前 5 筆中位數高出這麼多 → 尖峰
const int PRE_SAMPLES = 8;      // 尖峰前取 8 筆中位數當「放之前」的重量
const int POST_SKIP = 3;        // 最後一個尖峰後跳過 3 筆（還在震）
const int POST_WAIT = 8;        // 最後一個尖峰後第 8 筆才結算，取第 3~8 筆中位數當「放之後」的重量
const int SPIKE_GAP = 2;        // 尖峰讀數相隔超過 2 筆（中間有回落）才算新的一個尖峰
const int HIST = 16;            // 原始讀數環狀緩衝區大小（要大於 PRE_SAMPLES + 1）
float hist[HIST];
long sampleNo = 0;              // 開始後的第幾筆讀數
bool inEvent = false;           // 是否正在等一次放豆子結算
float eventBase = 0;            // 這次放之前的重量
long lastSpike = 0;             // 最後一個尖峰是第幾筆
int spikeCount = 0;             // 這次共有幾個尖峰（快速連投 2 顆會有 2 個，同時丟 2 顆只有 1 個）
bool violated = false;          // 曾經同時丟入多顆：遊戲照常進行（不讓小朋友發現），結束時判 0 分

const unsigned long GAME_TIME = 60000;
const int TARGET_BEANS = 10;
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

// 取 hist 裡第 from ~ to 筆（含）的中位數；筆數是偶數時取中間兩筆平均
float histMedian(long from, long to) {
  float a[HIST];
  int n = 0;
  for (long k = from; k <= to; k++) a[n++] = hist[k % HIST];
  for (int i = 1; i < n; i++) {   // 插入排序（最多 8 筆，最簡單）
    float key = a[i];
    int j = i - 1;
    while (j >= 0 && a[j] > key) { a[j + 1] = a[j]; j--; }
    a[j + 1] = key;
  }
  if (n % 2 == 1) return a[n / 2];
  return (a[n / 2 - 1] + a[n / 2]) / 2;
}

// 等秤穩定再歸零：連續 5 次（每次 3 筆平均，約 1.5 秒）讀數變化都小於容許值才回傳，最多等 10 秒
void waitForStable() {
  float last = scale.get_units(3);
  int calmCount = 0;
  unsigned long t0 = millis();
  while (calmCount < 5 && millis() - t0 < 10000) {
    float now = scale.get_units(3);
    if (fabs(now - last) < STABLE_TOLERANCE) calmCount++;
    else calmCount = 0;
    last = now;
  }
}

void loop() {
  // --- 1. 監聽 Python 指令 ---
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    
    if (cmd == 'R') {  
      // --- 重點修改：把原本在 setup 的儀式感移到這裡 ---
      Serial.println(">>> [指令接收] 準備開始測驗...");
      Serial.println(">>> 請放上空瓶，秤穩定後自動歸零...");
      delay(3000); // 這裡給一點時間讓使用者放瓶子

      waitForStable();  // 等杯子、軟墊沉降完、桌面不晃再歸零
      scale.tare(20);   // 執行歸零（取 20 筆平均當零點）
      for (int i = 0; i < HIST; i++) hist[i] = 0;
      sampleNo = 0;
      inEvent = false;
      violated = false;
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
    long i = sampleNo;
    float w = scale.get_units(1);
    hist[i % HIST] = w;

    // 顯示用重量：最近 5 筆的中位數
    float currentWeight = (i >= 4) ? histMedian(i - 4, i) : w;

    if (i >= PRE_SAMPLES) {
      // 1. 這筆是不是尖峰：比前 5 筆的中位數高出 SPIKE_JUMP
      bool isSpike = (w - histMedian(i - 5, i - 1)) >= SPIKE_JUMP;

      if (!inEvent) {
        if (isSpike) {
          // 看到尖峰 → 開始一次放豆子事件，記下放之前的重量
          inEvent = true;
          eventBase = histMedian(i - PRE_SAMPLES, i - 1);
          lastSpike = i;
          spikeCount = 1;
        }
      } else {
        if (isSpike) {
          if (i - lastSpike > SPIKE_GAP) spikeCount++;  // 中間有回落 → 又一顆落下
          lastSpike = i;
        }
        // 2. 最後一個尖峰後過了 POST_WAIT 筆（約 0.7 秒）→ 結算這次增加了幾顆
        if (i - lastSpike == POST_WAIT) {
          float delta = histMedian(i - (POST_WAIT - POST_SKIP), i) - eventBase;
          // 換算顆數：半顆重以上算 1 顆；第 2 顆起要多到 0.85 顆重才進位（一般四捨五入是 0.5）
          // 因為重的單顆（0.37g）加上漂移會超過 1.5 顆重，四捨五入會被當成 2 顆而誤判違規
          int n = (delta >= BEAN_WEIGHT * 0.5) ? (int)(delta / BEAN_WEIGHT + 0.15) : 0;
          if (delta >= BEAN_WEIGHT * 0.5 && n < 1) n = 1;
          inEvent = false;
          if (n >= 2 && spikeCount < n) {
            // 增加了 n 顆的重量，尖峰卻比 n 少 → 同時丟進多顆，違規
            // 遊戲不中斷、顆數照算，結束時才判 0 分（這行刻意不寫「違規」二字，免得前端跳出警告）
            violated = true;
            Serial.print(">>> [記錄] 同時丟入多顆，第 "); Serial.print(elapsedTime / 1000);
            Serial.println(" 秒，結束時判 0 分");
          }
          if (n >= 1) {
            // 一顆一顆放（快速連投 n 顆會有 n 個尖峰，算 n 顆）
            // 增加不到半顆（漂移、豆子彈出去）n = 0，不計數
            lastTotalBeans += n;
            if (lastTotalBeans >= TARGET_BEANS) {
              // 放滿後遊戲立刻結束、不會再印每秒進度，先補印一行，前端才會顯示 10/10
              Serial.print("剩餘: "); Serial.print(remainingSec);
              Serial.print("s | 重量: "); Serial.print(currentWeight < 0 ? 0 : currentWeight, 2);
              Serial.print("g | 進度: "); Serial.print(lastTotalBeans);
              Serial.println("/10");
              isGameOver = true;
              isStarted = false;
              endReason = "達成目標 10 顆！";
            }
          }
        }
      }
    }
    sampleNo++;
    if (remainingSec != lastSecond && !isGameOver) {
      float shownWeight = currentWeight < 0 ? 0 : currentWeight;  // 只有顯示時把負數壓成 0
      Serial.print("剩餘: "); Serial.print(remainingSec);
      Serial.print("s | 重量: "); Serial.print(shownWeight, 2);
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
    if (violated) score = 0;  // 曾同時丟入多顆：不管放了幾顆都判 0 分

    // ========================================
    // 請覆蓋這段：確保【先印原因，再印得分】
    // ========================================
    Serial.println("\n================================");
    
    Serial.print("遊戲結束原因：");
    Serial.print(endReason);
    if (violated) Serial.print("（違規：曾一次放入超過一顆，判 0 分）");
    Serial.println();
    
    Serial.print("最終得分等級：[ "); 
    Serial.print(score); 
    Serial.println(" ]"); 
    
    Serial.println("================================");
    endReason = ""; 
  }
  delay(30); 
}