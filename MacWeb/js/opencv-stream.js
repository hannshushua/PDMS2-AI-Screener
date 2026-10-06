// OpenCV 攝影機串流控制
let streamActive = false;
let streamInterval = null;

function startOpenCVStream() {
    if (streamActive) return;
    
    // 啟動攝影機
    fetch('/opencv-camera/start', {
        method: 'POST'
    }).then(response => response.json())
    .then(data => {
        if (data.success) {
            streamActive = true;
            const streamImg = document.getElementById('opencvStream');
            streamImg.style.display = 'block';
            
            // 開始定期更新畫面
            streamInterval = setInterval(() => {
                if (streamActive) {
                    streamImg.src = `/opencv-camera/frame?t=${Date.now()}`;
                }
            }, 100); // 每 100ms 更新一次
        }
    }).catch(err => console.error('啟動攝影機失敗:', err));
}

function stopOpenCVStream() {
    if (!streamActive) return;
    
    // 停止攝影機
    fetch('/opencv-camera/stop', {
        method: 'POST'
    }).then(response => response.json())
    .then(data => {
        streamActive = false;
        if (streamInterval) {
            clearInterval(streamInterval);
            streamInterval = null;
        }
        const streamImg = document.getElementById('opencvStream');
        streamImg.style.display = 'none';
    }).catch(err => console.error('停止攝影機失敗:', err));
}

// 在頁面載入時自動啟動攝影機 (如果是 Ch5-t1)
document.addEventListener('DOMContentLoaded', () => {
    const taskId = new URLSearchParams(window.location.search).get('task');
    if (taskId === 'Ch5-t1') {
        document.getElementById('opencvStream').style.display = 'block';
        startOpenCVStream();
    }
});

// 在頁面關閉時停止攝影機
window.addEventListener('beforeunload', () => {
    stopOpenCVStream();
});