// 目標故事首頁；若你的檔案不在 /html/index.html，改這行即可
const STORY_HOME = "/html/index.html";

(function () {
  const btn = document.getElementById("enterBtn");
  const uidInput = document.getElementById("uid");
  if (!btn || !uidInput) return;

  const go = async () => {
    const uid = uidInput.value.trim();
    
    // 檢查UID是否為空
    if (!uid) {
      alert("請輸入有效的UID");
      uidInput.focus();
      return;
    }

    // 點擊的微動畫
    btn.style.transform = "scale(0.98)";
    btn.disabled = true;
    btn.textContent = "創建中...";

        try {
      // ⭐ 先送 request 到後端 /create-uid-folder
      const response = await fetch("/create-uid-folder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uid }),
      });

      // ⭐ 再把 response 轉成 JSON
      const result = await response.json();

      if (result.success) {
        // UID 已由後端存入 session，同時備份到 localStorage
        const META_KEY = "kid-quest-progress-v1-meta";
        const st = JSON.parse(localStorage.getItem(META_KEY) || "{}");
        st.currentUid = uid;
        localStorage.setItem(META_KEY, JSON.stringify(st));

        // 成功建立/載入 UID，跳轉到故事首頁
        setTimeout(() => {
          window.location.href = STORY_HOME;
        }, 180);

      } else {
        // ⭐ 專門處理 UID 不存在
        if (result.code === "USER_NOT_FOUND") {
          alert("此使用者不存在，請聯絡管理者新增帳號");
        } else {
          alert(`錯誤: ${result.error}`);
        }

        btn.disabled = false;
        btn.textContent = "進入故事";
        btn.style.transform = "";
      }

    } catch (error) {
      console.error("建立資料夾時發生錯誤:", error);

      const msg = (error && error.message) ? error.message : String(error);
      alert("建立資料夾時發生錯誤：" + msg);

      btn.disabled = false;
      btn.textContent = "進入故事";
      btn.style.transform = "";
    }

  };

  btn.addEventListener("click", go);
  
  // 按Enter鍵也能觸發
  uidInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      go();
    }
  });

  // 全域按Enter或空白鍵
  window.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { 
      e.preventDefault(); 
      go(); 
    }
  });
})();
