// 與主站共用的 localStorage key
const KEY = "kid-quest-progress-v1";

// 獲取當前的 uid（改用後端 session）
async function getCurrentUid() {
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

/* ========= SVG 圖示庫 ========= */
const SVG_ICONS = {
  // 橋樑：增加拱形結構與水波紋，更有立體感
  bridge: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="wood" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#A0522D"/>
        <stop offset="100%" stop-color="#8B4513"/>
      </linearGradient>
    </defs>
    <path d="M0 75 Q 50 90, 100 75 L 100 100 L 0 100 Z" fill="#87CEEB" opacity="0.6"/>
    <path d="M 10 70 Q 50 40, 90 70" fill="none" stroke="#654321" stroke-width="4"/>
    <rect x="5" y="55" width="10" height="20" rx="2" fill="#654321"/>
    <rect x="85" y="55" width="10" height="20" rx="2" fill="#654321"/>
    <rect x="45" y="55" width="10" height="20" rx="2" fill="#654321"/>
    <rect x="5" y="60" width="90" height="12" rx="3" fill="url(#wood)" stroke="#5D4037" stroke-width="1"/>
  </svg>`,

  // 城堡：增加塔樓層次與旗幟，顏色更協調
  castle: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect x="25" y="45" width="50" height="45" rx="2" fill="#C0C0C0"/>
    <rect x="20" y="35" width="15" height="20" rx="1" fill="#A9A9A9"/>
    <rect x="65" y="35" width="15" height="20" rx="1" fill="#A9A9A9"/>
    <rect x="40" y="25" width="20" height="30" rx="1" fill="#808080"/>
    <path d="M 40 25 L 40 10 L 55 18 Z" fill="#DC143C"/>
    <rect x="40" y="10" width="2" height="15" fill="#333"/>
    <path d="M 42 70 A 8 8 0 0 1 58 70 L 58 90 L 42 90 Z" fill="#654321"/>
    <rect x="20" y="35" width="15" height="5" fill="#696969"/>
    <rect x="65" y="35" width="15" height="5" fill="#696969"/>
    <rect x="40" y="25" width="20" height="5" fill="#555"/>
  </svg>`,

  // 樓梯：增加側面陰影，呈現 3D 效果
  stairs: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <path d="M10 90 L 30 90 L 30 70 L 50 70 L 50 50 L 70 50 L 70 30 L 90 30 L 90 90 Z" fill="#D2B48C"/>
    <rect x="10" y="70" width="20" height="20" fill="#8B4513"/>
    <rect x="30" y="50" width="20" height="20" fill="#8B4513"/>
    <rect x="50" y="30" width="20" height="20" fill="#8B4513"/>
    <rect x="70" y="10" width="20" height="20" fill="#8B4513"/>
    <rect x="10" y="70" width="20" height="5" fill="#5D4037" opacity="0.3"/>
    <rect x="30" y="50" width="20" height="5" fill="#5D4037" opacity="0.3"/>
    <rect x="50" y="30" width="20" height="5" fill="#5D4037" opacity="0.3"/>
    <rect x="70" y="10" width="20" height="5" fill="#5D4037" opacity="0.3"/>
  </svg>`,

  // 牆壁：交錯的磚塊排列 (Running Bond)，更真實
  wall: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect x="5" y="15" width="90" height="70" fill="#CD5C5C" rx="2"/>
    <g stroke="#8B0000" stroke-width="2">
      <line x1="5" y1="32" x2="95" y2="32"/>
      <line x1="5" y1="50" x2="95" y2="50"/>
      <line x1="5" y1="68" x2="95" y2="68"/>
      <line x1="35" y1="15" x2="35" y2="32"/>
      <line x1="65" y1="15" x2="65" y2="32"/>
      <line x1="20" y1="32" x2="20" y2="50"/>
      <line x1="50" y1="32" x2="50" y2="50"/>
      <line x1="80" y1="32" x2="80" y2="50"/>
      <line x1="35" y1="50" x2="35" y2="68"/>
      <line x1="65" y1="50" x2="65" y2="68"/>
      <line x1="20" y1="68" x2="20" y2="85"/>
      <line x1="50" y1="68" x2="50" y2="85"/>
      <line x1="80" y1="68" x2="80" y2="85"/>
    </g>
  </svg>`,

  // 圓形：增加光澤與雙重邊框
  circle: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <circle cx="50" cy="50" r="35" fill="none" stroke="#FF69B4" stroke-width="8"/>
    <circle cx="50" cy="50" r="35" fill="none" stroke="#FF1493" stroke-width="2" opacity="0.3"/>
  </svg>`,

  // 正方形：圓角與雙重邊框
  square: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect x="20" y="20" width="60" height="60" rx="5" fill="none" stroke="#4169E1" stroke-width="8"/>
    <rect x="20" y="20" width="60" height="60" rx="5" fill="none" stroke="#000080" stroke-width="2" opacity="0.2"/>
  </svg>`,

  // 叉叉：圓潤端點
  cross: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <line x1="25" y1="25" x2="75" y2="75" stroke="#FF6347" stroke-width="10" stroke-linecap="round"/>
    <line x1="75" y1="25" x2="25" y2="75" stroke="#FF6347" stroke-width="10" stroke-linecap="round"/>
  </svg>`,

  // 線條：兩端增加圓點強調
  line: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <line x1="15" y1="50" x2="85" y2="50" stroke="#32CD32" stroke-width="8" stroke-linecap="round"/>
    <circle cx="15" cy="50" r="4" fill="#32CD32"/>
    <circle cx="85" cy="50" r="4" fill="#32CD32"/>
  </svg>`,

  // 油漆：改成滾輪刷過的痕跡
  paint: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect x="15" y="35" width="70" height="30" fill="#FFD700" opacity="0.8"/>
    <path d="M 15 35 Q 35 25, 55 35 T 85 35" stroke="#DAA520" stroke-width="2" fill="none"/>
    <path d="M 15 65 Q 35 75, 55 65 T 85 65" stroke="#DAA520" stroke-width="2" fill="none"/>
    <line x1="10" y1="50" x2="90" y2="50" stroke="#FFD700" stroke-width="28" stroke-opacity="0.3" stroke-linecap="round"/>
  </svg>`,

  // 連接：節點更清晰
  connect: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <line x1="25" y1="50" x2="75" y2="50" stroke="#4169E1" stroke-width="6" stroke-linecap="round"/>
    <circle cx="25" cy="50" r="12" fill="#FFD700" stroke="#DAA520" stroke-width="3"/>
    <circle cx="75" cy="50" r="12" fill="#FFD700" stroke="#DAA520" stroke-width="3"/>
    <circle cx="25" cy="50" r="4" fill="#FFF"/>
    <circle cx="75" cy="50" r="4" fill="#FFF"/>
  </svg>`,

  // === 剪刀系列：具象化的剪刀圖標 ===
  scissorsCircle: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <circle cx="50" cy="50" r="35" fill="#E6F2FF" stroke="#4169E1" stroke-width="3" stroke-dasharray="8,5"/>
    <g transform="translate(50, 75) rotate(-45) scale(0.5)">
      <path d="M -5 0 L -5 -40 M 5 0 L 5 -40" stroke="#C0C0C0" stroke-width="6"/>
      <circle cx="-10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
      <circle cx="10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
      <path d="M 0 -5 L 0 -45" stroke="#A9A9A9" stroke-width="2"/>
    </g>
  </svg>`,

  scissorsSquare: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect x="20" y="20" width="60" height="60" rx="4" fill="#E6F2FF" stroke="#4169E1" stroke-width="3" stroke-dasharray="8,5"/>
    <g transform="translate(50, 75) rotate(-45) scale(0.5)">
      <path d="M -5 0 L -5 -40 M 5 0 L 5 -40" stroke="#C0C0C0" stroke-width="6"/>
      <circle cx="-10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
      <circle cx="10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
    </g>
  </svg>`,

  scissorsHalfpaper: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect x="25" y="15" width="50" height="70" fill="none" stroke="#4169E1" stroke-width="2" stroke-dasharray="5,3"/>
    <line x1="50" y1="15" x2="50" y2="85" stroke="#4169E1" stroke-width="3" stroke-dasharray="6,4"/>
    <g transform="translate(50, 50) rotate(-90) scale(0.5)">
       <path d="M -5 0 L -5 -40 M 5 0 L 5 -40" stroke="#C0C0C0" stroke-width="6"/>
       <circle cx="-10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
       <circle cx="10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
    </g>
  </svg>`,

  scissorsLine: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <line x1="10" y1="50" x2="90" y2="50" stroke="#4169E1" stroke-width="4" stroke-dasharray="8,5"/>
    <g transform="translate(50, 50) rotate(-90) scale(0.5)">
       <path d="M -5 0 L -5 -40 M 5 0 L 5 -40" stroke="#C0C0C0" stroke-width="6"/>
       <circle cx="-10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
       <circle cx="10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
    </g>
  </svg>`,

  // 紙張：增加摺痕細節
  paper: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect x="25" y="15" width="50" height="70" fill="#FFF" stroke="#DAA520" stroke-width="2"/>
    <path d="M 75 15 L 55 15 L 75 35 Z" fill="#EEE8AA" stroke="#DAA520" stroke-width="1"/>
    <line x1="35" y1="30" x2="50" y2="30" stroke="#DAA520" stroke-width="2" stroke-linecap="round"/>
    <line x1="35" y1="45" x2="65" y2="45" stroke="#DAA520" stroke-width="2" stroke-linecap="round"/>
    <line x1="35" y1="60" x2="65" y2="60" stroke="#DAA520" stroke-width="2" stroke-linecap="round"/>
  </svg>`,

  // 摺疊一次：利用顏色展示正反面
  foldOnce: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="foldGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" style="stop-color:#FFF8DC;stop-opacity:1" />
        <stop offset="100%" style="stop-color:#DEB887;stop-opacity:1" />
      </linearGradient>
    </defs>
    <rect x="25" y="25" width="50" height="50" fill="#FFF8DC" stroke="#DAA520" stroke-width="2" stroke-dasharray="4,4"/>
    <path d="M 50 25 L 75 25 L 75 75 L 50 75 Z" fill="url(#foldGrad1)" stroke="#DAA520" stroke-width="2"/>
    <line x1="50" y1="25" x2="50" y2="75" stroke="#8B4513" stroke-width="2" stroke-dasharray="4,2"/>
    <path d="M 40 50 Q 45 45, 50 50" fill="none" stroke="#8B4513" stroke-width="2" marker-end="url(#arrow)"/>
  </svg>`,

  // 摺疊兩次：清晰的摺痕區域
  foldTwice: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <rect x="15" y="30" width="70" height="40" fill="#FFF8DC" stroke="#DAA520" stroke-width="1.5"/>
    <line x1="38" y1="30" x2="38" y2="70" stroke="#8B4513" stroke-width="1.5" stroke-dasharray="3,3"/>
    <line x1="62" y1="30" x2="62" y2="70" stroke="#8B4513" stroke-width="1.5" stroke-dasharray="3,3"/>
    <rect x="38" y="30" width="24" height="40" fill="#DEB887" opacity="0.6"/>
  </svg>`,

  // 豆子：多樣化的顏色與旋轉角度
  beans: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <ellipse cx="30" cy="40" rx="8" ry="12" fill="#FF69B4" transform="rotate(-20, 30, 40)" stroke="#C71585" stroke-width="1"/>
    <ellipse cx="55" cy="45" rx="9" ry="13" fill="#4169E1" transform="rotate(15, 55, 45)" stroke="#000080" stroke-width="1"/>
    <ellipse cx="75" cy="50" rx="8" ry="11" fill="#32CD32" transform="rotate(45, 75, 50)" stroke="#006400" stroke-width="1"/>
    <ellipse cx="40" cy="65" rx="8" ry="12" fill="#FFD700" transform="rotate(-10, 40, 65)" stroke="#B8860B" stroke-width="1"/>
    <ellipse cx="65" cy="70" rx="9" ry="12" fill="#FF6347" transform="rotate(30, 65, 70)" stroke="#8B0000" stroke-width="1"/>
  </svg>`
};

/* ========= 慶祝彩紙 SVG 圖示 ========= */
const CELEBRATION_SVG = {
  // 派對拉炮：增加爆炸的線條感
  party: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <path d="M 45 60 L 55 60 L 50 90 Z" fill="#FFD700"/>
    <circle cx="50" cy="90" r="3" fill="#DAA520"/>
    <g stroke-width="3" stroke-linecap="round">
      <line x1="40" y1="50" x2="30" y2="30" stroke="#FF6347"/>
      <line x1="60" y1="50" x2="70" y2="30" stroke="#4169E1"/>
      <line x1="50" y1="45" x2="50" y2="20" stroke="#32CD32"/>
      <line x1="35" y1="60" x2="20" y2="65" stroke="#FF1493"/>
      <line x1="65" y1="60" x2="80" y2="65" stroke="#FFD700"/>
    </g>
    <circle cx="30" cy="30" r="3" fill="#FF6347"/>
    <circle cx="70" cy="30" r="3" fill="#4169E1"/>
    <circle cx="50" cy="20" r="3" fill="#32CD32"/>
  </svg>`,

  // 氣球：增加高光和立體漸層
  balloon: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <radialGradient id="balloonGrad" cx="30%" cy="30%" r="70%">
        <stop offset="0%" stop-color="#FFB6C1"/>
        <stop offset="100%" stop-color="#DC143C"/>
      </radialGradient>
    </defs>
    <path d="M 50 75 Q 45 85, 50 95" stroke="#888" stroke-width="2" fill="none"/>
    <ellipse cx="50" cy="45" rx="22" ry="28" fill="url(#balloonGrad)"/>
    <ellipse cx="40" cy="35" rx="5" ry="8" fill="#FFF" opacity="0.6" transform="rotate(-15, 40, 35)"/>
    <path d="M 46 72 L 54 72 L 50 78 Z" fill="#DC143C"/>
  </svg>`,

  // 閃光：更銳利且有層次
  sparkle: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <path d="M50 10 L60 40 L90 50 L60 60 L50 90 L40 60 L10 50 L40 40 Z" fill="#FFD700"/>
    <path d="M50 25 L55 45 L75 50 L55 55 L50 75 L45 55 L25 50 L45 45 Z" fill="#FFFACD"/>
  </svg>`,

  // 星星：標準五角星，帶有邊框
  star: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <polygon points="50,10 63,38 94,38 69,56 79,86 50,70 21,86 31,56 6,38 37,38" fill="#FFD700" stroke="#DAA520" stroke-width="2" stroke-linejoin="round"/>
    <polygon points="50,20 58,40 80,40 62,52 69,72 50,60 31,72 38,52 20,40 42,40" fill="#FFF" opacity="0.3"/>
  </svg>`,

  // 閃爍：增加中心發光感
  twinkle: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <circle cx="50" cy="50" r="5" fill="#FFF"/>
    <path d="M50 15 L53 45 L85 50 L53 55 L50 85 L47 55 L15 50 L47 45 Z" fill="#87CEEB"/>
    <line x1="30" y1="30" x2="70" y2="70" stroke="#B0E0E6" stroke-width="3" stroke-linecap="round"/>
    <line x1="70" y1="30" x2="30" y2="70" stroke="#B0E0E6" stroke-width="3" stroke-linecap="round"/>
  </svg>`,

  // 糖果：包裝紙更具細節
  candy: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <polygon points="20,50 35,35 35,65" fill="#FF69B4"/>
    <polygon points="80,50 65,35 65,65" fill="#FF69B4"/>
    <circle cx="50" cy="50" r="20" fill="#FF1493"/>
    <circle cx="50" cy="50" r="15" fill="none" stroke="#FFF" stroke-width="2" opacity="0.5"/>
    <path d="M 40 40 Q 50 35, 60 40" stroke="#FFF" stroke-width="2" fill="none" opacity="0.7"/>
  </svg>`
};

// 任務內容（依 PDF）：ID → 顯示資料
const TASK_MAP = {
  // 第一關
  "ch1-t1": { emoji:"bridge", title:"串積木：做成一條橋",
    desc:"把魔法積木一顆顆串起來，讓我們過河",
    img:"/video/ch1-t1.mp4",
    steps:[
      "把繩子從積木洞穿過去",
      "一顆接一顆串緊，不要鬆掉",
      "拉直看看，像橋一樣穩固就成功！"
    ]
  },
  "ch1-t2": { emoji:"castle", title:"疊城堡：蓋瞭望塔",
    desc:"把魔法石頭一層一層疊高，找到前進方向。",
    img:"/video/ch1-t2.mp4",
    steps:[
      "從下面往上疊起來",
      "每疊一層就輕輕壓一下",
      "疊到和圖一樣就完成"
    ]
  },
  "ch1-t3": { emoji:"stairs", title:"疊階梯：翻過高牆",
    desc:"把方塊疊成樓梯，繼續前往魔法王國。",
    img: () => Math.random() < 0.5 ? "/video/ch1-t3-L.mp4" : "/video/ch1-t3-R.mp4",
    steps:[ "排出一階一階的形狀", "確認每格都踩得到", "小心地走上去！" ]
  },
  "ch1-t4": { emoji:"bridge", title:"疊高牆：蓋出傳送門",
    desc:"把方塊推成一面大牆，變出傳送門。",
    img: "/video/ch1-t4.mp4",
    steps:[ "排出兩層大牆", "確認牆壁間不要有空隙", "慢慢的疊起來！" ]
  },

  // 第二關
  "ch2-t1": { emoji:"circle", title:"畫圓：大圓圓魔法陣",
    desc:"在紙上畫一個大圓圈。",
    img:"/video/ch2-t1.mp4",
    steps:[ "跟著指示圖，照著畫圓", "閉合成完整的圓" ]
  },
  "ch2-t2": { emoji:"square", title:"畫方：守護盾",
    desc:"畫一個正正方方的盾牌。",
    img:"/video/ch2-t2.mp4",
    steps:[ "畫一條水平線", "畫一條垂直線", "連成四個直角的方形" ]
  },
  "ch2-t3": { emoji:"cross", title:"畫十字：啟動魔法",
    desc:"畫出十字星，讓魔法運作起來。",
    img:"/video/ch2-t3.mp4",
    steps:[ "先畫一條直線", "再畫一條與之垂直的直線", "兩線交叉在中心" ]
  },
  "ch2-t4": { emoji:"line", title:"描水平線：打敗恐龍",
    desc:"先用一條直線攻擊牠。",
    img:"/video/ch2-t4.mp4",
    steps:[ "把尺壓穩", "沿著尺邊畫一條直線", "確認線是水平的" ]
  },
  "ch2-t5": { emoji:"paint", title:"兩水平線中塗色：提升威力",
    desc:"把兩條水平線之間塗滿顏色！",
    img:"/video/ch2-t5.mp4",
    steps:[ "畫第二條平行線", "找到兩線之間的空間", "把空間均勻塗滿" ]
  },
  "ch2-t6": { emoji:"connect", title:"兩點連線：開門",
    desc:"把兩顆星星連起來，打開門！",
    img:"/video/ch2-t6.mp4",
    steps:[ "找到兩個點", "直直地畫線連起來", "檢查有沒有超出" ]
  },

  // 第三關
  "ch3-t1": { emoji:"scissorsCircle", title:"剪圓：做圓形窗戶",
    desc:"幫小精靈剪出一個圓窗。",
    img:"/video/ch3-t1.mp4",
    steps:[ "沿著畫好的圓慢慢剪", "手要轉，剪刀慢慢剪", "合上看看圓不圓" ]
  },
  "ch3-t2": { emoji:"scissorsSquare", title:"剪方：做方方正正的門",
    desc:"幫小精靈剪出正方形的門。",
    img:"/video/ch3-t2.mp4",
    steps:[ "剪直線四邊", "角角對齊成直角", "把邊修整整齊" ]
  },
  "ch3-t3": { emoji:"scissorsLine", title:"剪圓：把窗戶剪開",
    desc:"幫小精靈把窗戶剪開。",
    img:"/video/ch3-t3.mp4",
    steps:[ "沿著畫好的圓慢慢剪", "手要穩，線要直", "不要偏離畫好的線喔" ]
  },
  "ch3-t4": { emoji:"scissorsHalfpaper", title:"剪方：剪窗簾",
    desc:"幫小精靈將紙平分成兩半當窗簾。",
    img:"/video/ch3-t4.mp4",
    steps:[ "剪在紙的中心", "手要穩，線要直", "剪完兩張紙應該一樣大" ]
  },

  // 第四關
  "ch4-t1": { emoji:"foldOnce", title:"摺紙一摺：變出小飛毯",
    desc:"把紙對摺一次。",
    img:"/video/ch4-t1.mp4",
    steps:[ "邊對邊", "對齊後再摺", "把摺痕壓緊" ]
  },
  "ch4-t2": { emoji:"foldTwice", title:"摺紙兩摺：更結實的飛毯",
    desc:"再摺一次，就能起飛！",
    img:"/video/ch4-t2.mp4",
    steps:[ "再對摺一次", "壓出清楚摺痕", "展開檢查是否對齊" ]
  },

  // 第五關
  "ch5-t1": { emoji:"beans", title:"豆豆裝罐子：完成任務",
    desc:"把彩色豆豆一顆一顆裝進罐子裡。",
    img:"/video/ch5-t1.mp4",
    steps:[ "打開罐子", "一顆一顆放進去", "蓋緊蓋子" ]
  }
};

// 讀取 query string
function getId(){
  const u = new URL(location.href);
  return u.searchParams.get("id");
}

function render(){
  const id = getId();
  const data = TASK_MAP[id];
  if(!data){ location.replace("index.html"); return; }

  document.title = `${data.title}｜任務操作`;
  document.getElementById("emoji").innerHTML = SVG_ICONS[data.emoji];
  document.getElementById("title").textContent = data.title;
  document.getElementById("desc").textContent  = data.desc;

  const img = document.getElementById("img");
  const video = document.getElementById("video");
  const imgEmoji = document.getElementById("imgEmoji");
  
  // 如果 img 是函數就呼叫它，否則直接用
  const imgSrc = typeof data.img === 'function' ? data.img() : data.img;
  
  if(imgSrc){
    if(imgSrc.endsWith('.mp4')){
      // 顯示影片
      if(video){
        video.src = imgSrc;
        video.style.display = "block";
        video.controls = true;
      }
      if(img) img.style.display = "none";
      imgEmoji.style.display = "none";
      
      // 如果是 ch1-t3，送給 Flask
      if(id === "ch1-t3"){
        const stair_type = imgSrc.includes("-L.mp4") ? "L" : "R";
        fetch("/save-stair-type", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ stair_type: stair_type })
        }).catch(err => console.error("save-stair-type 失敗:", err));
      }
    }else{
      // 顯示圖片
      if(img){
        img.src = imgSrc;
        img.onload = ()=>{ img.style.display="block"; imgEmoji.style.display="none"; if(video) video.style.display="none"; };
        img.onerror = ()=>{ img.style.display="none"; imgEmoji.style.display="block"; if(video) video.style.display="none"; };
      }
      if(video) video.style.display = "none";
    }
  }

  // 步驟清單
  const ol = document.getElementById("steps");
  ol.innerHTML = "";
  (data.steps||[]).forEach(s=>{
    const li = document.createElement("li");
    li.textContent = s;
    ol.appendChild(li);
  });

  // 讀指示
  document.getElementById("readBtn").onclick = ()=>{
    const text = `${data.title}。${data.desc}。步驟：` + (data.steps||[]).join("、");
    const u = new SpeechSynthesisUtterance(text);
    u.lang="zh-TW"; speechSynthesis.cancel(); 
    speechSynthesis.speak(u);
  };
  
  // 停止朗讀
  document.getElementById("stopBtn").onclick = ()=>{
    speechSynthesis.cancel();
  };

  // 完成按鈕
  document.getElementById("doneBtn").onclick = async () => {
    const uid = await getCurrentUid();
    const id = getId(); // 獲取當前 ID，例如 "ch1-t1"

    if (!uid) {
        alert("找不到用戶資訊，請重新登入");
        return;
    }

    // 存入進度 (維持原樣)
    const st = JSON.parse(localStorage.getItem(KEY) || "{}");
    const [chNum, tNum] = id.replace("ch", "").split("-t").map(Number);
    if (!st.done) st.done = {};
    const chKey = `ch${chNum}`;
    if (!Array.isArray(st.done[chKey])) st.done[chKey] = [];
    st.done[chKey][tNum - 1] = true;
    localStorage.setItem(KEY, JSON.stringify(st));

    // 噴彩紙慶祝
    celebrate();

    // 通知後端開始分析 (讀取現有照片)
    try {
        const response = await fetch('/run-python', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id, uid: uid })
        });
        const result = await response.json();

        if (result.success) {
            console.log("分析啟動成功");

            // --- 核心修改：計算下一關 ---
            setTimeout(() => {
                const nextId = `ch${chNum}-t${tNum + 1}`;
                
                // 檢查 TASK_MAP 裡有沒有下一關
                if (TASK_MAP[nextId]) {
                    // 如果有下一關，跳轉到下一關
                    location.href = `task.html?id=${nextId}`;
                } else {
                    // 如果這章沒任務了，嘗試跳到下一章的第一關 (例如 ch1-t4 完接 ch2-t1)
                    const nextChId = `ch${chNum + 1}-t1`;
                    if (TASK_MAP[nextChId]) {
                        location.href = `task.html?id=${nextChId}`;
                    } else {
                        // 全部關卡都破完了，回首頁
                        alert("太棒了！你已經完成所有挑戰！");
                        location.href = "/html/index.html";
                    }
                }
            }, 1000); // 留 1 秒鐘看彩紙特效
            
        } else {
            alert("啟動失敗: " + result.error);
        }
    } catch (err) {
        console.error("錯誤:", err);
    }
};
}

// 簡易彩紙（使用 SVG）
function celebrate(){
  const box = document.getElementById("confetti");
  box.innerHTML="";
  const pieces = ["party", "balloon", "sparkle", "star", "twinkle", "candy"];
  
  for(let i=0; i<24; i++){
    const wrapper = document.createElement("div");
    wrapper.style.position = "absolute";
    wrapper.style.width = "40px";
    wrapper.style.height = "40px";
    wrapper.style.left = Math.random()*100 + "vw";
    wrapper.style.top = "-50px";
    wrapper.style.transform = `rotate(${Math.random()*360}deg)`;
    wrapper.style.transition = "all 0.7s ease-out";
    
    const svgKey = pieces[Math.floor(Math.random()*pieces.length)];
    wrapper.innerHTML = CELEBRATION_SVG[svgKey];
    
    box.appendChild(wrapper);
    
    // 觸發動畫
    setTimeout(() => {
      wrapper.style.top = "100vh";
      wrapper.style.transform = `translateY(0) rotate(${Math.random()*720}deg)`;
    }, 50);
  }
  
  box.classList.add("active");
  setTimeout(()=>{
    box.classList.remove("active");
    box.innerHTML = "";
  }, 700);
}

render();

// 安全返回處理
const HOME = "/html/index.html";
function safeBack(e){
  if(e) e.preventDefault();
  if (document.referrer) {
    try {
      const prev = new URL(document.referrer);
      if (prev.origin === location.origin) { 
        history.back(); 
        return; 
      }
    } catch (err) {}
  }
  location.href = HOME;
}

// 綁定返回按鈕
const topBtn = document.getElementById("backBtn");
const bottomBtn = document.getElementById("backBtnBottom");
if (topBtn) topBtn.addEventListener("click", safeBack);
if (bottomBtn) bottomBtn.addEventListener("click", safeBack);