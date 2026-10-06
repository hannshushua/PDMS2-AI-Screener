// superadmin.js — 主管介面（醫療人員管理）
(async function () {
  let userLevel = 0;
  const $tbody = document.querySelector('[data-role="tbody"]');

  // === 驗證登入 ===
  async function ensureAuth() {
    const r = await fetch('/api/auth/whoami');
    const js = await r.json();
    if (!js.ok || !js.logged_in) {
      alert('尚未登入');
      location.href = '/html/login.html';
      return false;
    }
    userLevel = Number(js.user.level || 0);
    if (userLevel < 3) {
      alert('⚠️ 只有主管可以進入此頁面');
      location.href = '/html/admin.html';
      return false;
    }
    return true;
  }

  // === 抓清單 ===
  async function loadAdmins() {
    const res = await fetch('/api/admin/list');
    const js = await res.json();
    if (!js.ok) {
      $tbody.innerHTML = `<tr><td colspan="4">讀取失敗：${js.msg}</td></tr>`;
      return;
    }
    render(js.admins || []);
  }

  // === 畫表格 ===
  function render(list) {
    if (!list.length) {
      $tbody.innerHTML = '<tr><td colspan="3">目前沒有醫療人員</td></tr>';
      return;
    }
    $tbody.innerHTML = list.map(a => `
      <tr data-id="${a.account}">
        <td>${a.account}</td>
        <td>${a.name || a.account}</td>
        <td>
          <button class="btn" data-action="edit">✏️ 修改</button>
          <button class="btn btn-del" data-action="del">🗑️ 刪除</button>
        </td>
      </tr>
    `).join('');
  }

  // === 按鈕事件 ===
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const tr = btn.closest('tr');
    const id = tr?.dataset.id;

    // 新增
    if (btn.dataset.action === 'add') {
      const account = prompt('輸入帳號：');
      const password = prompt('輸入密碼（預設 123456）：') || '123456';
      const email = prompt('輸入 Email（可留空）：') || '';
      if (!account) return alert('❌ 帳號不可空白');
      const res = await fetch('/api/admin/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account, password, email })
      });
      const js = await res.json();
      alert(js.ok ? '✅ 新增成功' : `❌ 失敗：${js.msg}`);
      await loadAdmins();
      return;
    }

    // 修改
    if (btn.dataset.action === 'edit') {
      const newAccount = prompt('輸入新帳號：', tr.children[0].textContent);
      const newEmail = prompt('輸入新 Email：', '');
      const newPassword = prompt('輸入新密碼（留空不改）：', '');
      if (!newAccount) return alert('❌ 帳號不可空白');
      const res = await fetch(`/api/admin/update/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account: newAccount, email: newEmail, password: newPassword })
      });
      const js = await res.json();
      alert(js.ok ? '✅ 修改成功' : `❌ 失敗：${js.msg}`);
      await loadAdmins();
      return;
    }

    // 刪除
    if (btn.dataset.action === 'del') {
      if (!confirm(`確定要刪除帳號「${id}」嗎？`)) return;
      const res = await fetch(`/api/admin/delete/${id}`, { method: 'DELETE' });
      const js = await res.json();
      alert(js.ok ? '🗑️ 已刪除' : `❌ 失敗：${js.msg}`);
      await loadAdmins();
    }
  });

  // === 工具列按鈕 ===
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    if (btn.dataset.action === 'reload') await loadAdmins();
  });

  // === 初始化 ===
  const ok = await ensureAuth();
  if (ok) await loadAdmins();
})();
