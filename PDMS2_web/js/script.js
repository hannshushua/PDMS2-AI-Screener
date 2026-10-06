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

/** 各個任務 / 關卡的插圖（掛圖平塗風格；舊版亮面插圖仍保留在 images/icons/） */
const ICON_PATHS = {
  // 第一關：朱紅積木
  blocks_ai:    "chart/ch1-00-建造魔法道路.png",
  bridge:       "chart/ch1-t1-串積木.png",
  castle:       "chart/ch1-t2-疊城堡.png",
  stairs:       "chart/ch1-t3-疊階梯.png",
  wall:         "chart/ch1-t4-疊高牆.png",

  // 第二關：鉻黃蠟筆
  maze:    "chart/ch2-00-神秘圖案迷宮.png",
  circle:  "chart/ch2-t1-畫圓.png",
  square:  "chart/ch2-t2-畫方.png",
  cross:   "chart/ch2-t3-畫十字.png",
  line:    "chart/ch2-t4-描水平線.png",
  paint:   "chart/ch2-t5-兩水平線中塗色.png",
  connect: "chart/ch2-t6-兩點連線.png",

  // 第三關：草綠剪刀
  house:             "chart/ch3-00-精靈小屋.png",
  scissorsCircle:    "chart/ch3-t1-剪圓.png",
  scissorsSquare:    "chart/ch3-t2-剪方.png",
  scissorsLine:      "chart/ch3-t3-剪窗簾.png",
  scissorsHalfpaper: "chart/ch3-t4-剪地毯.png",

  // 第四關：群青色紙
  paper:     "chart/ch4-00-摺紙飛毯.png",
  foldOnce:  "chart/ch4-t1-摺紙一摺.png",
  foldTwice: "chart/ch4-t2-摺紙兩摺.png",

  // 第五關：紫色布條與豆子
  treasure: "chart/ch5-00-寶藏大發現.png",
  beans:    "chart/ch5-t1-豆豆裝罐子.png",
  unbutton: "chart/ch5-t2-解鈕扣.png",
  button:   "chart/ch5-t3-扣鈕扣.png"
};

/** 統一產生 <img> icon 的 HTML。
 *  旁邊一定有文字標題，所以插圖是裝飾性的（alt 留空）；
 *  載入失敗就把圖藏起來，留下空白格，不讓替代文字擠在序號色格下面。 */
function getIconHtml(key) {
  const file = ICON_PATHS[key];   // 沒列在 ICON_PATHS 就用 key.png
  const src = ICON_BASE + encodeURI(file || `${key}.png`);
  return `<img src="${src}" alt="" class="icon-img" decoding="async" onerror="this.onerror=null;this.style.visibility='hidden'">`;
}


/* ========= 故事資料 ========= */
const STORY = [
  {
    key: "ch1",
    emoji: "blocks_ai",
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
      { icon: "scissorsLine", title: "剪窗簾：裝飾圓窗", note: "幫小精靈剪出漂亮的窗簾。" },
      { icon: "scissorsHalfpaper", title: "剪地毯：幫房子鋪地毯", note: "靠自己保持直線，剪出地毯。" },
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
      { icon: "unbutton", title: "解鈕扣：打開魔法披風", note: "把鈕扣條上的鈕扣解開，越快越好。" },
      { icon: "button", title: "扣鈕扣：穿上魔法披風", note: "把最下面的鈕扣扣好，越快越好。" },
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

    const shortTitle = ch.title.replace(/第.+關：/, '');
    btn.innerHTML = `
      <div class="emoji">${iconHtml}</div>
      <div class="caption"><span class="cap-num">第 ${idx + 1} 關</span><br><span class="cap-sub">${shortTitle}</span></div>
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

/* 目前這一關的顏色：主色、壓在主色上的字色、平塗淡底 */
function updateAccentColor() {
  const n = state.chapterIndex + 1;
  const root = document.documentElement;
  root.style.setProperty('--accent',      `var(--ch${n})`);
  root.style.setProperty('--accent-on',   `var(--ch${n}-on)`);
  root.style.setProperty('--accent-tint', `var(--ch${n}-tint)`);
}

function renderStory() {
  const ch = STORY[state.chapterIndex];
  const iconHtml = getIconHtml(ch.emoji, ch.title);

  updateAccentColor();
  resetTts();
  $("#storyCard").dataset.chapter = String(state.chapterIndex + 1);
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

    // 標題拆兩層：冒號前是孩子要做的動作（大字），冒號後是故事（小字）
    const [verb, story] = t.title.split("：");
    tpl.querySelector(".task-verb").textContent = verb;
    tpl.querySelector(".task-story").textContent = story || "";
    tpl.querySelector(".task-title").setAttribute("aria-label", t.title);

    const startBtn = tpl.querySelector(".start-btn");
    const doneBtn = tpl.querySelector(".done-btn");

    const isDone = Boolean(state.done[ch.key][i]);
    card.classList.toggle("is-done", isDone);
    doneBtn.setAttribute("aria-pressed", String(isDone));
    if (isDone && justStamped && justStamped.key === ch.key && justStamped.i === i) {
      card.classList.add("just-stamped");
    }

    startBtn.addEventListener("click", () => {
      const id = makeTaskId(state.chapterIndex, i);
      window.location.href = `task.html?id=${encodeURIComponent(id)}`;
    });

    doneBtn.addEventListener("click", () => {
      state.done[ch.key][i] = !state.done[ch.key][i];
      saveState();
      justStamped = state.done[ch.key][i] ? { key: ch.key, i } : null;
      renderAll();
      justStamped = null;
    });

    grid.appendChild(tpl);
  });

  layoutTaskGrid(grid, ch.tasks.length);
}

/* 剛蓋章的那一格；只在重繪的這一次播動畫 */
let justStamped = null;

/* 欄數同時看任務數與實際可用寬度。
   格子窄於 MIN_CARD_W 就塞不下標題加兩顆按鈕，
   在平板橫向硬排 4 欄會讓文字擠成兩三個字換一行。
   列高交給 CSS 的高度斷點決定，這裡不寫死，否則行內樣式會蓋掉 media query。 */
const MIN_CARD_W = 268;
const GRID_GAP   = 3;   /* 格線粗細 */

function layoutTaskGrid(grid, count) {
  if (!grid || !count) return;
  const avail  = grid.clientWidth || window.innerWidth;
  const fits   = Math.max(1, Math.floor((avail + GRID_GAP) / (MIN_CARD_W + GRID_GAP)));
  const wanted = Math.min(count <= 4 ? count : count <= 6 ? 3 : 4, fits);
  // 掛圖不留空格：欄數要能整除任務數（4 個任務放不下 4 欄時排 2×2，不排 3＋1）
  let cols = 1;
  for (let c = wanted; c >= 1; c--) {
    if (count % c === 0) { cols = c; break; }
  }
  grid.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
  grid.style.removeProperty('grid-auto-rows');
}

/* 轉向或改變視窗大小時重算欄數 */
let _relayoutTimer = null;
function relayoutTaskGrid() {
  clearTimeout(_relayoutTimer);
  _relayoutTimer = setTimeout(() => {
    const grid = $("#tasksGrid");
    const ch = STORY[state.chapterIndex];
    if (grid && ch) layoutTaskGrid(grid, ch.tasks.length);
  }, 120);
}
window.addEventListener("resize", relayoutTaskGrid);
window.addEventListener("orientationchange", relayoutTaskGrid);

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

/* ========= 集點圈進度 ========= */
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

/* ========= 旁白（播放/暫停切換） ========= */
let _ttsPlaying = false;

function setTtsState(playing) {
  _ttsPlaying = playing;
  const btn = $("#ttsBtn");
  btn.textContent = playing ? "暫停" : "聽故事";
  btn.classList.toggle("is-playing", playing);
}

function resetTts() {
  speechSynthesis.cancel();
  setTtsState(false);
}

function toggleStory() {
  if (_ttsPlaying) {
    resetTts();
    return;
  }
  const ch = STORY[state.chapterIndex];
  const text =
    `${ch.title}。${personalize(ch.intro)}。` +
    ch.tasks.map((t) => t.title).join("、");
  const u = new SpeechSynthesisUtterance(text);
  u.lang  = "zh-TW";
  u.rate  = 1;
  u.pitch = 1.05;
  u.onend  = () => setTtsState(false);
  u.onerror = () => setTtsState(false);
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
  setTtsState(true);
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

  $("#ttsBtn").addEventListener("click", toggleStory);

  const switchBtn = $("#switchBtn");
  if (switchBtn) {
    switchBtn.textContent = "換人玩";   // 注音由注音字型本身提供
    switchBtn.addEventListener("click", () => {
      if (confirm("確定要換下一個小朋友玩嗎？")) {
        localStorage.clear();
        location.href = "/html/start.html";
      }
    });
  }
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

