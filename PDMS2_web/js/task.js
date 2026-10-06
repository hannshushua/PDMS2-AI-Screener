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

  // 解鈕扣：披風敞開，鈕扣還縫在右門襟，左門襟只剩空扣眼
  unbutton: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <path d="M66 86 C70 79 78 77 84 84 C79 89 72 84 66 86 Z" fill="#E8A94B" stroke="#3A2570" stroke-width="1.6" stroke-linejoin="round"/>
    <path d="M44 15 C34 17 26 22 22 29 C15 47 14 68 18 85 C23 89 28 83 33 87 C37 89 40 84 41 80 C39 58 40 33 44 15 Z" fill="#5A3FAE" stroke="#3A2570" stroke-width="1.8" stroke-linejoin="round"/>
    <path d="M53 15 C63 17 73 23 78 31 C85 49 87 70 84 85 C78 90 71 83 66 86 C61 89 57 84 56 80 C54 58 52 33 53 15 Z" fill="#7B5CD6" stroke="#3A2570" stroke-width="1.8" stroke-linejoin="round"/>
    <g fill="none" stroke="#3A2570" stroke-width="1.1" opacity="0.28" stroke-linecap="round">
      <path d="M30 33 C27 51 26 68 28 81"/>
      <path d="M36 31 C34 51 34 68 35 79"/>
      <path d="M70 34 C73 52 73 69 71 83"/>
      <path d="M63 30 C64 52 63 69 62 81"/>
    </g>
    <path d="M44 15 C46 11 51 11 53 15 C51 19 46 19 44 15 Z" fill="#3A2570"/>
    <g stroke="#3A2570" stroke-width="1.5" stroke-linecap="round" opacity="0.75">
      <path d="M36 31 L36 38"/><path d="M35 51 L35 58"/><path d="M35 70 L35 77"/>
    </g>
    <g stroke="#8A6118" stroke-width="1.4">
      <circle cx="62" cy="35" r="5.4" fill="#F2C244"/>
      <circle cx="62" cy="55" r="5.4" fill="#F2C244"/>
      <circle cx="61" cy="74" r="5.4" fill="#F2C244"/>
    </g>
    <g fill="#FFF0B8" opacity="0.85">
      <path d="M59 32.6 C60 31.4 62 31.2 63.2 31.9 C61.4 31.9 60 32.6 59 33.8 Z"/>
      <path d="M59 52.6 C60 51.4 62 51.2 63.2 51.9 C61.4 51.9 60 52.6 59 53.8 Z"/>
      <path d="M58 71.6 C59 70.4 61 70.2 62.2 70.9 C60.4 70.9 59 71.6 58 72.8 Z"/>
    </g>
    <g fill="#8A6118">
      <circle cx="60.4" cy="35" r="0.9"/><circle cx="63.6" cy="35" r="0.9"/>
      <circle cx="60.4" cy="55" r="0.9"/><circle cx="63.6" cy="55" r="0.9"/>
      <circle cx="59.4" cy="74" r="0.9"/><circle cx="62.6" cy="74" r="0.9"/>
    </g>
  </svg>`,

  // 扣鈕扣：披風扣合垂順，最下面那顆鈕扣亮起來
  button: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
    <path d="M18 86 C25 90 33 84 41 87 C34 81 24 79 18 86 Z" fill="#E8A94B" stroke="#3A2570" stroke-width="1.6" stroke-linejoin="round"/>
    <path d="M50 14 C40 15 28 21 24 29 C16 48 14 70 18 86 C25 90 33 84 41 87 C46 89 54 89 59 87 C67 84 75 90 82 86 C86 70 84 48 76 29 C72 21 60 15 50 14 Z" fill="#6B4FC4" stroke="#3A2570" stroke-width="1.8" stroke-linejoin="round"/>
    <path d="M50 16 C48 40 48 64 49 86" fill="none" stroke="#3A2570" stroke-width="1.2" opacity="0.45"/>
    <g fill="none" stroke="#3A2570" stroke-width="1.1" opacity="0.26" stroke-linecap="round">
      <path d="M31 32 C27 52 26 70 28 84"/>
      <path d="M39 29 C37 52 37 70 38 85"/>
      <path d="M69 32 C73 52 74 70 72 84"/>
      <path d="M61 29 C63 52 63 70 62 85"/>
    </g>
    <path d="M50 14 C46 10 41 11 38 15 C42 18 47 18 50 16 Z" fill="#3A2570"/>
    <path d="M50 14 C54 10 59 11 62 15 C58 18 53 18 50 16 Z" fill="#3A2570"/>
    <circle cx="50" cy="73" r="13" fill="#FFF0B8" opacity="0.5"/>
    <g stroke="#8A6118" stroke-width="1.4">
      <circle cx="50" cy="36" r="5.4" fill="#F2C244"/>
      <circle cx="50" cy="55" r="5.4" fill="#F2C244"/>
      <circle cx="50" cy="73" r="6.2" fill="#FFDA5E"/>
    </g>
    <g fill="#FFF0B8" opacity="0.85">
      <path d="M47 33.6 C48 32.4 50 32.2 51.2 32.9 C49.4 32.9 48 33.6 47 34.8 Z"/>
      <path d="M47 52.6 C48 51.4 50 51.2 51.2 51.9 C49.4 51.9 48 52.6 47 53.8 Z"/>
      <path d="M46.6 70.2 C47.7 68.9 50 68.7 51.4 69.5 C49.3 69.5 47.7 70.3 46.6 71.7 Z"/>
    </g>
    <g fill="#8A6118">
      <circle cx="48.4" cy="36" r="0.9"/><circle cx="51.6" cy="36" r="0.9"/>
      <circle cx="48.4" cy="55" r="0.9"/><circle cx="51.6" cy="55" r="0.9"/>
      <circle cx="48.2" cy="73" r="1"/><circle cx="51.8" cy="73" r="1"/>
    </g>
  </svg>`,

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

    img: "/video/ch1-t3.mp4",

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

  "ch3-t3": { emoji:"scissorsLine", title:"沿著線剪紙：把窗戶剪開",

    desc:"幫小精靈把窗戶剪開。",

    img:"/video/ch3-t3.mp4",

    steps:[ "沿著畫好的圓慢慢剪", "手要穩，線要直", "不要偏離畫好的線喔" ]

  },

  "ch3-t4": { emoji:"scissorsHalfpaper", title:"把紙剪兩半：剪窗簾",

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

  },

  "ch5-t2": { emoji:"unbutton", title:"解鈕扣：打開魔法披風",

    desc:"把鈕扣條上的鈕扣解開，越快越好。",

    img:"/video/ch5-t2.mp4",

    steps:[ "拿起鈕扣條", "把鈕扣一顆一顆解開", "三顆都解開就完成" ]

  },

  "ch5-t3": { emoji:"button", title:"扣鈕扣：穿上魔法披風",

    desc:"把最下面的鈕扣扣好，越快越好。",

    img:"/video/ch5-t3.mp4",

    steps:[ "拿起鈕扣條", "對準最下面的扣眼", "把鈕扣扣好" ]

  }

};



// 讀取 query string

function getId(){

  const u = new URL(location.href);

  return u.searchParams.get("id");

}



/* 示範影片／圖片的長寬比：CSS 用 --media-ar 算出左欄放得下的最大尺寸，墨框貼著它 */
function setMediaRatio(w, h){
  if (!w || !h) return;
  const fig = document.querySelector(".task-illustration");
  if (fig) fig.style.setProperty("--media-ar", (w / h).toFixed(4));
}

/* 每個任務的掛圖插圖（images/chart/，檔名＝任務編號＋中文名） */
const TASK_CHART_ICONS = {
  "ch1-t1": "ch1-t1-串積木.png",
  "ch1-t2": "ch1-t2-疊城堡.png",
  "ch1-t3": "ch1-t3-疊階梯.png",
  "ch1-t4": "ch1-t4-疊高牆.png",
  "ch2-t1": "ch2-t1-畫圓.png",
  "ch2-t2": "ch2-t2-畫方.png",
  "ch2-t3": "ch2-t3-畫十字.png",
  "ch2-t4": "ch2-t4-描水平線.png",
  "ch2-t5": "ch2-t5-兩水平線中塗色.png",
  "ch2-t6": "ch2-t6-兩點連線.png",
  "ch3-t1": "ch3-t1-剪圓.png",
  "ch3-t2": "ch3-t2-剪方.png",
  "ch3-t3": "ch3-t3-剪窗簾.png",
  "ch3-t4": "ch3-t4-剪地毯.png",
  "ch4-t1": "ch4-t1-摺紙一摺.png",
  "ch4-t2": "ch4-t2-摺紙兩摺.png",
  "ch5-t1": "ch5-t1-豆豆裝罐子.png",
  "ch5-t2": "ch5-t2-解鈕扣.png",
  "ch5-t3": "ch5-t3-扣鈕扣.png"
};

function render(){

  const id = getId();

  const data = TASK_MAP[id];

  if(!data){ location.replace("index.html"); return; }

  // 關卡色：任務頁沿用那一關的掛圖顏色（id 形如 ch2-t1）
  const chNum = parseInt((id.match(/^ch(\d+)/) || [])[1], 10);
  if (chNum >= 1 && chNum <= 5) {
    const root = document.documentElement;
    root.style.setProperty("--accent",      `var(--ch${chNum})`);
    root.style.setProperty("--accent-on",   `var(--ch${chNum}-on)`);
    root.style.setProperty("--accent-tint", `var(--ch${chNum}-tint)`);
  }



  document.title = `${data.title}｜任務操作`;

  // 標題旁的小圖：用這個任務的掛圖插圖；找不到才退回舊的 SVG 圖示
  const chartIcon = TASK_CHART_ICONS[id];
  document.getElementById("emoji").innerHTML = chartIcon
    ? `<img src="/images/chart/${encodeURIComponent(chartIcon)}" alt="">`
    : SVG_ICONS[data.emoji];

  // 標題拆兩層：冒號前是孩子要做的動作（大字），冒號後是故事（小字）
  const titleEl = document.getElementById("title");
  const [verb, story] = data.title.split("：");
  titleEl.innerHTML = "";
  const verbEl = document.createElement("span"); verbEl.className = "task-verb"; verbEl.textContent = verb;
  titleEl.appendChild(verbEl);
  if (story) {
    const storyEl = document.createElement("span"); storyEl.className = "task-story"; storyEl.textContent = story;
    titleEl.appendChild(storyEl);
  }
  titleEl.setAttribute("aria-label", data.title);

  document.getElementById("desc").textContent  = data.desc;



  const img = document.getElementById("img");

  const video = document.getElementById("video");

  const imgEmoji = document.getElementById("imgEmoji");

 

  // 如果 img 是函數就呼叫它，否則直接用

  const imgSrc = typeof data.img === 'function' ? data.img() : data.img;

  // 記下這次抽到的是左邊還是右邊版本（語音提示會跟著同一邊）

  window.__taskSide =

    /[-_](L|left)\.(mp4|webm)$/i.test(imgSrc || "") ? "left" :

    /[-_](R|right)\.(mp4|webm)$/i.test(imgSrc || "") ? "right" : null;

 

  if(imgSrc){

    if(imgSrc.endsWith('.mp4')){

      // 顯示影片

      if(video){

        // 先顯示再設 src：Safari 不會自動播放還在 display:none 的影片

        video.style.display = "block";

        video.controls = true;

        video.muted = true;      // 引導影片一律靜音，不蓋到語音提示

        // 量出影片長寬比交給 CSS，讓影片撐到左欄放得下的最大尺寸
        video.addEventListener("loadedmetadata", () => setMediaRatio(video.videoWidth, video.videoHeight), { once: true });
        video.src = imgSrc;

        forceAutoplay(video);

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

        img.onload = ()=>{ setMediaRatio(img.naturalWidth, img.naturalHeight); img.style.display="block"; imgEmoji.style.display="none"; if(video) video.style.display="none"; };

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



  // 「讀指示 / 停止」改由檔尾的語音提示區塊處理（播放 voice_guide 的 mp3）



  // 完成按鈕

  document.getElementById("doneBtn").onclick = ()=>{

    const st = JSON.parse(localStorage.getItem(KEY) || "{}");

    // 解析 chX-tY

    const [ch,t] = id.split("-").map(s=>parseInt(s.replace(/\D/g,""),10));

    if(!st.done) st.done = {};

    const chKey = `ch${ch}`;

    if(!Array.isArray(st.done[chKey])) st.done[chKey] = [];

    st.done[chKey][t-1] = true;

    localStorage.setItem(KEY, JSON.stringify(st));



    // 按鈕反白一下再前往相機頁（彩紙已退場）

    document.getElementById("doneBtn").classList.add("is-going");

    setTimeout(()=>{

      location.href = `/html/camera.html?id=${encodeURIComponent(id)}`;

    }, 220);

  };

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

// ── 每一關的語音提示：進入 2 秒後播放，播完再等 2 秒重播（無限循環） ──
(function setupVoiceGuide(){

  const id = getId();
  if(!id || !TASK_MAP[id]) return;

  const audio = document.getElementById("guideAudio");
  if(!audio) return;

  const GAP = 2000;          // 進場延遲 / 每次重播間隔（毫秒）
  let timer = null;
  let stopped = false;
  let waiting = false;       // 是否正在等使用者互動解鎖自動播放
  let started = false;       // 是否已經開始播過

  // 抽到左右版本時優先播對應語音，找不到就退回一般版本

  const sources = (window.__taskSide

    ? [`/voice_guide/${id}_${window.__taskSide}.mp3`]

    : []).concat([`/voice_guide/${id}.mp3`]);

  let srcIndex = 0;

  audio.src = sources[srcIndex];

  function stopGuide(){
    stopped = true;
    clearTimeout(timer);
    try{ audio.pause(); }catch(e){}
  }

  // 「讀指示」：不管現在停著還是播到一半，都從頭再播一次，之後繼續循環
  function replayGuide(){
    stopped = false;
    clearTimeout(timer);
    try{ audio.pause(); }catch(e){}
    play();
  }

  function schedule(delay){
    clearTimeout(timer);
    if(stopped) return;
    timer = setTimeout(play, delay);
  }

  function play(){
    if(stopped) return;
    started = true;
    try{ audio.currentTime = 0; }catch(e){}
    const p = audio.play();
    if(p && typeof p.catch === "function"){
      // 瀏覽器擋自動播放時，等使用者第一次互動再播
      p.catch(()=> waitForGesture());
    }
  }

  function waitForGesture(){
    if(waiting || stopped) return;
    waiting = true;
    const kick = ()=>{
      waiting = false;
      document.removeEventListener("click", kick);
      document.removeEventListener("touchstart", kick);
      document.removeEventListener("keydown", kick);
      play();
    };
    document.addEventListener("click", kick);
    document.addEventListener("touchstart", kick);
    document.addEventListener("keydown", kick);
  }

  audio.addEventListener("ended", ()=> schedule(GAP));
  audio.addEventListener("error", ()=>{
    // 這個檔名不存在就換下一個候選
    if(srcIndex + 1 < sources.length){
      srcIndex += 1;
      audio.src = sources[srcIndex];
      // 已經播過才立刻補播；還沒開始的話交給原本的 2 秒倒數
      if(started) schedule(0);
      return;
    }
    console.warn("找不到語音提示：", audio.src);
    stopGuide();
  });

  // 「讀指示」重播、「停止」停掉循環，離開頁面也停
  const readBtn = document.getElementById("readBtn");
  if(readBtn) readBtn.addEventListener("click", replayGuide);
  const stopBtn = document.getElementById("stopBtn");
  if(stopBtn) stopBtn.addEventListener("click", stopGuide);
  const doneBtn = document.getElementById("doneBtn");
  if(doneBtn) doneBtn.addEventListener("click", stopGuide);
  window.addEventListener("pagehide", stopGuide);

  schedule(GAP);

})();


// ── 盡可能讓引導影片自動播放（Safari / iOS 特別龜毛） ──
// 靜音 + playsinline 是自動播放的必要條件，另外在各種時機重試，
// 真的被擋住時，使用者第一次碰到畫面就會補播。
function forceAutoplay(video){

  if(!video) return;

  // 這幾個屬性要在載入時就存在，Safari 才認
  video.muted = true;
  video.defaultMuted = true;
  video.playsInline = true;
  video.setAttribute("muted", "");
  video.setAttribute("playsinline", "");
  video.setAttribute("webkit-playsinline", "");
  video.setAttribute("autoplay", "");

  const MEDIA_EVENTS = ["loadedmetadata", "loadeddata", "canplay", "canplaythrough"];
  const GESTURES = ["pointerdown", "click", "touchstart", "touchend", "keydown"];

  let done = false;
  let tries = 0;

  function cleanup(){
    MEDIA_EVENTS.forEach(e => video.removeEventListener(e, attempt));
    GESTURES.forEach(e => document.removeEventListener(e, attempt, true));
    document.removeEventListener("visibilitychange", attempt);
    clearInterval(poller);
  }

  function attempt(){
    if(done) return;
    if(tries++ > 60){ cleanup(); return; }   // 約 30 秒後放棄自動重試
    const p = video.play();
    if(p && typeof p.then === "function"){
      p.then(()=>{ done = true; cleanup(); }).catch(()=>{ /* 還被擋著，等下一個時機 */ });
    }else if(!video.paused){
      done = true; cleanup();
    }
  }

  MEDIA_EVENTS.forEach(e => video.addEventListener(e, attempt));
  GESTURES.forEach(e => document.addEventListener(e, attempt, true));
  document.addEventListener("visibilitychange", attempt);

  // 有些瀏覽器 promise 不會 reject，只是靜靜地不播 —— 定期檢查補刀
  const poller = setInterval(()=>{ if(video.paused) attempt(); else { done = true; cleanup(); } }, 500);

  video.load();
  attempt();

}
