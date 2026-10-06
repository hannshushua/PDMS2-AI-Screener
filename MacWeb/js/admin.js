// admin.js (權限分離版：Level 2 個資 / Level 3 成績)
(function () {
  const state = {
    userLevel: 0, 
    currentUid: '',
    currentName: '',
    rows: [],
    usersList: [],
    sortKey: 'test_date',
    sortAsc: false,
    selUserId: '',
    selLevel: '',
    allLevels: []
  };

  const $tbody = document.getElementById('tbody');
  const $selName = document.getElementById('sel-name');
  const $selLvl = document.getElementById('sel-level');
  
  // Dialog 相關元素
  const $dialog = document.getElementById('edit-dialog');
  const $f_userId = $dialog.querySelector('[data-field="userId"]');
  const $f_name = $dialog.querySelector('[data-field="name"]');
  const $f_level = $dialog.querySelector('[data-field="level"]');
  const $f_score = $dialog.querySelector('[data-field="score"]');
  const $f_scoreText = $dialog.querySelector('[data-field="score-text"]');
  const $f_testDate = $dialog.querySelector('[data-field="test_date"]');
  const $scoreSection = document.getElementById('score-fields');
  
  let editingRowKey = null;

  async function init() {
    try {
      const r = await fetch('/api/auth/whoami');
      const js = await r.json();
      if (!js.ok || !js.logged_in) { alert("請先登入"); window.location.href = '/'; return; }

      const user = js.user;
      state.currentUid = user.account;
      state.userLevel = parseInt(user.level) || 0;
      state.currentName = user.name || user.account;

      let roleName = '家長';
      if (state.userLevel === 2) roleName = '管理員';
      if (state.userLevel >= 3) roleName = '超級管理員';

      const infoEl = document.getElementById('current-user-info');
      if(infoEl) infoEl.textContent = `目前登入: ${state.currentName} (${roleName})`;

      // === 設定權限 Class ===
      document.body.classList.remove('is-admin', 'is-super-admin');
      
      // Level 2 以上 (包含 Level 3) 視為 Admin
      if (state.userLevel >= 2) {
        document.body.classList.add('is-admin');
      }
      
      // Level 3 以上視為 Super Admin
      if (state.userLevel >= 3) {
        document.body.classList.add('is-super-admin');
      }

      await loadData();
      // 只有管理員需要載入使用者清單
      if (state.userLevel >= 2) await loadAllUsers();
      
      rebuildSelects();
      
      if (state.userLevel === 1) {
        state.selUserId = state.currentUid;
        $selName.value = state.currentUid;
        $selName.disabled = true;
      }
      render();

    } catch (e) {
      console.error('Init failed', e);
      alert('初始化失敗，請檢查後端連線');
    }
  }

  async function loadAllUsers() {
      try {
          const r = await fetch('/users');
          const js = await r.json();
          if (js.ok) state.usersList = js.users;
      } catch (e) { console.warn("載入使用者名單失敗", e); }
  }

  async function loadData() {
    const $loading = document.getElementById('tbody');
    if ($loading) $loading.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:20px">資料讀取中...</td></tr>';

    try {
      let payload = {};
      if (state.userLevel === 1) payload.uid = state.currentUid;

      const r = await fetch('/api/search-scores', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const js = await r.json();
      if (js.success) {
        state.rows = js.data;
        const lvlSet = new Set();
        state.rows.forEach(r => lvlSet.add(r.task_id));
        state.allLevels = Array.from(lvlSet).sort();
      } else {
        alert("資料載入錯誤: " + (js.error || '未知錯誤'));
        state.rows = [];
      }
    } catch (e) {
      console.warn('Load data error', e);
      state.rows = [];
    }
  }

  function rebuildSelects() {
    $selName.innerHTML = '';
    
    if (state.userLevel === 1) {
      const opt = document.createElement('option');
      opt.value = state.currentUid;
      opt.textContent = `${state.currentName} (${state.currentUid})`;
      opt.selected = true;
      $selName.appendChild(opt);
    } else {
      const def = document.createElement('option');
      def.value = '';
      def.textContent = '（所有小朋友）';
      $selName.appendChild(def);

      const sourceList = (state.usersList.length > 0) ? state.usersList : [];
      // 簡單的 dedupe 邏輯
      const uidMap = new Map();
      sourceList.forEach(u => uidMap.set(u.uid, u.name));
      state.rows.forEach(r => { if (!uidMap.has(r.uid)) uidMap.set(r.uid, r.name || r.uid); });

      Array.from(uidMap.keys()).sort().forEach(uid => {
          const opt = document.createElement('option');
          opt.value = uid;
          opt.textContent = uidMap.get(uid) || uid;
          $selName.appendChild(opt);
      });
    }

    $selLvl.innerHTML = '<option value="">（所有關卡）</option>';
    const standardLevels = ['Ch1-t1', 'Ch1-t2', 'Ch1-t3', 'Ch1-t4', 'Ch2-t1', 'Ch2-t2', 'Ch2-t3', 'Ch2-t4', 'Ch2-t5', 'Ch2-t6', 'Ch3-t1', 'Ch3-t2', 'Ch3-t3', 'Ch3-t4', 'Ch4-t1', 'Ch4-t2', 'Ch5-t1'];
    const levelsToShow = new Set([...standardLevels, ...state.allLevels]);
    Array.from(levelsToShow).sort().forEach(lvl => {
      const opt = document.createElement('option');
      opt.value = lvl;
      opt.textContent = lvl;
      $selLvl.appendChild(opt);
    });
  }

  function render() {
    let displayRows = state.rows.filter(r => {
      const matchUser = !state.selUserId || r.uid === state.selUserId;
      const matchLevel = !state.selLevel || r.task_id === state.selLevel;
      return matchUser && matchLevel;
    });

    displayRows.sort((a, b) => {
      let valA = a[state.sortKey] || '';
      let valB = b[state.sortKey] || '';
      if (state.sortKey === 'score') {
        valA = parseFloat(valA) || 0;
        valB = parseFloat(valB) || 0;
      }
      if (valA < valB) return state.sortAsc ? -1 : 1;
      if (valA > valB) return state.sortAsc ? 1 : -1;
      return 0;
    });

    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
        if (th.dataset.sort === state.sortKey) {
            th.classList.add(state.sortAsc ? 'sort-asc' : 'sort-desc');
        }
    });

    if (displayRows.length === 0) {
      $tbody.innerHTML = `<tr><td colspan="8" class="empty">沒有符合的資料</td></tr>`;
      return;
    }

    $tbody.innerHTML = displayRows.map(r => {
      let imgCell = '<span class="muted" style="color:#ccc">無圖片</span>';
      if (r.result_img_path) {
          // DB 存的格式是 kid/{uid}/{filename}，需要轉換成 /images/{uid}/{filename}
          let thumbSrc = r.result_img_path;
          // 解析 kid/{uid}/{filename} → /images/{uid}/{filename}
          if (thumbSrc.startsWith('kid/')) {
              const parts = thumbSrc.split('/');
              if (parts.length >= 3) {
                  const uid = parts[1];
                  const filename = parts.slice(2).join('/');
                  thumbSrc = `/images/${uid}/${filename}`;
              }
          } else if (!thumbSrc.startsWith('/')) {
              thumbSrc = '/' + thumbSrc;
          }
          const linkUrl = r.compare_url || thumbSrc;
          imgCell = `
            <div style="display:flex; align-items:center; gap:10px;">
                <div style="width:40px; height:40px; background:#eee; border-radius:4px; overflow:hidden;">
                    <img src="${thumbSrc}" style="width:100%; height:100%; object-fit:cover;" onerror="this.style.display='none'">
                </div>
                <a href="${linkUrl}" target="_blank" class="btn btn-sm" style="text-decoration:none;">檢視</a>
            </div>
          `;
      }

      // ★★★ 只有 Level 3 (Super Admin) 才有刪除按鈕 ★★★
      let adminBtns = '';
      if (state.userLevel >= 3) {
        adminBtns = `
          <td class="admin-col">
             <button class="btn btn-sm btn-delete" onclick="deleteScore('${r.row_key}')">刪除</button>
          </td>
        `;
      } else if (state.userLevel === 2) {
         // Level 2 保留空白格，維持排版
         adminBtns = `<td class="admin-col"></td>`;
      } else {
         adminBtns = `<td class="admin-col"></td>`;
      }

      return `
        <tr>
          <td>${r.uid}</td>
          <td>${r.name || '—'}</td>
          <td>${r.task_name || r.task_id}</td>
          <td><span class="badge ${r.score === null ? 'gray' : ''}">${r.score !== null ? r.score : '—'}</span></td>
          <td>${r.test_date}</td>
          <td>${r.time || ''}</td>
          <td>${imgCell}</td>
          ${adminBtns}
        </tr>
      `;
    }).join('');
  }

  // ★★★ 全域事件監聽 ★★★
  document.addEventListener('click', e => {
      const target = e.target.closest('button');
      if (!target) return;
      const action = target.dataset.action;

      if (action === 'reset') {
          if (state.userLevel === 1) {
              state.selLevel = '';
              $selLvl.value = '';
          } else {
              state.selUserId = '';
              $selName.value = '';
              state.selLevel = '';
              $selLvl.value = '';
          }
          render();
      }
      
      // 新增紀錄 (只有 Super Admin 能觸發，HTML 已隱藏，這裡做雙重防護)
      else if (action === 'new') {
          if (state.userLevel < 3) { alert("權限不足"); return; }
          
          editingRowKey = null;
          $dialog.querySelector('.dlg-title').textContent = "新增測試紀錄";
          $scoreSection.style.display = 'block';
          
          $f_userId.value = state.selUserId || '';
          $f_name.value = '';
          $f_level.value = '';
          $f_score.value = 0;
          $f_scoreText.textContent = 0;
          $f_testDate.valueAsDate = new Date();
          
          $dialog.showModal();
      }

      // 管理使用者 (Admin & Super Admin 皆可)
      else if (action === 'manage-users') {
          if (state.userLevel < 2) return;

          editingRowKey = 'USER_MODE';
          $dialog.querySelector('.dlg-title').textContent = "管理使用者 (新增/修改)";
          $scoreSection.style.display = 'none';
          
          $f_userId.value = '';
          $f_name.value = '';
          $dialog.close();
          
          const uid = prompt("請輸入使用者的 UID (必填):", "");
          if (!uid) return;
          const name = prompt("請輸入使用者姓名:", "");
          const birth = prompt("請輸入生日 (格式: YYYY-MM-DD) 作為密碼:", "2020-01-01");
          
          if (uid && birth) {
              saveUser(uid, name, birth);
          }
      }

      else if (action === 'save') {
          e.preventDefault();
          const uid = $f_userId.value.trim();
          const name = $f_name.value.trim();
          if (!uid) { alert("UID 為必填"); return; }
          
          if (editingRowKey === null) {
              const level = $f_level.value.trim();
              const score = $f_score.value;
              const date = $f_testDate.value;
              
              if (!level) { alert("關卡代號為必填"); return; }
              saveScore(uid, name, level, score, date);
          }
      }
  });

  $dialog.addEventListener('close', () => {});
  $f_score.addEventListener('input', e => { $f_scoreText.textContent = e.target.value; });

  // --- API ---

  async function saveUser(uid, name, birthday) {
      try {
          const r = await fetch('/api/user/upsert', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ uid, name, birthday })
          });
          const js = await r.json();
          if (js.ok) {
              alert("使用者儲存成功！");
              await loadAllUsers();
              rebuildSelects();
          } else {
              alert("失敗: " + js.msg);
          }
      } catch (e) { alert("連線錯誤"); }
  }

  async function saveScore(uid, name, task_id, score, test_date) {
      try {
          // 如果有填姓名，Level 3 也可以順便更新個資
          if (name) {
              await fetch('/api/user/upsert', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ uid, name, birthday: null })
              });
          }

          const r = await fetch('/scores/upsert', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ uid, task_id, score, test_date })
          });
          
          const js = await r.json();
          if (js.ok) {
              alert("紀錄新增成功！");
              $dialog.close();
              await loadData();
              render();
          } else {
              alert("失敗: " + js.msg);
          }
      } catch (e) { console.error(e); alert("儲存失敗"); }
  }

  $selName.addEventListener('change', e => { state.selUserId = e.target.value; render(); });
  $selLvl.addEventListener('change', e => { state.selLevel = e.target.value; render(); });
  
  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (state.sortKey === key) state.sortAsc = !state.sortAsc;
      else { state.sortKey = key; state.sortAsc = true; }
      render();
    });
  });

  document.getElementById('btn-logout')?.addEventListener('click', async () => {
      if(confirm('確定要登出嗎？')) { await fetch('/api/auth/logout', { method: 'POST' }); window.location.href = '/'; }
  });

  window.deleteScore = async function(rowKey) {
      if(state.userLevel < 3) { alert("權限不足：只有超級管理員可以刪除"); return; }
      if(!confirm('確定要刪除這筆紀錄嗎？此動作無法復原。')) return;
      try {
          const r = await fetch(`/scores?row_key=${encodeURIComponent(rowKey)}`, { method: 'DELETE' });
          const js = await r.json();
          if(js.ok) { alert('刪除成功'); loadData().then(rebuildSelects).then(render); } else { alert('刪除失敗: ' + js.msg); }
      } catch(e) { console.error(e); alert('刪除失敗'); }
  };

  init();
})();