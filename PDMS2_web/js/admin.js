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
      // 主視圖：每個 uid+task_id 只保留最新一筆
      const map = new Map();
      filtered.forEach(r => {
        const key = r.uid + '|' + r.task_id;
        const cur = map.get(key);
        if (!cur) { map.set(key, r); return; }
        const a = (cur.test_date || '') + '|' + (cur.time || '');
        const b = (r.test_date || '') + '|' + (r.time || '');
        if (b > a) map.set(key, r);
      });
      filtered = [...map.values()];
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

    const colCount = userLevel === 3 ? 7 : 6;
    if (total === 0) {
      $tbody.innerHTML = `<tr><td colspan="${colCount}" class="empty">${state.historyDate ? '這天沒有測驗紀錄' : '目前沒有符合條件的測驗紀錄'}</td></tr>`;
      return;
    }

    $tbody.innerHTML = paged.map(r => {
      const dateDisplay = state.historyDate
        ? `${r.test_date || ''} ${r.time || ''}`.trim()
        : (r.test_date ?? '');

      const opTd = (userLevel === 3)
        ? `<td><div style="display:flex; gap:8px;">
             <button class="btn btn-sm" data-action="edit">編輯</button>
             <button class="btn btn-sm danger" data-action="del">刪除</button>
           </div></td>`
        : '';

      const sv = r.score;
      const scoreCell = (sv === null || sv === undefined || sv === -1)
        ? '<span class="score-badge score-na">—</span>'
        : sv === 0 ? '<span class="score-badge score-0">0</span>'
        : sv === 1 ? '<span class="score-badge score-1">1</span>'
        :            '<span class="score-badge score-2">2</span>';

      const imgCell = (r.compare_url || r.result_img_url)
        ? `<a href="${r.compare_url || r.result_img_url}" target="_blank" class="btn-view">🔍 檢視結果</a>`
        : '<span class="no-perm">尚無圖片</span>';

      return `
        <tr data-key="${r.row_key}" data-uid="${r.uid}" data-name="${r.name || ''}">
          ${opTd}
          <td style="font-weight:700; color:#5C4E4E; cursor:pointer; text-decoration:underline dotted #FFBF80;" data-action="show-chart">${r.uid}</td>
          <td>${r.name || '—'}</td>
          <td style="font-weight:700;">${r.task_id || ''}</td>
          <td>${scoreCell}</td>
          <td style="font-weight:600; color:#7A6060;">${dateDisplay}</td>
          <td>${imgCell}</td>
        </tr>`;
    }).join('');
  }

  // ── 進度圖 ──────────────────────────────────────────────────────────────────
  let _chartInstance = null;

  function openProgressChart(uid, name) {
    // 從 state.rows 拿出該 UID 全部歷史（未去重）
    const uidRows = state.rows.filter(r => r.uid === uid);

    // 每個 task_id 只取最新一筆（date|time 最大）
    const latestMap = new Map();
    uidRows.forEach(r => {
      const key = r.task_id;
      const ts = (r.test_date || '') + '|' + (r.time || '');
      const cur = latestMap.get(key);
      if (!cur || ts > (cur.test_date || '') + '|' + (cur.time || '')) latestMap.set(key, r);
    });

    // 按 task_id 排序（Ch1-t1 < Ch1-t2 < ... < Ch5-t1）
    const sorted = [...latestMap.values()].sort((a, b) => a.task_id < b.task_id ? -1 : 1);
    const labels = sorted.map(r => r.task_id);
    const scores = sorted.map(r => (r.score === null || r.score === undefined || r.score === -1) ? null : r.score);

    const colors = scores.map(s =>
      s === null ? '#D8D0C8'
      : s === 0  ? '#FF8FA3'
      : s === 1  ? '#FFD166'
      :             '#4ECBA8'
    );

    document.getElementById('chart-title').textContent = `${uid}（${name || '—'}）測驗進度`;
    const dialog = document.getElementById('chart-dialog');
    dialog.showModal();

    if (_chartInstance) { _chartInstance.destroy(); _chartInstance = null; }

    _chartInstance = new Chart(document.getElementById('progress-chart'), {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: '最新分數',
          data: scores,
          borderColor: '#FF9F43',
          borderWidth: 3,
          pointBackgroundColor: colors,
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          pointRadius: 8,
          pointHoverRadius: 11,
          tension: 0.35,
          fill: true,
          backgroundColor: 'rgba(255, 159, 67, 0.08)',
          spanGaps: true,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => ctx.raw === null ? '尚未測驗' : `分數：${ctx.raw}`
            }
          }
        },
        scales: {
          y: {
            min: 0, max: 2,
            ticks: { stepSize: 1, font: { size: 14 } },
            grid: { color: '#F0E6D2' }
          },
          x: {
            ticks: { font: { size: 13 }, maxRotation: 45 },
            grid: { color: '#F9F6F0' }
          }
        }
      }
    });
  }

  document.getElementById('chart-dialog')?.addEventListener('close', () => {
    if (_chartInstance) { _chartInstance.destroy(); _chartInstance = null; }
  });

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

    if (act === 'show-chart') {
      const tr = btn.closest('tr');
      openProgressChart(tr.dataset.uid, tr.dataset.name);
      return;
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
      const r = await fetch(`/api/ai_advice/${state.selUserId}`, { credentials: 'include' });
      const js = await r.json();
      if (js.ok) {
        content.innerHTML = `<div class="markdown-body">${marked.parse(js.advice)}</div>`;
      } else {
        content.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 40px;">❌ 產生建議失敗：${js.msg || '未知錯誤'}</div>`;
      }
    } catch (e) {
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
      // 保留 60 秒保底輪詢，以防 SSE 連線中斷後靜默失敗
      setInterval(reloadScores, 60 * 1000);
    }
  })();
})();