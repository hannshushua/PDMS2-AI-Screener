// /* ========= SVG 圖示庫 ========= */
// const SVG_ICONS = {
//   // 橋樑：增加了水的波紋和橋拱的結構感
//   bridge: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <defs>
//       <linearGradient id="woodGrad" x1="0%" y1="0%" x2="0%" y2="100%">
//         <stop offset="0%" style="stop-color:#A0522D;stop-opacity:1" />
//         <stop offset="100%" style="stop-color:#8B4513;stop-opacity:1" />
//       </linearGradient>
//     </defs>
//     <path d="M0 80 Q 50 95, 100 80 L 100 100 L 0 100 Z" fill="#87CEEB" opacity="0.6"/>
//     <rect x="5" y="55" width="10" height="30" rx="2" fill="#654321"/>
//     <rect x="85" y="55" width="10" height="30" rx="2" fill="#654321"/>
//     <rect x="45" y="55" width="10" height="30" rx="2" fill="#654321"/>
//     <path d="M 10 65 Q 30 45, 50 65 Q 70 45, 90 65" fill="none" stroke="#654321" stroke-width="4" stroke-linecap="round"/>
//     <rect x="5" y="65" width="90" height="12" rx="3" fill="url(#woodGrad)" stroke="#5D4037" stroke-width="1"/>
//   </svg>`,

//   // 城堡：增加了塔樓的層次感和旗幟
//   castle: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <rect x="25" y="40" width="50" height="50" rx="2" fill="#C0C0C0"/>
//     <rect x="20" y="30" width="15" height="20" rx="1" fill="#A9A9A9"/>
//     <rect x="65" y="30" width="15" height="20" rx="1" fill="#A9A9A9"/>
//     <rect x="40" y="25" width="20" height="25" rx="1" fill="#808080"/>
//     <path d="M 40 25 L 40 10 L 55 18 Z" fill="#DC143C"/>
//     <rect x="40" y="10" width="2" height="15" fill="#333"/>
//     <path d="M 42 65 A 8 8 0 0 1 58 65 L 58 90 L 42 90 Z" fill="#654321"/>
//     <rect x="20" y="30" width="15" height="5" fill="#696969"/>
//     <rect x="65" y="30" width="15" height="5" fill="#696969"/>
//     <rect x="40" y="25" width="20" height="5" fill="#555"/>
//   </svg>`,

//   // 樓梯：增加了立體感（陰影）
//   stairs: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <path d="M10 90 L 30 90 L 30 70 L 50 70 L 50 50 L 70 50 L 70 30 L 90 30 L 90 90 L 10 90" fill="#DEB887"/>
//     <rect x="10" y="70" width="20" height="20" fill="#8B4513"/>
//     <rect x="30" y="50" width="20" height="20" fill="#8B4513"/>
//     <rect x="50" y="30" width="20" height="20" fill="#8B4513"/>
//     <rect x="70" y="10" width="20" height="20" fill="#8B4513"/>
//     <rect x="10" y="70" width="20" height="5" fill="#A0522D" opacity="0.5"/>
//     <rect x="30" y="50" width="20" height="5" fill="#A0522D" opacity="0.5"/>
//     <rect x="50" y="30" width="20" height="5" fill="#A0522D" opacity="0.5"/>
//     <rect x="70" y="10" width="20" height="5" fill="#A0522D" opacity="0.5"/>
//   </svg>`,

//   // 牆壁：交錯的磚塊設計
//   wall: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <rect x="5" y="15" width="90" height="70" fill="#CD5C5C" rx="2"/>
//     <g stroke="#8B0000" stroke-width="2">
//       <line x1="5" y1="32" x2="95" y2="32"/>
//       <line x1="5" y1="50" x2="95" y2="50"/>
//       <line x1="5" y1="68" x2="95" y2="68"/>
//       <line x1="35" y1="15" x2="35" y2="32"/>
//       <line x1="65" y1="15" x2="65" y2="32"/>
//       <line x1="20" y1="32" x2="20" y2="50"/>
//       <line x1="50" y1="32" x2="50" y2="50"/>
//       <line x1="80" y1="32" x2="80" y2="50"/>
//       <line x1="35" y1="50" x2="35" y2="68"/>
//       <line x1="65" y1="50" x2="65" y2="68"/>
//       <line x1="20" y1="68" x2="20" y2="85"/>
//       <line x1="50" y1="68" x2="50" y2="85"/>
//       <line x1="80" y1="68" x2="80" y2="85"/>
//     </g>
//   </svg>`,

//   // 迷宮：更圓潤的路徑，明確的起點（黃點）
//   maze: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <rect x="5" y="5" width="90" height="90" rx="5" fill="#E0F7FA"/>
//     <path d="M 15 15 L 85 15 L 85 85 L 15 85 L 15 35 M 35 35 L 65 35 M 35 35 L 35 65 M 65 35 L 65 65" 
//           stroke="#00838F" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
//     <circle cx="25" cy="25" r="6" fill="#FFD700" stroke="#F57F17" stroke-width="2"/>
//   </svg>`,

//   // 圓形：增加立體光澤
//   circle: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <circle cx="50" cy="50" r="35" fill="none" stroke="#FF69B4" stroke-width="8"/>
//     <circle cx="50" cy="50" r="35" fill="none" stroke="#FF1493" stroke-width="2" opacity="0.3"/>
//   </svg>`,

//   // 正方形：增加圓角和雙重線條
//   square: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <rect x="20" y="20" width="60" height="60" rx="5" fill="none" stroke="#4169E1" stroke-width="8"/>
//     <rect x="20" y="20" width="60" height="60" rx="5" fill="none" stroke="#000080" stroke-width="2" opacity="0.2"/>
//   </svg>`,

//   // 叉叉：圓頭端點，看起來更友善
//   cross: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <line x1="25" y1="25" x2="75" y2="75" stroke="#FF6347" stroke-width="10" stroke-linecap="round"/>
//     <line x1="75" y1="25" x2="25" y2="75" stroke="#FF6347" stroke-width="10" stroke-linecap="round"/>
//   </svg>`,

//   // 線條：簡單明瞭
//   line: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <line x1="15" y1="50" x2="85" y2="50" stroke="#32CD32" stroke-width="8" stroke-linecap="round"/>
//     <circle cx="15" cy="50" r="4" fill="#32CD32"/>
//     <circle cx="85" cy="50" r="4" fill="#32CD32"/>
//   </svg>`,

//   // 油漆：看起來像刷過的痕跡
//   paint: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <path d="M10 40 Q 30 30, 50 40 T 90 40" stroke="#000" stroke-width="2" fill="none" opacity="0.3"/>
//     <path d="M10 70 Q 30 60, 50 70 T 90 70" stroke="#000" stroke-width="2" fill="none" opacity="0.3"/>
//     <path d="M 15 45 Q 35 35, 55 45 T 85 45 L 85 65 Q 65 75, 45 65 T 15 65 Z" fill="#FFD700"/>
//     <path d="M 15 45 Q 35 35, 55 45 T 85 45" stroke="#DAA520" stroke-width="2" fill="none"/>
//   </svg>`,

//   // 連接：節點和線條更清晰
//   connect: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <line x1="25" y1="50" x2="75" y2="50" stroke="#4169E1" stroke-width="6" stroke-linecap="round"/>
//     <circle cx="25" cy="50" r="12" fill="#FFD700" stroke="#DAA520" stroke-width="3"/>
//     <circle cx="75" cy="50" r="12" fill="#FFD700" stroke="#DAA520" stroke-width="3"/>
//     <circle cx="25" cy="50" r="4" fill="#FFF"/>
//     <circle cx="75" cy="50" r="4" fill="#FFF"/>
//   </svg>`,

//   // 房子：增加了煙囪、窗戶和門框
//   house: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <rect x="65" y="25" width="10" height="20" fill="#8B4513"/>
//     <path d="M 50 15 L 15 45 L 85 45 Z" fill="#DC143C" stroke="#8B0000" stroke-width="2" stroke-linejoin="round"/>
//     <rect x="25" y="45" width="50" height="45" fill="#FFF8DC" stroke="#DEB887" stroke-width="2"/>
//     <rect x="42" y="65" width="16" height="25" rx="2" fill="#8B4513"/>
//     <circle cx="45" cy="77" r="1.5" fill="#FFD700"/>
//     <rect x="55" y="52" width="14" height="14" fill="#87CEEB" stroke="#4682B4" stroke-width="2"/>
//     <line x1="62" y1="52" x2="62" y2="66" stroke="#4682B4" stroke-width="2"/>
//     <line x1="55" y1="59" x2="69" y2="59" stroke="#4682B4" stroke-width="2"/>
//   </svg>`,

//   // 剪圓：具象化的剪刀圖標
//   scissorsCircle: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <circle cx="50" cy="50" r="35" fill="#E6F2FF" stroke="#4169E1" stroke-width="3" stroke-dasharray="8,5"/>
//     <g transform="translate(50, 75) rotate(-45) scale(0.5)">
//       <path d="M -5 0 L -5 -40 M 5 0 L 5 -40" stroke="#C0C0C0" stroke-width="6"/>
//       <circle cx="-10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
//       <circle cx="10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
//       <path d="M 0 -5 L 0 -45" stroke="#A9A9A9" stroke-width="2"/>
//     </g>
//   </svg>`,

//   // 剪方：具象化的剪刀圖標
//   scissorsSquare: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <rect x="20" y="20" width="60" height="60" rx="4" fill="#E6F2FF" stroke="#4169E1" stroke-width="3" stroke-dasharray="8,5"/>
//     <g transform="translate(50, 75) rotate(-45) scale(0.5)">
//       <path d="M -5 0 L -5 -40 M 5 0 L 5 -40" stroke="#C0C0C0" stroke-width="6"/>
//       <circle cx="-10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
//       <circle cx="10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
//     </g>
//   </svg>`,
//   scissorsHalfpaper: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <rect x="25" y="15" width="50" height="70" fill="none" stroke="#4169E1" stroke-width="2" stroke-dasharray="5,3"/>
//     <line x1="50" y1="15" x2="50" y2="85" stroke="#4169E1" stroke-width="3" stroke-dasharray="6,4"/>
//     <g transform="translate(50, 50) rotate(-90) scale(0.5)">
//        <path d="M -5 0 L -5 -40 M 5 0 L 5 -40" stroke="#C0C0C0" stroke-width="6"/>
//        <circle cx="-10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
//        <circle cx="10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
//     </g>
//   </svg>`,

//   scissorsLine: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <line x1="10" y1="50" x2="90" y2="50" stroke="#4169E1" stroke-width="4" stroke-dasharray="8,5"/>
//     <g transform="translate(50, 50) rotate(-90) scale(0.5)">
//        <path d="M -5 0 L -5 -40 M 5 0 L 5 -40" stroke="#C0C0C0" stroke-width="6"/>
//        <circle cx="-10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
//        <circle cx="10" cy="10" r="10" fill="none" stroke="#DC143C" stroke-width="4"/>
//     </g>
//   </svg>`,

//   // 紙張：增加了摺痕細節
//   paper: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <rect x="25" y="15" width="50" height="70" fill="#FFF" stroke="#DAA520" stroke-width="2"/>
//     <path d="M 75 15 L 55 15 L 75 35 Z" fill="#EEE8AA" stroke="#DAA520" stroke-width="1"/>
//     <line x1="35" y1="30" x2="50" y2="30" stroke="#DAA520" stroke-width="2" stroke-linecap="round"/>
//     <line x1="35" y1="45" x2="65" y2="45" stroke="#DAA520" stroke-width="2" stroke-linecap="round"/>
//     <line x1="35" y1="60" x2="65" y2="60" stroke="#DAA520" stroke-width="2" stroke-linecap="round"/>
//   </svg>`,

//   // 摺疊一次：使用透明度展示疊加
//   foldOnce: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <defs>
//       <linearGradient id="foldGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
//         <stop offset="0%" style="stop-color:#FFF8DC;stop-opacity:1" />
//         <stop offset="100%" style="stop-color:#F5DEB3;stop-opacity:1" />
//       </linearGradient>
//     </defs>
//     <rect x="20" y="25" width="60" height="50" fill="#FFF8DC" stroke="#DAA520" stroke-width="2" stroke-dasharray="4,4"/>
//     <path d="M 50 25 L 80 25 L 80 75 L 50 75 Z" fill="url(#foldGrad1)" stroke="#DAA520" stroke-width="2"/>
//     <line x1="50" y1="25" x2="50" y2="75" stroke="#8B4513" stroke-width="2" stroke-dasharray="4,2"/>
//     <path d="M 45 50 Q 50 45, 55 50" fill="none" stroke="#8B4513" stroke-width="2" marker-end="url(#arrow)"/>
//   </svg>`,

//   // 摺疊兩次：明顯的摺痕區域
//   foldTwice: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <rect x="15" y="30" width="70" height="40" fill="#FFF8DC" stroke="#DAA520" stroke-width="1.5"/>
//     <line x1="38" y1="30" x2="38" y2="70" stroke="#8B4513" stroke-width="1.5" stroke-dasharray="3,3"/>
//     <line x1="62" y1="30" x2="62" y2="70" stroke="#8B4513" stroke-width="1.5" stroke-dasharray="3,3"/>
//     <rect x="38" y="30" width="24" height="40" fill="#F5DEB3" opacity="0.5"/>
//     <path d="M 25 50 Q 38 40, 45 50" fill="none" stroke="#8B4513" stroke-width="1.5"/>
//   </svg>`,

//   // 寶藏：圓頂寶箱、金幣和光澤
//   treasure: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <defs>
//       <linearGradient id="chestGrad" x1="0%" y1="0%" x2="0%" y2="100%">
//         <stop offset="0%" style="stop-color:#8B4513;stop-opacity:1" />
//         <stop offset="100%" style="stop-color:#5D4037;stop-opacity:1" />
//       </linearGradient>
//     </defs>
//     <path d="M 20 45 Q 50 25, 80 45" fill="#DAA520" stroke="#B8860B" stroke-width="3"/>
//     <rect x="20" y="45" width="60" height="35" rx="3" fill="url(#chestGrad)" stroke="#4E342E" stroke-width="2"/>
//     <rect x="20" y="55" width="60" height="5" fill="#3E2723" opacity="0.3"/>
//     <rect x="45" y="50" width="10" height="12" rx="1" fill="#FFD700" stroke="#B8860B" stroke-width="1"/>
//     <circle cx="50" cy="56" r="2" fill="#000"/>
//     <circle cx="30" cy="45" r="3" fill="#B8860B"/>
//     <circle cx="70" cy="45" r="3" fill="#B8860B"/>
//   </svg>`,

//   // 豆子：多樣化的顏色與旋轉角度
//   beans: `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
//     <ellipse cx="30" cy="40" rx="8" ry="12" fill="#FF69B4" transform="rotate(-20, 30, 40)" stroke="#C71585" stroke-width="1"/>
//     <ellipse cx="55" cy="45" rx="9" ry="13" fill="#4169E1" transform="rotate(15, 55, 45)" stroke="#000080" stroke-width="1"/>
//     <ellipse cx="75" cy="50" rx="8" ry="11" fill="#32CD32" transform="rotate(45, 75, 50)" stroke="#006400" stroke-width="1"/>
//     <ellipse cx="40" cy="65" rx="8" ry="12" fill="#FFD700" transform="rotate(-10, 40, 65)" stroke="#B8860B" stroke-width="1"/>
//     <ellipse cx="65" cy="70" rx="9" ry="12" fill="#FF6347" transform="rotate(30, 65, 70)" stroke="#8B0000" stroke-width="1"/>
//     <path d="M 28 36 Q 30 38, 32 36" stroke="white" stroke-width="2" opacity="0.5" fill="none" transform="rotate(-20, 30, 40)"/>
//   </svg>`
// };

/* ========= PNG 圖示路徑（全部改用 PNG） ========= */
/** 圖片的「共同前綴路徑」——配合 Flask 的 static
 *  → 圖片實際放在：PDMS2_web/static/img/icons/bridge.png
 *  → 瀏覽器路徑：   /static/img/icons/bridge.png
 */
const ICON_BASE = "../images/";

/** 各個任務 / 關卡的檔名（不含路徑） */
const ICON_PATHS = {
  // 第一關
  bridge: "bridge.jpg",
  castle: "tower.jpg",
  stairs: "stairs.jpg",
  wall: "tower.jpg",

  // 第二關
  maze: "maze.jpg",
  circle: "circle.jpg",
  square: "square.jpg",
  cross: "cross.jpg",
  line: "line.jpg",
  paint: "fill.jpg",
  connect: "connect.jpg",

  // 第三關
  house: "circle_win.jpg",
  scissorsCircle: "circle_win.jpg",
  scissorsSquare: "square_door.jpg",
  scissorsLine: "circle_win.jpg",
  scissorsHalfpaper: "square_door.jpg",

  // 第四關
  paper: "fold1.jpg",
  foldOnce: "fold1.jpg",
  foldTwice: "fold2.jpg",

  // 第五關
  treasure: "treasure.jpg",
  beans: "beans.jpg"
};

/** 統一產生 <img> icon 的 HTML */
function getIconHtml(key, altText = "") {
  const file = ICON_PATHS[key];   // 沒列在 ICON_PATHS 就用 key.png
  const src = ICON_BASE + file;
  const alt = altText || key;
  return `<img src="${src}" alt="${alt}" class="icon-img">`;
}


/* ========= 故事資料 ========= */
const STORY = [
  {
    key: "ch1",
    emoji: "bridge",
    title: "第一關：建造魔法道路",
    intro: "小河被颱風沖壞了！把零件找齊，做出能過河的道路吧。",
    tasks: [
      { icon: "bridge", title: "串積木：做成一條橋", note: "把魔法積木一顆顆串起來，讓我們過河。" },
      { icon: "castle", title: "疊城堡：蓋瞭望塔", note: "把魔法石頭一層一層疊高，找到前進方向。" },
      { icon: "stairs", title: "疊階梯：翻過高牆", note: "把方塊疊成樓梯，繼續前往魔法王國。" },
      { icon: "wall", title: "疊高牆：蓋出傳送門", note: "把方塊推成一面大牆，變出傳送門。" },
    ],
  },
  {
    key: "ch2",
    emoji: "maze",
    title: "第二關：神秘圖案迷宮",
    intro: "巫師教我們用圖形魔法通過迷宮！",
    tasks: [
      { icon: "circle", title: "畫圓：大圓圓魔法陣", note: "在紙上畫一個大圓圈。" },
      { icon: "square", title: "畫方：守護盾", note: "畫一個正正方方的盾牌。" },
      { icon: "cross", title: "畫十字：啟動魔法", note: "畫出十字星，讓魔法運作起來。" },
      { icon: "line", title: "描水平線：打敗恐龍", note: "先用一條直線攻擊牠。" },
      { icon: "paint", title: "兩水平線中塗色：提升威力", note: "把兩條水平線之間塗滿顏色！" },
      { icon: "connect", title: "兩點連線：開門", note: "把兩顆星星連起來，打開門！" },
    ],
  },
  {
    key: "ch3",
    emoji: "house",
    title: "第三關：精靈小屋",
    intro: "幫助精靈修好小屋，他會給我們魔法紙作為回報。",
    tasks: [
      { icon: "scissorsCircle", title: "剪圓：做圓形窗戶", note: "幫小精靈剪出一個圓窗。" },
      { icon: "scissorsSquare", title: "剪方：做方方正正的門", note: "幫小精靈剪出正方形的門。" },
      { icon: "scissorsLine", title: "剪圓：把窗戶剪開", note: "幫小精靈把窗戶剪開。" },
      { icon: "scissorsHalfpaper", title: "剪方：剪窗簾", note: "幫小精靈將紙平分成兩半當窗簾。" },
    ],
  },
  {
    key: "ch4",
    emoji: "paper",
    title: "第四關：摺紙飛毯",
    intro: "用魔法紙摺出會飛的飛毯！",
    tasks: [
      { icon: "foldOnce", title: "摺紙一摺：變出小飛毯", note: "把紙對摺一次。" },
      { icon: "foldTwice", title: "摺紙兩摺：更結實的飛毯", note: "再摺一次，就能起飛！" },
    ],
  },
  {
    key: "ch5",
    emoji: "treasure",
    title: "第五關：寶藏大發現",
    intro: "到寶藏洞窟把魔法豆豆裝進罐子，回到魔法王國！",
    tasks: [
      { icon: "beans", title: "豆豆裝罐子：完成任務", note: "把彩色豆豆一顆一顆裝進罐子。" },
    ],
  },
];

/* ========= 狀態儲存 ========= */
/** META_KEY：只存「目前是哪個 UID」 */
const META_KEY = "kid-quest-progress-v1-meta";
/** STATE_KEY_PREFIX：每個 UID 自己的進度，都用這個當前綴 */
const STATE_KEY_PREFIX = "kid-quest-progress-v1";
/** STORAGE_KEY：這次實際要讀寫 localStorage 的 key，會在 init() 裡依照 uid 設定 */
let STORAGE_KEY = STATE_KEY_PREFIX;


async function getCurrentUid() {
  try {
    const response = await fetch("/session/get-uid");
    if (response.ok) {
      const result = await response.json();
      return result.uid;
    } else {
      const st = JSON.parse(localStorage.getItem(META_KEY) || "{}");
      return st.currentUid || null;
    }
  } catch (error) {
    console.error("獲取 UID 時發生錯誤:", error);
    const st = JSON.parse(localStorage.getItem(META_KEY) || "{}");
    return st.currentUid || null;
  }
}

async function setCurrentUid(uid) {
  try {
    const response = await fetch("/session/set-uid", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ uid: uid }),
    });

    if (response.ok) {
      const st = JSON.parse(localStorage.getItem(META_KEY) || "{}");
      st.currentUid = uid;
      localStorage.setItem(META_KEY, JSON.stringify(st));
      return true;
    } else {
      console.error("設置 UID 到 session 失敗");
      return false;
    }
  } catch (error) {
    console.error("設置 UID 時發生錯誤:", error);
    return false;
  }
}



const state = {
  name: "",
  chapterIndex: 0,
  done: {},
};

function loadState() {
  try {
    Object.assign(state, JSON.parse(localStorage.getItem(STORAGE_KEY)) || {});
  } catch {}
  for (const ch of STORY) {
    if (!Array.isArray(state.done[ch.key]))
      state.done[ch.key] = new Array(ch.tasks.length).fill(false);
    else if (state.done[ch.key].length !== ch.tasks.length) {
      const copy = new Array(ch.tasks.length).fill(false);
      for (let i = 0; i < Math.min(copy.length, state.done[ch.key].length); i++)
        copy[i] = !!state.done[ch.key][i];
      state.done[ch.key] = copy;
    }
  }
}
function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}


/* ========= DOM 快捷 ========= */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

function makeTaskId(chIdx, tIdx) {
  return `ch${chIdx + 1}-t${tIdx + 1}`;
}

/* ========= 元件注入（全部改用 PNG） ========= */
function renderStickers() {
  const rail = $("#stickerRail");
  rail.innerHTML = "";
  STORY.forEach((ch, idx) => {
    const btn = document.createElement("button");
    btn.className = "sticker";
    btn.setAttribute("aria-label", ch.title);

    const iconHtml = getIconHtml(ch.emoji, ch.title);

    btn.innerHTML = `
      <div class="emoji">${iconHtml}</div>
      <div class="caption">${idx + 1}關</div>
    `;

    if (idx === state.chapterIndex) btn.classList.add("active");
    btn.addEventListener("click", () => {
      state.chapterIndex = idx;
      saveState();
      renderAll();
    });
    rail.appendChild(btn);
  });
}

function renderStory() {
  const ch = STORY[state.chapterIndex];
  const iconHtml = getIconHtml(ch.emoji, ch.title);

  $("#storyEmoji").innerHTML = iconHtml;
  $("#chapterTitle").textContent = ch.title;
  $("#chapterIntro").textContent = personalize(ch.intro);
  $("#prevBtn").disabled = state.chapterIndex === 0;
  $("#nextBtn").disabled = state.chapterIndex === STORY.length - 1;
}

function renderTasks() {
  const ch = STORY[state.chapterIndex];
  const grid = $("#tasksGrid");
  grid.innerHTML = "";
  ch.tasks.forEach((t, i) => {
    const tpl = $("#taskTpl").content.cloneNode(true);
    const card = tpl.querySelector(".task-card");

    const iconHtml = getIconHtml(t.icon, t.title);
    tpl.querySelector(".task-icon").innerHTML = iconHtml;

    tpl.querySelector(".task-title").textContent = t.title;
    tpl.querySelector(".task-note").textContent = t.note || "";

    const startBtn = tpl.querySelector(".start-btn");
    const doneBtn = tpl.querySelector(".done-btn");

    if (state.done[ch.key][i]) card.classList.add("is-done");

    startBtn.addEventListener("click", () => {
      const id = makeTaskId(state.chapterIndex, i);
      window.location.href = `task.html?id=${encodeURIComponent(id)}`;
    });

    doneBtn.addEventListener("click", () => {
      state.done[ch.key][i] = !state.done[ch.key][i];
      saveState();
      renderAll();
      if (state.done[ch.key][i]) celebrate();
    });

    grid.appendChild(tpl);
  });
}

/* ========= 小老師模式 ========= */
function renderAdmin() {
  const list = $("#chapterList");
  list.innerHTML = "";
  STORY.forEach((ch, idx) => {
    const item = document.createElement("div");
    item.className = "admin-item";
    const done = (state.done[ch.key] || []).filter(Boolean).length;
    item.innerHTML = `
      <span>${idx + 1}. ${ch.title}</span>
      <span class="mini">${done}/${ch.tasks.length}</span>
    `;
    item.addEventListener("click", () => {
      state.chapterIndex = idx;
      saveState();
      renderAll();
    });
    list.appendChild(item);
  });
  $("#childName").value = state.name || "";
}

/* ========= 星星進度與彩紙 ========= */
function renderStars() {
  let total = 0,
    done = 0;
  for (const ch of STORY) {
    total += ch.tasks.length;
    done += (state.done[ch.key] || []).filter(Boolean).length;
  }
  const pct = total ? done / total : 0;
  const stars = [$("#star1"), $("#star2"), $("#star3"), $("#star4"), $("#star5")];
  stars.forEach((s) => s.classList.remove("lit"));
  const lit = Math.round(pct * 5);
  for (let i = 0; i < lit; i++) stars[i].classList.add("lit");
}

/** 不用 emoji，改成彩色小圓點 */
function celebrate() {
  const box = $("#confetti");
  box.innerHTML = "";
  for (let i = 0; i < 30; i++) {
    const s = document.createElement("span");
    s.className = "confetti-dot";
    s.style.left = Math.random() * 100 + "vw";
    s.style.top = "-10vh";
    s.style.width = "10px";
    s.style.height = "10px";
    s.style.borderRadius = "50%";
    s.style.position = "absolute";
    s.style.backgroundColor = `hsl(${Math.random() * 360}, 80%, 60%)`;
    box.appendChild(s);
  }
  box.classList.add("active");
  setTimeout(() => box.classList.remove("active"), 900);
}

/* ========= 旁白 ========= */
function speakStory() {
  const ch = STORY[state.chapterIndex];
  const text =
    `${ch.title}。${personalize(ch.intro)}。` +
    ch.tasks.map((t) => t.title).join("、");
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "zh-TW";
  u.rate = 1;
  u.pitch = 1.05;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}

/* ========= 工具 ========= */
function personalize(text) {
  const name = (state.name || "").trim();
  if (!name) return text;
  return text
    .replaceAll("我們", `${name}和我們`)
    .replaceAll("巫師", `巫師（${name}的好朋友）`);
}

function toast(msg) {
  const n = document.createElement("div");
  n.className = "btn ghost pill";
  n.style.position = "fixed";
  n.style.left = "50%";
  n.style.bottom = "18px";
  n.style.transform = "translateX(-50%)";
  n.style.zIndex = 3;
  n.textContent = msg;
  document.body.appendChild(n);
  setTimeout(() => n.remove(), 1800);
}

/* ========= 綁定事件 ========= */
function bindEvents() {
  $("#prevBtn").addEventListener("click", () => {
    if (state.chapterIndex > 0) {
      state.chapterIndex--;
      saveState();
      renderAll();
    }
  });
  $("#nextBtn").addEventListener("click", () => {
    if (state.chapterIndex < STORY.length - 1) {
      state.chapterIndex++;
      saveState();
      renderAll();
    }
  });

  $("#toggleAdmin").addEventListener("click", (e) => {
    const panel = $("#adminPanel");
    const now = panel.hasAttribute("hidden");
    if (now) panel.removeAttribute("hidden");
    else panel.setAttribute("hidden", "");
    e.currentTarget.setAttribute("aria-expanded", now ? "true" : "false");
  });
  $("#closeAdmin").addEventListener("click", () =>
    $("#adminPanel").setAttribute("hidden", "")
  );

  $("#resetBtn").addEventListener("click", () => {
    if (confirm("要把所有進度清空嗎？")) {
      localStorage.removeItem(STORAGE_KEY); // 只清掉這個 UID 的進度
      // 清掉 state 內容再重新初始化
      state.name = "";
      state.chapterIndex = 0;
      state.done = {};
      loadState();
      renderAll();
    }
  });


  $("#childName").addEventListener("input", (e) => {
    state.name = e.target.value;
    saveState();
    renderAll();
  });

  $("#ttsBtn").addEventListener("click", speakStory);
}

/* ========= 啟動 ========= */
function renderAll() {
  renderStickers();
  renderStory();
  renderTasks();
  renderAdmin();
  renderStars();
}

async function init() {
  // 1. 先問後端目前是誰；如果後端沒回，就退回用 META_KEY 裡的 currentUid
  const uid = await getCurrentUid();

  // 2. 根據 uid 決定這次要讀寫哪一份 localStorage
  //    例如 uid = a012 → kid-quest-progress-v1:a012
  STORAGE_KEY = uid ? `${STATE_KEY_PREFIX}:${uid}` : STATE_KEY_PREFIX;

  // 3. 把這個 key 裡的進度讀進 state，必要時補齊陣列
  loadState();

  // 4. 綁定事件 + 初次渲染
  bindEvents();
  renderAll();
}


window.addEventListener("DOMContentLoaded", () => {
  init();
});

