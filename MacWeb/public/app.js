const uidSelect = document.getElementById("uidSelect");
const refreshUidBtn = document.getElementById("refreshUid");
const pickImageBtn = document.getElementById("pickImage");
const filenameInput = document.getElementById("filenameInput");
const filenameSelect = document.getElementById("filenameSelect");
const urlForm = document.getElementById("urlForm");
const resultUrl = document.getElementById("resultUrl");
const copyBtn = document.getElementById("copyBtn");
const statusText = document.getElementById("statusText");
const previewImage = document.getElementById("previewImage");
const previewHint = document.getElementById("previewHint");

function setStatus(message, type = "") {
  statusText.textContent = message;
  statusText.className = `status ${type}`.trim();
}

async function loadUids() {
  uidSelect.innerHTML = "<option value=''>讀取中...</option>";
  try {
    const response = await fetch("/api/uids");
    if (!response.ok) {
      throw new Error("無法讀取 uid。");
    }

    const data = await response.json();
    if (!Array.isArray(data.uids) || data.uids.length === 0) {
      uidSelect.innerHTML = "<option value=''>找不到 uid</option>";
      setStatus("PDMS2 底下沒有可用的 uid 目錄。", "warn");
      return;
    }

    uidSelect.innerHTML = data.uids
      .map((uid) => `<option value="${uid}">${uid}</option>`)
      .join("");

    setStatus(`已載入 ${data.uids.length} 個 uid`, "ok");
  } catch (error) {
    uidSelect.innerHTML = "<option value=''>讀取失敗</option>";
    setStatus(error.message || "讀取 uid 失敗", "warn");
  }
}

async function loadImagesForCurrentUid() {
  const uid = uidSelect.value;
  if (!uid) {
    setStatus("請先選擇 uid", "warn");
    return;
  }

  filenameSelect.innerHTML = "<option value=''>讀取中...</option>";

  try {
    const response = await fetch(`/api/images?uid=${encodeURIComponent(uid)}`);
    if (!response.ok) {
      throw new Error("無法取得圖片清單。");
    }

    const data = await response.json();
    if (!Array.isArray(data.files) || data.files.length === 0) {
      filenameSelect.innerHTML = "<option value=''>沒有圖片</option>";
      setStatus(`${uid} 目錄沒有圖片檔`, "warn");
      return;
    }

    filenameSelect.innerHTML =
      "<option value=''>請選擇圖片</option>" +
      data.files.map((name) => `<option value="${name}">${name}</option>`).join("");

    setStatus(`已載入 ${data.files.length} 張圖片`, "ok");
  } catch (error) {
    filenameSelect.innerHTML = "<option value=''>讀取失敗</option>";
    setStatus(error.message || "讀取圖片清單失敗", "warn");
  }
}

function generateUrl(uid, filename) {
  return `${window.location.origin}/images/${encodeURIComponent(uid)}/${encodeURIComponent(filename)}`;
}

function showPreview(url) {
  previewImage.style.display = "none";
  previewHint.style.display = "block";
  previewHint.textContent = "載入圖片中...";

  previewImage.onload = () => {
    previewImage.style.display = "block";
    previewHint.style.display = "none";
  };

  previewImage.onerror = () => {
    previewImage.style.display = "none";
    previewHint.style.display = "block";
    previewHint.textContent = "圖片不存在或無法讀取";
  };

  previewImage.src = url;
}

urlForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const uid = uidSelect.value.trim();
  const filename = filenameInput.value.trim();

  if (!uid || !filename) {
    setStatus("請輸入 uid 與檔名", "warn");
    return;
  }

  const url = generateUrl(uid, filename);
  resultUrl.value = url;
  setStatus("網址已產生", "ok");
  showPreview(url);
});

refreshUidBtn.addEventListener("click", () => {
  loadUids();
});

pickImageBtn.addEventListener("click", () => {
  loadImagesForCurrentUid();
});

filenameSelect.addEventListener("change", () => {
  if (filenameSelect.value) {
    filenameInput.value = filenameSelect.value;
  }
});

copyBtn.addEventListener("click", async () => {
  const url = resultUrl.value.trim();
  if (!url) {
    setStatus("目前沒有可複製的網址", "warn");
    return;
  }

  try {
    await navigator.clipboard.writeText(url);
    setStatus("已複製網址到剪貼簿", "ok");
  } catch {
    setStatus("複製失敗，請手動複製", "warn");
  }
});

loadUids();
