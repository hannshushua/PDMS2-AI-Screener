// custom-scrollbar.js — 自繪捲軸（觸控螢幕友善：粗軌道、短握把、大熱區）
// 用法：在頁面底部加 <script src="/js/custom-scrollbar.js"></script> 即可。
// 會自動接管「整頁捲動」以及頁面內任何夠大的捲動區塊（例如 task.html 的步驟欄）。
// 顏色自動沿用該頁既有的主色變數（--accent → --primary → 預設橘）。
(function () {
  'use strict';

  const TRACK_WIDTH = 60;   // 軌道寬度，同時是觸控熱區（外接觸控螢幕要夠大才按得到）
  const THUMB_WIDTH = 38;   // 握把可見寬度
  const THUMB_MIN = 90;     // 握把最短長度
  const THUMB_MAX = 200;    // 握把最長長度（原生捲軸給不了的上限）
  const EDGE_GAP = 10;      // 離捲動區右緣與上下的留白，別太貼邊否則不好按
  const MIN_AREA_H = 150;   // 捲動區至少要這麼高才掛捲軸，避免小方塊也長出一條

  const style = document.createElement('style');
  style.textContent = `
    html { scrollbar-width: none; }
    html::-webkit-scrollbar { width: 0; height: 0; }
    .cscroll-host { scrollbar-width: none; }
    .cscroll-host::-webkit-scrollbar { width: 0; height: 0; }
    .cscroll-track {
      position: fixed;
      width: ${TRACK_WIDTH}px;
      z-index: 2147483000;
      display: flex;
      justify-content: center;
      touch-action: none;
      opacity: 0;
      transition: opacity .18s ease;
      pointer-events: none;
    }
    .cscroll-track.is-visible { opacity: 1; pointer-events: auto; }
    /* 掛圖風格：方角、墨框、握把用目前關卡色 */
    .cscroll-rail {
      box-sizing: border-box;
      width: ${THUMB_WIDTH}px;
      height: 100%;
      border: 3px solid var(--ink, #1D1C1A);
      background: var(--paper-dim, #EDECE6);
    }
    .cscroll-thumb {
      box-sizing: border-box;
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
      width: ${THUMB_WIDTH}px;
      border: 3px solid var(--ink, #1D1C1A);
      border-radius: 4px;
      background: var(--accent, var(--primary, #1D1C1A));
      cursor: grab;
      transition: width .12s ease;
    }
    .cscroll-track.is-dragging .cscroll-thumb {
      width: ${THUMB_WIDTH + 6}px;
      cursor: grabbing;
    }
  `;
  document.head.appendChild(style);

  const bars = new Map();

  function createBar(scroller) {
    const isPage = scroller === document.documentElement;
    const track = document.createElement('div');
    track.className = 'cscroll-track';
    const rail = document.createElement('div');
    rail.className = 'cscroll-rail';
    const thumb = document.createElement('div');
    thumb.className = 'cscroll-thumb';
    track.append(rail, thumb);
    document.body.appendChild(track);
    if (!isPage) scroller.classList.add('cscroll-host');

    let thumbH = THUMB_MIN;
    let trackH = 0;

    function maxScroll() {
      return scroller.scrollHeight - scroller.clientHeight;
    }

    function update() {
      const max = maxScroll();
      if (max <= 1) {
        track.classList.remove('is-visible');
        return;
      }
      // 把軌道對齊到捲動區的可視範圍（整頁就是整個視窗）
      const r = isPage
        ? { top: 0, right: window.innerWidth, height: document.documentElement.clientHeight }
        : scroller.getBoundingClientRect();
      track.style.top = (r.top + EDGE_GAP) + 'px';
      track.style.left = (r.right - TRACK_WIDTH - EDGE_GAP) + 'px';
      trackH = r.height - EDGE_GAP * 2;
      track.style.height = trackH + 'px';

      track.classList.add('is-visible');

      const ratio = scroller.clientHeight / scroller.scrollHeight;
      thumbH = Math.min(THUMB_MAX, Math.max(THUMB_MIN, trackH * ratio));
      thumb.style.height = thumbH + 'px';
      thumb.style.top = (scroller.scrollTop / max) * (trackH - thumbH) + 'px';
    }

    // 依指標在軌道上的位置換算成該捲到哪
    function scrollToPointer(clientY, grabOffset) {
      const travel = trackH - thumbH;
      if (travel <= 0) return;
      const top = clientY - track.getBoundingClientRect().top - grabOffset;
      const progress = Math.min(1, Math.max(0, top / travel));
      scroller.scrollTop = progress * maxScroll();
    }

    thumb.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const grabOffset = e.clientY - thumb.getBoundingClientRect().top;
      track.classList.add('is-dragging');
      thumb.setPointerCapture(e.pointerId);

      const onMove = (ev) => scrollToPointer(ev.clientY, grabOffset);
      const onUp = (ev) => {
        track.classList.remove('is-dragging');
        thumb.releasePointerCapture(ev.pointerId);
        thumb.removeEventListener('pointermove', onMove);
        thumb.removeEventListener('pointerup', onUp);
        thumb.removeEventListener('pointercancel', onUp);
      };
      thumb.addEventListener('pointermove', onMove);
      thumb.addEventListener('pointerup', onUp);
      thumb.addEventListener('pointercancel', onUp);
    });

    track.addEventListener('pointerdown', (e) => {
      if (e.target === thumb) return;
      scrollToPointer(e.clientY, thumbH / 2);
    });

    const target = isPage ? window : scroller;
    target.addEventListener('scroll', update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(scroller);

    update();
    return { update, remove() { ro.disconnect(); track.remove(); scroller.classList?.remove('cscroll-host'); } };
  }

  // 找出頁面上所有值得掛捲軸的區塊
  function findScrollers() {
    const found = [];
    if (document.documentElement.scrollHeight > document.documentElement.clientHeight + 1) {
      found.push(document.documentElement);
    }
    for (const el of document.body.querySelectorAll('*')) {
      if (el.classList.contains('cscroll-track') || el.closest('.cscroll-track')) continue;
      if (el.clientHeight < MIN_AREA_H) continue;
      if (el.scrollHeight <= el.clientHeight + 4) continue;
      const oy = getComputedStyle(el).overflowY;
      if (oy === 'auto' || oy === 'scroll') found.push(el);
    }
    return found;
  }

  function refresh() {
    const wanted = new Set(findScrollers());
    for (const [el, bar] of bars) {
      if (!wanted.has(el) || !el.isConnected) { bar.remove(); bars.delete(el); }
    }
    for (const el of wanted) {
      if (bars.has(el)) bars.get(el).update();
      else bars.set(el, createBar(el));
    }
  }

  // 元件自己也會動 DOM，這裡用 rAF 收斂，避免 observer 互相觸發成迴圈
  let pending = false;
  function scheduleRefresh() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; refresh(); });
  }

  function mount() {
    refresh();
    window.addEventListener('resize', scheduleRefresh);
    // 內容會隨資料載入、影片載入、關卡切換而變，持續盯著
    new ResizeObserver(scheduleRefresh).observe(document.body);
    new MutationObserver(scheduleRefresh).observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
