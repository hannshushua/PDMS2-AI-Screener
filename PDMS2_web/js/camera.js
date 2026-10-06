// camera.js (修正跳轉邏輯：存檔後直接回主頁)

const KEY = "kid-quest-progress-v1";
const TOP = 0; 
const SIDE = 1; 
const waittime = 3;
const DEFAULT_CAMERA_SETTING = { top: TOP, side: SIDE };

// 遊戲狀態輪詢變數
let gameStateInterval = null;

function getId(){
  const u = new URL(location.href);
  return u.searchParams.get("id");
}

async function getUid(){
  try {
    const response = await fetch('/session/get-uid');
    if (response.ok) {
      const result = await response.json();
      return result.uid;
    } else {
      const st = JSON.parse(localStorage.getItem(KEY) || "{}");
      return st.currentUid || null;
    }
  } catch (error) {
    console.error('獲取 UID 時發生錯誤:', error);
    const st = JSON.parse(localStorage.getItem(KEY) || "{}");
    return st.currentUid || null;
  }
}

function isImagePath(s){ return typeof s==="string" && (s.startsWith("/images/") || /\.(png|jpe?g|svg|webp|gif)$/i.test(s)); }
function setIcon(el, src){
  if(!el) return;
  el.innerHTML = isImagePath(src) ? `<img class="icon-img" src="${encodeURI(src)}" alt="" onerror="this.remove()">` : "";
}

async function loadCameraSetting() {
  try {
    const response = await fetch("/camera-settings");
    if (!response.ok) throw new Error("讀取攝影機設定失敗");
    const result = await response.json();
    if (!result.success || !result.settings) throw new Error("讀取攝影機設定失敗");

    const top = Number.isInteger(result.settings.top)
      ? result.settings.top
      : DEFAULT_CAMERA_SETTING.top;
    const side = Number.isInteger(result.settings.side)
      ? result.settings.side
      : DEFAULT_CAMERA_SETTING.side;

    return { top, side };
  } catch (error) {
    return { ...DEFAULT_CAMERA_SETTING };
  }
}

function getCameraIndex(role) {
  const setting = cameraSetting;
  return role === "side" ? setting.side : setting.top;
}

let cameraSetting = { ...DEFAULT_CAMERA_SETTING };

const ID_TO_META = {
  "ch1-t1": {icon:"/images/chart/ch1-t1-串積木.png", title:"串積木：做成一條橋"},
  "ch1-t2": {icon:"/images/chart/ch1-t2-疊城堡.png", title:"疊城堡：蓋瞭望塔"},
  "ch1-t3": {icon:"/images/chart/ch1-t3-疊階梯.png", title:"疊階梯：翻過高牆"},
  "ch1-t4": {icon:"/images/chart/ch1-t4-疊高牆.png", title:"疊高牆：蓋出傳送門"},
  "ch2-t1": {icon:"/images/chart/ch2-t1-畫圓.png", title:"畫圓：大圓圓魔法陣"},
  "ch2-t2": {icon:"/images/chart/ch2-t2-畫方.png", title:"畫方：守護盾"},
  "ch2-t3": {icon:"/images/chart/ch2-t3-畫十字.png", title:"畫十字：啟動魔法"},
  "ch2-t4": {icon:"/images/chart/ch2-t4-描水平線.png", title:"描水平線：打敗恐龍"},
  "ch2-t5": {icon:"/images/chart/ch2-t5-兩水平線中塗色.png", title:"兩水平線中塗色：提升威力"},
  "ch2-t6": {icon:"/images/chart/ch2-t6-兩點連線.png", title:"兩點連線：開門"},
  "ch3-t1": {icon:"/images/chart/ch3-t1-剪圓.png", title:"剪圓：做圓形窗戶"},
  "ch3-t2": {icon:"/images/chart/ch3-t2-剪方.png", title:"剪方：做方方正正的門"},
  "ch3-t3": {icon:"/images/chart/ch3-t3-剪窗簾.png", title:"剪窗簾：裝飾圓窗"},
  "ch3-t4": {icon:"/images/chart/ch3-t4-剪地毯.png", title:"剪地毯：幫房子鋪地毯"},
  "ch4-t1": {icon:"/images/chart/ch4-t1-摺紙一摺.png", title:"摺紙一摺：變出小飛毯"},
  "ch4-t2": {icon:"/images/chart/ch4-t2-摺紙兩摺.png", title:"摺紙兩摺：更結實的飛毯"},
  "ch5-t1": {icon:"/images/chart/ch5-t1-豆豆裝罐子.png", title:"豆豆裝罐子：完成任務"},
  "ch5-t2": {icon:"/images/chart/ch5-t2-解鈕扣.png", title:"解鈕扣：打開魔法披風"},
  "ch5-t3": {icon:"/images/chart/ch5-t3-扣鈕扣.png", title:"扣鈕扣：穿上魔法披風"},
};

// 鈕扣關：錄影而不是拍照
const BUTTON_TASKS = ["ch5-t2", "ch5-t3"];

const els = {
  taskIcon: document.getElementById("taskIcon"),
  taskTitle: document.getElementById("taskTitle"),
  cameraStream: document.getElementById("cameraStream"),
  placeholderText: document.getElementById("placeholderText"),
  statusInfo: document.getElementById("statusInfo"),
  shotBtn: document.getElementById("shotBtn"), 
  stopBtn: document.getElementById("stopBtn"),
  // Ch5-t1 專用元素
  gameInfo: document.getElementById("gameInfo"),
  goBanner: document.getElementById("goBanner"),
  doneBanner: document.getElementById("doneBanner"),
  startVoice: document.getElementById("startVoice"),
  beanCount: document.getElementById("beanCount"),
  timeRemaining: document.getElementById("timeRemaining"),
  targetBeanCount: document.getElementById("targetBeanCount"),
};

let cameraActive = false;
let streamInterval = null;
let frameRequestInFlight = false;
const id = getId();

// 統一跳回首頁的函數
function goHome() {
    window.location.href = "/html/index.html";
}

const TASK_ORDER = [
  "ch1-t1","ch1-t2","ch1-t3","ch1-t4",
  "ch2-t1","ch2-t2","ch2-t3","ch2-t4","ch2-t5","ch2-t6",
  "ch3-t1","ch3-t2","ch3-t3","ch3-t4",
  "ch4-t1","ch4-t2",
  "ch5-t1","ch5-t2","ch5-t3"
];

function goNext() {
  const idx = TASK_ORDER.indexOf(id);
  if (idx !== -1 && idx < TASK_ORDER.length - 1) {
    window.location.href = `/html/task.html?id=${encodeURIComponent(TASK_ORDER[idx + 1])}`;
  } else {
    goHome();
  }
}

function updateStatus(message, type = 'info') {
  els.statusInfo.textContent = message;
  els.statusInfo.className = `status-info ${type}`;
}

// 關卡色：相機頁沿用那一關的掛圖顏色（id 形如 ch2-t1）
(function applyChapterColour(){
  const n = parseInt(((id || "").match(/^ch(\d+)/) || [])[1], 10);
  if (n >= 1 && n <= 5) {
    const root = document.documentElement;
    root.style.setProperty("--accent",      `var(--ch${n})`);
    root.style.setProperty("--accent-on",   `var(--ch${n}-on)`);
    root.style.setProperty("--accent-tint", `var(--ch${n}-tint)`);
  }
})();

// 初始化標題
(function initHeader(){
  const meta = ID_TO_META[id] || {icon:"", title:"拍照存證"};
  setIcon(els.taskIcon, meta.icon);
  if(meta.title && els.taskTitle) els.taskTitle.textContent = meta.title;
  
  if (els.stopBtn) {
      els.stopBtn.style.display = 'none';
  }
  
  if (id === "ch5-t1") {
    // Ch5-t1 隱藏拍照按鈕（因為會自動開始）
    els.shotBtn.style.display = 'none';
    
    // 顯示遊戲資訊區塊
    if (els.gameInfo) {
      els.gameInfo.style.display = 'block';
    }
    // 隱藏相機預覽區域
    if (els.cameraStream) {
      els.cameraStream.style.display = 'none';
    }
    if (els.placeholderText) {
      els.placeholderText.textContent = '遊戲準備中...';
    }
  } else if (BUTTON_TASKS.includes(id)) {
    els.shotBtn.textContent = "開始錄影";
    els.shotBtn.dataset.icon = "rec";
  } else {
      els.shotBtn.textContent = "拍照、存檔並進下一關";
  }
})();

// 串流預覽
function startVideoStream() {
  if (streamInterval) clearInterval(streamInterval);
  streamInterval = setInterval(async () => {
    if (frameRequestInFlight) return;
    frameRequestInFlight = true;
    try {
      const response = await fetch('/opencv-camera/frame');
      if (!response.ok) return;
      const data = await response.json();
      if (data.success) {
        els.cameraStream.src = "data:image/jpeg;base64," + data.image;
      }
    } catch (err) {
      console.error("獲取幀錯誤:", err);
    } finally {
      frameRequestInFlight = false;
    }
  }, 120);
}

// 開啟相機
async function openCamera() {
  // Ch5-t1 不需要開啟相機預覽，直接自動開始遊戲
  if (id === "ch5-t1") {
    updateStatus('準備自動開始遊戲...', 'info');
    // 延遲1秒後自動開始遊戲
    setTimeout(() => {
      autoStartGame();
    }, 1000);
    return;
  }
  
  try {
    updateStatus('正在開啟相機...', 'loading');
    let CAM_INDEX = getCameraIndex("top");
    if(["ch1-t2", "ch1-t3", "ch1-t4"].includes(id)) CAM_INDEX = getCameraIndex("side");
    
    const response = await fetch('/opencv-camera/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: id, camera_index: CAM_INDEX })
    });
    if (!response.ok) throw new Error('無法開啟相機');
    const result = await response.json();
    if (result.success) {
      cameraActive = true;
      updateStatus('相機預覽已開啟，請準備！', 'success');
      els.placeholderText.style.display = 'none';
      els.cameraStream.style.display = 'block';
      els.shotBtn.disabled = false;
      startVideoStream();
    } else {
      throw new Error(result.error || '開啟相機失敗');
    }
  } catch (error) {
    // 技術細節只留給主控台；畫面上給孩子與大人看得懂的話，並提供再試一次
    console.error('開啟相機錯誤:', error);
    updateStatus('相機還沒準備好，請大人幫忙檢查一下', 'error');
    const retry = document.getElementById('retryBtn');
    if (retry) retry.hidden = false;
  }
}

// 再試一次：重新開啟相機
(function bindRetry(){
  const retry = document.getElementById('retryBtn');
  if (!retry) return;
  retry.addEventListener('click', async () => {
    retry.hidden = true;
    await openCamera();
  });
})();

// 輪詢遊戲狀態（Ch5-t1 專用）
// 開始語音只播一次；輪詢每 0.5 秒會一直進來，所以要自己記住播過了
let startVoicePlayed = false;

function playStartVoice() {
  if (startVoicePlayed || !els.startVoice) return;
  startVoicePlayed = true;

  const attempt = () => {
    const p = els.startVoice.play();
    if (p && typeof p.catch === "function") {
      p.catch(() => {
        // 瀏覽器擋掉自動播放，等使用者第一次碰畫面再補播
        const kick = () => {
          document.removeEventListener("pointerdown", kick);
          document.removeEventListener("keydown", kick);
          els.startVoice.play().catch(() => {});
        };
        document.addEventListener("pointerdown", kick);
        document.addEventListener("keydown", kick);
      });
    }
  };
  attempt();
}

async function pollGameState(uid) {
  console.log('[遊戲狀態] 開始輪詢，UID:', uid);
  startVoicePlayed = false;   // 同一頁重開一局時語音要能再播
  
  if (gameStateInterval) {
    clearInterval(gameStateInterval);
  }
  
  gameStateInterval = setInterval(async () => {
    try {
      const response = await fetch(`/game-state/${uid}`);
      if (!response.ok) {
        console.warn('[遊戲狀態] 無法取得遊戲狀態，狀態碼:', response.status);
        return;
      }
      
      const data = await response.json();
      console.log('[遊戲狀態] 收到資料:', data);
      
      if (data.success && data.state) {
        const state = data.state;
        
        // 更新顯示
        if (els.beanCount) {
          els.beanCount.textContent = state.bean_count;
          console.log('[遊戲狀態] 更新豆豆數量:', state.bean_count);
        }
        if (els.timeRemaining) {
          els.timeRemaining.textContent = state.remaining_time;
          console.log('[遊戲狀態] 更新剩餘時間:', state.remaining_time);
        }
        if (els.targetBeanCount) {
          els.targetBeanCount.textContent = state.target_bean_count || 10;
          console.log('[遊戲狀態] 目標豆豆數量:', state.target_bean_count);
        }
        
        // 已經開始就不用再顯示「遊戲準備中...」
        if (els.placeholderText && (state.started || state.game_over)) {
          els.placeholderText.style.display = "none";
        }

        // Arduino 喊 [GO!] 了，畫面上顯示綠色的「開始了！」並播放提示語音
        if (els.goBanner) {
          els.goBanner.style.display = (state.started && !state.game_over) ? "block" : "none";
        }
        if (state.started && !state.game_over) {
          playStartVoice();
        }
        // 結束後換成橘黃色的「完成了，你真棒」
        if (els.doneBanner) {
          els.doneBanner.style.display = state.game_over ? "block" : "none";
        }

        // 警告提示
        if (state.warning) {
          updateStatus('注意：檢測到作弊行為！', 'error');
        } else if (state.running) {
          const target = state.target_bean_count || 10;
          updateStatus(`遊戲進行中... 豆豆：${state.bean_count}/${target} | 剩餘：${state.remaining_time}秒`, 'loading');
        }
        
        // 遊戲結束
        if (state.game_over) {
          console.log('[遊戲狀態] 遊戲結束，分數:', state.score);
          clearInterval(gameStateInterval);
          gameStateInterval = null;
          
          let resultMsg = '';
          if (state.score === 2) {
            resultMsg = '完美完成！';
          } else if (state.score === 1) {
            resultMsg = '完成任務！';
          } else {
            resultMsg = '完成任務！';
          }
          
          updateStatus(`遊戲結束！${resultMsg}`, 'success');
          
          // 3秒後跳轉回主頁
          setTimeout(() => {
            goHome(); // <--- 修改這裡：跳轉回主頁
          }, 3000);
        }
      }
    } catch (error) {
      console.error('[遊戲狀態] 輪詢錯誤:', error);
    }
  }, 500); // 每0.5秒更新一次
}

async function captureWithCamera(cameraIndex, fullTaskId, uid, skipStart = false) {
  try {
    if (!skipStart) {
      const switchResponse = await fetch('/opencv-camera/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camera_index: cameraIndex })
      });
      if (!switchResponse.ok) {
        throw new Error('切換相機失敗');
      }
      await new Promise(r => setTimeout(r, 500));
    }

    const captureResponse = await fetch('/opencv-camera/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_id: fullTaskId,
        uid: uid
      })
    });
    if (!captureResponse.ok) throw new Error('拍照失敗');
    return await captureResponse.json();
  } catch (error) {
    console.error('拍照錯誤:', error);
    throw error;
  }
}

async function triggerBackgroundAnalysis(taskId, uid) {
  try {
    let body_data = { 
        id: taskId,
        uid: uid 
    };
    
    if (taskId === "ch5-t1") {
      body_data.cam_index = getCameraIndex("side"); 
    } else {
      body_data.cam_index = getCameraIndex("top"); 
    }

    const response = await fetch('/run-python', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body_data)
    });
    
    if (!response.ok) {
      console.warn('分析請求失敗');
      return;
    }
    
    const result = await response.json();
    console.log('分析已觸發:', result);
    return result.task_id;
    
  } catch (error) {
    console.warn('觸發分析時發生錯誤:', error);
  }
}

// 清空遊戲狀態的函數
async function clearGameState(uid) {
  try {
    const response = await fetch('/clear-game-state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid: uid })
    });
    
    if (!response.ok) {
      console.warn('清空遊戲狀態失敗');
      return false;
    }
    
    const result = await response.json();
    console.log('遊戲狀態已清空:', result);
    return true;
  } catch (error) {
    console.error('清空遊戲狀態錯誤:', error);
    return false;
  }
}

// 自動開始遊戲（Ch5-t1 專用）
async function autoStartGame() {
  try {
    console.log('[自動開始] 準備開始遊戲...');
    const currentUid = await getUid() || 'default';
    
    updateStatus('遊戲即將開始...', 'loading');
    
    // 清空遊戲狀態
    await clearGameState(currentUid);
    console.log('[自動開始] 狀態已清空');
    
    // 短暫延遲確保狀態已寫入
    await new Promise(r => setTimeout(r, 300));
    
    updateStatus('遊戲開始！請開始收集豆豆...', 'loading');
    
    // 觸發後端遊戲程式
    await triggerBackgroundAnalysis(id, currentUid);
    console.log('[自動開始] 遊戲已啟動');
    
    // 開始輪詢遊戲狀態
    pollGameState(currentUid);
    
  } catch (error) {
    console.error('[自動開始] 錯誤:', error);
    updateStatus(`自動開始失敗: ${error.message}`, 'error');
  }
}

// 主函數（保留給其他任務使用）
async function takeShot() {
  try {
    const currentUid = await getUid() || 'default';
    els.shotBtn.disabled = true;
    
    if (id === "ch5-t1") {
      // Ch5-t1 走自動流程，不應執行到此
      console.log('[takeShot] Ch5-t1 應該使用自動開始，不應執行到此處');
      return;
      
    } else if (["ch1-t2", "ch1-t3", "ch1-t4"].includes(id)) {
      // === 需要拍兩張（side + top）的任務 ===
      await countdown(waittime);

      // 1. 拍側面（預覽時已開著 side 相機，直接拍）
      updateStatus('正在拍攝側面鏡頭...', 'loading');
      await captureWithCamera(getCameraIndex("side"), `${id}-side`, currentUid, true);

      // 2. 切換並拍上方
      updateStatus('側面完成，切換上方鏡頭...', 'loading');
      await captureWithCamera(getCameraIndex("top"), `${id}-top`, currentUid, false);

      // 兩張都拍完才關相機
      await closeCamera();

      // 3. 呼叫後端分析（背景執行）
      updateStatus('正在分析並寫入資料庫...', 'loading');
      await triggerBackgroundAnalysis(id, currentUid);

      // 4. 全部完成才關相機，再跳轉
      await closeCamera();
      updateStatus('存檔完成！準備進下一關...', 'success');
      await new Promise(r => setTimeout(r, 800));
      goNext();

    } else {
      // === 一般單張照片任務 ===
      await countdown(waittime);

      // 1. 拍上方（預覽時已開著 top 相機，直接拍）
      updateStatus('正在拍照（上方鏡頭）...', 'loading');
      await captureWithCamera(getCameraIndex("top"), id, currentUid, true);

      // 拍完才關相機
      await closeCamera();

      // 2. 呼叫後端分析（背景執行）
      updateStatus('正在分析並寫入資料庫...', 'loading');
      await triggerBackgroundAnalysis(id, currentUid);

      // 3. 完成後才跳轉
      updateStatus('存檔完成！準備進下一關...', 'success');
      await new Promise(r => setTimeout(r, 800));
      goNext();
    }
    
  } catch (error) {
    console.error('操作錯誤:', error);
    updateStatus(`操作失敗: ${error.message}`, 'error');
    els.shotBtn.disabled = false;
    // 如果失敗，重新開啟相機讓使用者重試
    if (id !== "ch5-t1") {
      await openCamera();
    }
  }
}

async function countdown(seconds) {
  for (let i = seconds; i > 0; i--) {
    updateStatus(`準備拍照... ${i}`, 'loading');
    await new Promise(r => setTimeout(r, 1000));
  }
}

async function closeCamera() {
  try {
    if (streamInterval) {
      clearInterval(streamInterval);
      streamInterval = null;
    }
    const response = await fetch('/opencv-camera/stop', { method: 'POST' });
    if (!response.ok) console.warn('無法通知後端關閉相機');
    cameraActive = false;
    els.shotBtn.disabled = true;
    els.placeholderText.style.display = 'block';
    els.cameraStream.style.display = 'none';
    els.cameraStream.src = "";
    updateStatus('相機已關閉', 'info');
  } catch (err) {
    console.error('關閉相機失敗:', err);
  }
}

// 鈕扣關：開始錄影
async function startRecording() {
  try {
    const uid = await getUid() || 'default';
    updateStatus('正在開始錄影...', 'loading');
    const response = await fetch('/opencv-camera/record/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: id, uid: uid })
    });
    const result = await response.json();
    if (!result.success) {
      updateStatus(`開始錄影失敗：${result.error || ''}`, 'error');
      return;
    }
    els.shotBtn.style.display = 'none';
    els.stopBtn.style.display = 'inline-flex';
    document.body.classList.add('is-recording');
    updateStatus('錄影中', 'recording');
  } catch (err) {
    console.error('開始錄影失敗:', err);
    updateStatus('開始錄影失敗', 'error');
  }
}

// 鈕扣關：停止錄影並關閉相機
async function stopRecording() {
  try {
    els.stopBtn.disabled = true;
    document.body.classList.remove('is-recording');
    updateStatus('正在存檔...', 'loading');
    const response = await fetch('/opencv-camera/record/stop', { method: 'POST' });
    const result = await response.json();
    await closeCamera();
    if (result.success) {
      updateStatus('錄影完成！準備進下一關...', 'success');
      await new Promise(r => setTimeout(r, 800));
      goNext();
    } else {
      updateStatus(`停止錄影失敗：${result.error || ''}`, 'error');
    }
  } catch (err) {
    console.error('停止錄影失敗:', err);
    updateStatus('停止錄影失敗', 'error');
  } finally {
    els.stopBtn.disabled = false;
  }
}

function shotBtnClickHandler() {
    if (BUTTON_TASKS.includes(id)) {
      startRecording();
      return;
    }
    takeShot(); 
}

els.shotBtn.addEventListener("click", shotBtnClickHandler);
if (els.stopBtn) {
  els.stopBtn.addEventListener("click", () => {
    if (BUTTON_TASKS.includes(id)) stopRecording();
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  cameraSetting = await loadCameraSetting();
  await openCamera();
});

// ✅ 新的寫法 (消除警告，且更穩定)
window.addEventListener("pagehide", () => {
  // 1. 清除計時器
  if (streamInterval) clearInterval(streamInterval);
  if (gameStateInterval) clearInterval(gameStateInterval);

  // 2. 如果相機還開著，通知後端關閉
  // 使用 sendBeacon 是因為頁面關閉時，一般的 fetch/await 容易被瀏覽器取消
  if (cameraActive) {
      // 這裡不需要 async/await，sendBeacon 是發後不理的
      navigator.sendBeacon('/opencv-camera/stop');
  }
});