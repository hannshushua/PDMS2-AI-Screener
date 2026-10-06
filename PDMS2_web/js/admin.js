(function () {
  let userLevel = 0; 
  let taskList = []; // 存放從資料庫抓取的關卡清單

  async function ensureAuth() {
    try {
      const r = await fetch('/api/auth/whoami', { credentials: 'include' });
      const js = await r.json().catch(() => ({})); 
      if (!r.ok || !js.logged_in) {
        location.href = '/html/admin_login.html';
        return false;
      }
      userLevel = Number((js.user && js.user.level) || 0);
      if (userLevel < 3) document.getElementById('th-op')?.remove();
      if (userLevel < 2) {
        document.getElementById('th-manual')?.remove();
        document.getElementById('th-diff')?.remove();
      }

      // 按鈕文字隨身分調整：Level 2 開出來的是「新增受測者」，不是補登測驗成績
      const $btnAdd = document.getElementById('btn-add-record');
      if ($btnAdd) {
        const isL2 = userLevel === 2;
        $btnAdd.textContent = isL2 ? '新增受測者' : '新增紀錄';
        $btnAdd.title = isL2
          ? '建立一位新的受測者，並同步開通家長登入帳號（帳號為 UID、密碼為出生日期）'
          : '手動補登或修改一筆測驗紀錄';
      }

      const roleDisplay = document.getElementById('user-role-display');
      if (roleDisplay) {
        const userName = js.user.name || js.user.account;
        const labels = { 1: "家長身分", 2: "醫療人員", 3: "系統主管" };
        roleDisplay.innerHTML = `當前身分：${labels[userLevel] || '未確認'} ｜ 登入帳號：${userName}`;
      }
    } catch (e) {
      location.href = '/html/admin_login.html';
      return false;
    }
    
    if (userLevel < 2) {
      const addBtn = document.getElementById('btn-add-record');
      if (addBtn) addBtn.style.display = 'none';
      const changePwdBtn = document.getElementById('btn-change-pwd');
      if (changePwdBtn) changePwdBtn.style.display = '';

      // 家長身分：在 header 加「回到總覽」按鈕
      const userInfoDiv = document.querySelector('.user-info');
      if (userInfoDiv) {
        const backBtn = document.createElement('button');
        backBtn.className = 'text-link';
        backBtn.textContent = '← 回到總覽';
        backBtn.addEventListener('click', () => {
          location.href = '/html/parent_dashboard.html';
        });
        userInfoDiv.prepend(backBtn);
      }
    }

    if (userLevel >= 3) {
      // 主管身分：在 header 加「帳號管理」按鈕
      const userInfoDiv = document.querySelector('.user-info');
      if (userInfoDiv) {
        const mgmtBtn = document.createElement('button');
        mgmtBtn.className = 'text-link';
        mgmtBtn.textContent = '帳號管理';
        mgmtBtn.addEventListener('click', () => {
          location.href = '/html/superadmin.html';
        });
        userInfoDiv.prepend(mgmtBtn);
      }
    }
    return true;
  }

  document.getElementById('btn-logout')?.addEventListener('click', async () => {
    if (confirm('確定要登出系統嗎？')) {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
      location.href = '/html/admin_login.html';
    }
  });

  const PAGE_SIZE = 15;
  const state = { rows: [], users: [], sortKey: 'test_date', sortAsc: false, selUserId: '', selLevel: '', historyDate: '', currentPage: 1 };
  const $tbody = document.querySelector('[data-role="tbody"]');
  const $selName = document.querySelector('[data-role="sel-name"]');
  const $selLvl = document.querySelector('[data-role="sel-level"]');
  const $dialog = document.querySelector('[data-role="dialog"]');
  
  const $f_userId = $dialog?.querySelector('[data-field="userId"]');
  const $f_name = $dialog?.querySelector('[data-field="name"]');
  const $f_birthday = $dialog?.querySelector('[data-field="birthday"]');
  const $f_level = $dialog?.querySelector('[data-field="level"]');
  const $f_score = $dialog?.querySelector('[data-field="score"]');
  const $f_testDate = $dialog?.querySelector('[data-field="test_date"]');
  const $scoreDisplay = document.getElementById('score-display');

  if ($f_score && $scoreDisplay) {
    $f_score.addEventListener('input', () => { $scoreDisplay.textContent = $f_score.value; });
  }

  // 取得最新關卡清單
  async function reloadTasks() {
    try {
      const r = await fetch('/api/tasks', { credentials: 'include' });
      const js = await r.json();
      taskList = (js && js.ok) ? js.tasks : [];
    } catch (e) { console.error("關卡載入失敗", e); taskList = []; }
  }

  async function reloadScores() {
    try {
      const r = await fetch('/scores', { credentials: 'include' });
      state.rows = (await r.json()) || [];
      render();
    } catch (e) { console.error("資料載入失敗", e); }
  }

  async function reloadUsers() {
    try {
      const r = await fetch('/users', { credentials: 'include' });
      const js = await r.json();
      state.users = (js && js.ok) ? js.users : [];
      rebuildSelects();
    } catch { state.users = []; }
  }

  function rebuildSelects() {
    const optsU = ['<option value="">（請選擇受測者）</option>'];
    state.users.forEach(uid => optsU.push(`<option value="${uid}">${uid}</option>`));
    if ($selName) $selName.innerHTML = optsU.join('');

    // 使用動態抓取的關卡建立選項
    if ($selLvl) {
      const optsL = ['<option value="">（請選擇測驗項目）</option>'];
      taskList.forEach(t => optsL.push(`<option value="${t.task_id}">${t.task_id} (${t.task_name})</option>`));
      $selLvl.innerHTML = optsL.join('');
    }

    if ($f_level) {
      const optsDialog = ['<option value="">（僅建立基本資料請留空）</option>'];
      taskList.forEach(t => optsDialog.push(`<option value="${t.task_id}">${t.task_id} (${t.task_name})</option>`));
      $f_level.innerHTML = optsDialog.join('');
    }
  }

  // 人工分數減 AI 分數：0 為一致，差 1 分黃、差 2 分紅，任一邊缺值就不比
  function diffBadge(aiScore, manualScore) {
    if (manualScore === null || manualScore === undefined) return '<span class="diff-badge diff-na" title="尚未人工評分">—</span>';
    if (aiScore === null || aiScore === undefined || aiScore === -1) return '<span class="diff-badge diff-na" title="這次沒有有效的 AI 判讀結果">—</span>';
    const d = manualScore - aiScore;
    if (d === 0) return '<span class="diff-badge diff-same" title="AI 與人工評分一致">一致</span>';
    const cls = Math.abs(d) === 1 ? 'diff-1' : 'diff-2';
    return `<span class="diff-badge ${cls}" title="人工 ${manualScore} 分 − AI ${aiScore} 分">${d > 0 ? '+' : ''}${d}</span>`;
  }

  function render() {
    if (!$tbody) return;
    let filtered = state.rows.filter(r =>
      (!state.selUserId || r.uid === state.selUserId) &&
      (!state.selLevel || r.task_id === state.selLevel)
    );

    if (state.historyDate) {
      // 歷史模式：顯示指定日期所有紀錄，同一天按時間由新到舊
      filtered = filtered.filter(r => r.test_date === state.historyDate);
      filtered.sort((a, b) => { const ta = a.time || '', tb = b.time || ''; return tb > ta ? 1 : tb < ta ? -1 : 0; });
    } else {
      // 主視圖：列出每一次測驗，由新到舊（同一關測多次會全部列出）
      filtered.sort((a, b) => {
        const da = (a.test_date || '') + '|' + (a.time || '');
        const db = (b.test_date || '') + '|' + (b.time || '');
        return db > da ? 1 : db < da ? -1 : 0;
      });
    }

    const total = filtered.length;
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (state.currentPage > totalPages) state.currentPage = totalPages;
    const start = (state.currentPage - 1) * PAGE_SIZE;
    const paged = filtered.slice(start, start + PAGE_SIZE);

    const $count = document.getElementById('record-count');
    if ($count) $count.textContent = `共 ${total} 筆，第 ${state.currentPage} / ${totalPages} 頁`;

    const $pg = document.getElementById('pagination');
    if ($pg) {
      if (totalPages <= 1) {
        $pg.style.display = 'none';
      } else {
        $pg.style.display = 'flex';
        const pages = [];
        // 產生要顯示的頁碼：頭、尾、當前前後各一，其餘省略
        const show = new Set([1, totalPages, state.currentPage, state.currentPage - 1, state.currentPage + 1].filter(p => p >= 1 && p <= totalPages));
        const sorted = [...show].sort((a, b) => a - b);
        let html = `<button class="page-btn" ${state.currentPage === 1 ? 'disabled' : ''} data-pg="${state.currentPage - 1}">←</button>`;
        sorted.forEach((p, i) => {
          if (i > 0 && p - sorted[i - 1] > 1) html += `<span class="page-info">…</span>`;
          html += `<button class="page-btn ${p === state.currentPage ? 'active' : ''}" data-pg="${p}">${p}</button>`;
        });
        html += `<button class="page-btn" ${state.currentPage === totalPages ? 'disabled' : ''} data-pg="${state.currentPage + 1}">→</button>`;
        $pg.innerHTML = html;
      }
    }

    const colCount = userLevel === 3 ? 10 : (userLevel === 2 ? 9 : 7);
    if (total === 0) {
      $tbody.innerHTML = `<tr><td colspan="${colCount}" class="empty">${state.historyDate ? '這天沒有測驗紀錄' : '目前沒有符合條件的測驗紀錄'}</td></tr>`;
      return;
    }

    $tbody.innerHTML = paged.map(r => {
      const dateDisplay = r.test_date || '';
      const timeDisplay = r.time || '—';

      const opTd = (userLevel === 3)
        ? `<td data-label="操作區塊"><div style="display:flex; gap:8px;">
             <button class="btn btn-sm" data-action="edit">編輯</button>
             <button class="btn btn-sm danger" data-action="del">刪除</button>
           </div></td>`
        : '';

      const sv = r.score;
      const isVideo = /\.mp4$/i.test(r.result_img_path || '');
      const scoreCell = (sv === null || sv === undefined)
        ? (isVideo
            ? '<span class="score-badge score-na" title="影片已上傳，等待人工評分">待評分</span>'
            : '<span class="score-badge score-na" title="尚未測驗">—</span>')
        : sv === -1 ? '<span class="score-badge score-na" title="AI 分析失敗（例如找不到紙張），請重拍或人工評分">分析失敗</span>'
        : sv === 0 ? '<span class="score-badge score-0" title="0 分：未達標準">0</span>'
        : sv === 1 ? '<span class="score-badge score-1" title="1 分：部分達標">1</span>'
        :            '<span class="score-badge score-2" title="2 分：完全達標">2</span>';

      const mv = r.manual_score;
      const scoreHref = `/manual-score?rk=${encodeURIComponent(r.row_key)}`;
      const manualCell = (userLevel >= 2)
        ? `<td data-label="人工評分">${(mv === null || mv === undefined)
            ? `<a class="btn-view" href="${scoreHref}" target="_blank" title="開啟人工評分頁：只顯示原始照片，不顯示 AI 判讀結果">✎ 人工評分</a>`
            : `<a class="score-badge score-${mv}" href="${scoreHref}" target="_blank" style="text-decoration:none;" title="人工評分 ${mv} 分，評分者 ${r.manual_rater || '—'}（點擊可改分）">${mv}</a>`}</td>`
        : '';

      const diffCell = (userLevel >= 2)
        ? `<td data-label="差異">${diffBadge(sv, mv)}</td>`
        : '';

      const imgCell = (r.compare_url || r.result_img_url)
        ? `<a href="${r.compare_url || r.result_img_url}" target="_blank" class="btn-view" title="開新分頁檢視這次測驗的原圖與 AI 判讀結果對比">${isVideo ? '播放影片' : '🔍 檢視結果'}</a>`
        : '<span class="no-perm" title="這次測驗沒有留下結果圖">尚無圖片</span>';

      return `
        <tr data-key="${r.row_key}" data-uid="${r.uid}" data-name="${r.name || ''}">
          ${opTd}
          <td data-label="受測者編號" style="font-weight:700; color:#5C4E4E;">${r.uid}</td>
          <td data-label="受測者姓名">${r.name || '—'}</td>
          <td data-label="測驗項目" style="font-weight:700;">${r.task_id || ''}</td>
          <td data-label="AI 評分">${scoreCell}</td>
          ${manualCell}
          ${diffCell}
          <td data-label="測驗日期" style="font-weight:600; color:#7A6060;">${dateDisplay}</td>
          <td data-label="測驗時間" style="font-weight:600; color:#7A6060; font-variant-numeric:tabular-nums;">${timeDisplay}</td>
          <td data-label="圖片檢視">${imgCell}</td>
        </tr>`;
    }).join('');
  }

  document.getElementById('pagination')?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-pg]');
    if (!btn || btn.disabled) return;
    state.currentPage = Number(btn.dataset.pg);
    render();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const act = btn.dataset.action;

    if (act === 'new') {
      const taskFields = document.getElementById('task-fields');
      const bdayGroup = document.getElementById('group-birthday');
      const title = document.getElementById('dialog-title');
      
      if (bdayGroup) bdayGroup.style.display = 'block'; 
      
      const isL2 = (userLevel === 2);
      if (taskFields) taskFields.style.display = isL2 ? 'none' : 'block';
      if (title) title.textContent = isL2 ? '新增受測者資料' : '新增測驗紀錄';

      $f_userId.value = ''; $f_name.value = ''; $f_userId.disabled = false;
      if ($f_birthday) $f_birthday.value = '';
      if ($f_level) $f_level.value = '';
      
      // ✅ 預設改回 -1
      if ($f_score) { $f_score.value = '-1'; $scoreDisplay.textContent = '-1'; }
      if ($f_testDate) $f_testDate.value = new Date().toISOString().split('T')[0];

      $dialog.showModal();
      $dialog.dataset.mode = 'create';
    }

    if (act === 'save') {
      e.preventDefault();
      const uid = $f_userId.value.trim();
      const task_id = $f_level ? $f_level.value : '';
      if (!uid) return alert('系統提示：請務必填寫受測者編號 (UID)');


      // 送出前確認：uid 是主鍵又連著家長帳號，打錯事後幾乎救不回來
      if (userLevel === 2) {
        const nameVal = $f_name.value.trim();
        const bdVal = $f_birthday?.value || '';
        let info = { exists: false };
        try {
          const lr = await fetch('/api/user/lookup?uid=' + encodeURIComponent(uid), { credentials: 'include' });
          info = await lr.json().catch(() => ({ exists: false }));
        } catch (err) { info = { exists: false }; }

        const lines = [
          '請確認以下資料無誤：', '',
          '受測者編號：' + uid,
          '姓名：' + (nameVal || '(未填)'),
          '出生日期：' + (bdVal || '(未填)'), ''
        ];
        if (info.exists) {
          lines.push('【注意】這個編號已經有資料，送出會覆蓋成上面的內容。');
          lines.push('原姓名：' + (info.name || '(空白)'));
          lines.push('原出生日期：' + (info.birthday || '(空白)'));
          if (bdVal && info.birthday && bdVal !== info.birthday) {
            lines.push('');
            lines.push('出生日期有異動，家長的登入密碼會一併改成新的出生日期。');
          }
        } else {
          lines.push('這個編號目前不存在，送出會建立一位新的受測者。');
          lines.push('編號送出後無法修改，請再確認一次是否正確。');
        }
        if (!confirm(lines.join('\n'))) return;
      }
      const btnSave = e.target;
      const originalText = btnSave.textContent;
      btnSave.textContent = '資料處理中...';
      btnSave.disabled = true;

      try {
        let js;
        if (userLevel === 2 || (userLevel === 3 && !task_id)) {
          const r = await fetch('/api/user/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid, name: $f_name.value, birthday: $f_birthday?.value || '' })
          });
          js = await r.json().catch(() => ({}));
        } 
        else if (userLevel === 3 && task_id) {
          if ($dialog.dataset.mode === 'create' && $f_birthday?.value) {
            await fetch('/api/user/add', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ uid, name: $f_name.value, birthday: $f_birthday.value })
            });
          }
          const payload = { uid, task_id, score: Number($f_score.value), test_date: $f_testDate.value };
          if ($dialog.dataset.mode === 'edit') payload.row_key_old = $dialog.dataset.key;
          
          const r = await fetch('/scores/upsert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          js = await r.json().catch(() => ({}));
        }
        
        if (js.ok) {
          $dialog.close();
          await reloadUsers(); await reloadScores();
        } else {
          alert('作業無法完成：' + (js.msg || js.err || '未知的系統狀態'));
        }
      } catch (err) { 
        alert('網路連線異常，請檢查網路狀態後再試。'); 
      } finally {
        btnSave.textContent = originalText;
        btnSave.disabled = false;
      }
    }

    if (act === 'edit' && userLevel === 3) {
      const row = state.rows.find(x => x.row_key === btn.closest('tr').dataset.key);
      if (row) {
        document.getElementById('task-fields').style.display = 'block';
        const bdayGroup = document.getElementById('group-birthday');
        if (bdayGroup) bdayGroup.style.display = 'none';

        $f_userId.value = row.uid; $f_userId.disabled = true;
        $f_name.value = row.name || '';
        $f_level.value = row.task_id || '';
        
        // ✅ 編輯時若沒有分數，預設為 -1
        $f_score.value = row.score ?? -1; $scoreDisplay.textContent = row.score ?? -1;
        $f_testDate.value = (row.test_date || '').slice(0, 10);
        
        document.getElementById('dialog-title').textContent = '編輯測驗紀錄';
        $dialog.showModal(); 
        $dialog.dataset.mode = 'edit'; 
        $dialog.dataset.key = row.row_key;
      }
    }
    
    if (act === 'del' && userLevel === 3) {
      if (confirm('重要提醒：確定要刪除這筆測驗紀錄嗎？刪除後將無法復原。')) {
        const r = await fetch(`/scores?row_key=${btn.closest('tr').dataset.key}`, { method: 'DELETE' });
        if (r.ok) reloadScores();
      }
    }

    if (act === 'clear-filter') {
      state.selUserId = ''; state.selLevel = ''; state.currentPage = 1;
      if ($selName) $selName.value = '';
      if ($selLvl) $selLvl.value = '';
      render();
    }
  });

  if ($selName) $selName.addEventListener('change', () => { 
    state.selUserId = $selName.value; 
    state.currentPage = 1; 
    render(); 
    
    // 顯示/隱藏 AI 建議按鈕
    const aiBtn = document.getElementById('btn-ai-advice');
    if (aiBtn) {
      aiBtn.style.display = state.selUserId ? 'inline-block' : 'none';
    }
  });

  document.getElementById('btn-ai-advice')?.addEventListener('click', async () => {
    if (!state.selUserId) return;
    const dialog = document.getElementById('ai-advice-dialog');
    const content = document.getElementById('ai-advice-content');
    
    dialog.showModal();
    content.innerHTML = `
      <div style="text-align: center; padding: 40px;">
        <div style="margin-bottom: 20px; font-size: 40px;">🤖</div>
        <div>正在與 AI 專家連線，分析 ${state.selUserId} 的表現並生成建議...</div>
      </div>
    `;
    
    try {
      console.log("[AI] Requesting advice for:", state.selUserId);
      const r = await fetch(`/api/ai_advice/${state.selUserId}`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`);
      const js = await r.json();
      if (js.ok) {
        content.innerHTML = `<div class="markdown-body">${marked.parse(js.advice)}</div>`;
      } else {
        content.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 40px;">❌ 產生建議失敗：${js.msg || '未知錯誤'}</div>`;
      }
    } catch (e) {
      console.error("[AI] Error:", e);
      content.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 40px;">❌ 連線失敗，請檢查網路狀況。</div>`;
    }
  });
  if ($selLvl) $selLvl.addEventListener('change', () => { state.selLevel = $selLvl.value; state.currentPage = 1; render(); });

  const $selDate = document.getElementById('sel-date');
  const $btnClearHistory = document.getElementById('btn-clear-history');
  const $historyBadge = document.getElementById('history-badge');

  function setHistoryMode(date) {
    state.historyDate = date; state.currentPage = 1;
    const on = !!date;
    if ($btnClearHistory) $btnClearHistory.style.display = on ? '' : 'none';
    if ($historyBadge) $historyBadge.style.display = on ? '' : 'none';
    render();
  }

  if ($selDate) $selDate.addEventListener('change', () => setHistoryMode($selDate.value));
  if ($btnClearHistory) $btnClearHistory.addEventListener('click', () => {
    if ($selDate) $selDate.value = '';
    setHistoryMode('');
  });

  (async function init() {
    if (await ensureAuth()) {
      await reloadTasks();
      await reloadUsers();
      await reloadScores();

      // SSE 即時推播：有新分數就自動刷新
      function connectSSE() {
        const es = new EventSource('/events');
        es.addEventListener('score-updated', () => reloadScores());
        es.onerror = () => { es.close(); setTimeout(connectSSE, 5000); };
      }
      connectSSE();

      // 跨機器情境（例如在 Mac 拍照、這台看畫面）收不到 SSE，
      // 改用輕量版本戳記輪詢：有變動才去重抓較重的 /scores。
      let lastVersion = null;
      let checking = false;
      async function checkVersion() {
        if (checking) return;
        checking = true;
        try {
          const r = await fetch('/scores/version', { credentials: 'include' });
          const js = await r.json();
          if (js.ok) {
            if (lastVersion !== null && js.version !== lastVersion) await reloadScores();
            lastVersion = js.version;
          }
        } catch (e) {
          console.error("版本檢查失敗", e);
        } finally {
          checking = false;
        }
      }
      setInterval(checkVersion, 4000);
    }
  })();
})();