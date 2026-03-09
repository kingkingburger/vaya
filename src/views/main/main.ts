import { Electroview } from "electrobun/view";
import type { VayaRPC } from "../../bun/rpc-schema";

// ===== Constants =====
const BACKEND_URL = "http://127.0.0.1:8765";
const WS_URL = "ws://127.0.0.1:8765";

// ===== State =====
type Screen = "loading" | "error" | "drop" | "main";
let currentScreen: Screen = "loading";
let gpuAvailable = false;
let nvencAvailable = false;
let currentVideoId: string | null = null;
type Segment = { start: number; end: number; score: number; manual?: boolean };
let highlights: Segment[] = [];
let selectedSegmentIdx: number = -1;
let wsConnection: WebSocket | null = null;

// Undo/Redo
let undoStack: Segment[][] = [];
let redoStack: Segment[][] = [];

// Timeline interaction state
type MouseMode = "idle" | "dragging_segment" | "resizing_left" | "resizing_right" | "adding";
let mouseMode: MouseMode = "idle";
let dragSegmentIdx = -1;
let dragStartX = 0;
let dragOrigStart = 0;
let dragOrigEnd = 0;

// Debounce save
let saveTimeout: ReturnType<typeof setTimeout> | null = null;

// ===== DOM refs =====
const screens = {
  loading: document.getElementById("screen-loading")!,
  error: document.getElementById("screen-error")!,
  drop: document.getElementById("screen-drop")!,
  main: document.getElementById("screen-main")!,
};

const errorMessage = document.getElementById("error-message")!;
const retryBtn = document.getElementById("retry-btn")!;
const browseBtn = document.getElementById("browse-btn")!;
const dropZone = document.getElementById("drop-zone")!;
const dropGpuText = document.getElementById("drop-gpu-text")!;
const mainGpuText = document.getElementById("main-gpu-text")!;

// Main screen - info fields
const infoFilename = document.getElementById("info-filename")!;
const infoResolution = document.getElementById("info-resolution")!;
const infoFps = document.getElementById("info-fps")!;
const infoDuration = document.getElementById("info-duration")!;
const infoCodec = document.getElementById("info-codec")!;
const infoSize = document.getElementById("info-size")!;

// Progress
const progressBanner = document.getElementById("progress-banner")!;
const progressStage = document.getElementById("progress-stage")!;
const progressPercent = document.getElementById("progress-percent")!;
const progressBar = document.getElementById("progress-bar")!;

// Timeline
const timelineCanvas = document.getElementById("timeline-canvas") as HTMLCanvasElement;

// Highlight list
const highlightList = document.getElementById("highlight-list")!;

// Toast
const toastContainer = document.getElementById("toast-container")!;

// Modal
const modalOverlay = document.getElementById("modal-overlay")!;
const modalTitle = document.getElementById("modal-title")!;
const modalMessage = document.getElementById("modal-message")!;
const modalCancel = document.getElementById("modal-cancel")!;
const modalConfirm = document.getElementById("modal-confirm")!;

// ===== Screen management =====
function showScreen(screen: Screen) {
  for (const [key, el] of Object.entries(screens)) {
    el.classList.toggle("active", key === screen);
  }
  currentScreen = screen;

  if (screen === "main") {
    resizeTimeline();
  }
}

// ===== Toast system =====
function showToast(message: string, type: "error" | "warning" | "success" = "error", duration = 4000) {
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("toast-out");
    toast.addEventListener("animationend", () => toast.remove());
  }, duration);
}

// ===== Modal system =====
function showModal(title: string, message: string): Promise<boolean> {
  return new Promise((resolve) => {
    modalTitle.textContent = title;
    modalMessage.textContent = message;
    modalOverlay.classList.remove("hidden");

    const cleanup = () => {
      modalOverlay.classList.add("hidden");
      modalCancel.removeEventListener("click", onCancel);
      modalConfirm.removeEventListener("click", onConfirm);
    };

    const onCancel = () => { cleanup(); resolve(false); };
    const onConfirm = () => { cleanup(); resolve(true); };

    modalCancel.addEventListener("click", onCancel);
    modalConfirm.addEventListener("click", onConfirm);
  });
}

// ===== GPU status text =====
function updateGpuText() {
  const text = gpuAvailable
    ? (nvencAvailable ? "GPU + NVENC" : "GPU (no NVENC)")
    : "CPU only";
  dropGpuText.textContent = text;
  mainGpuText.textContent = text;
}

// ===== Format helpers =====
function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatFileSize(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}

function extractFilename(filePath: string): string {
  return filePath.split(/[\\/]/).pop() || filePath;
}

// ===== Video info display =====
function displayVideoInfo(info: {
  duration: number;
  width: number;
  height: number;
  fps: number;
  codec: string;
  file_size: number;
}, filePath: string) {
  infoFilename.textContent = extractFilename(filePath);
  infoFilename.title = filePath;
  infoResolution.textContent = `${info.width}x${info.height}`;
  infoFps.textContent = `${info.fps}`;
  infoDuration.textContent = formatDuration(info.duration);
  infoCodec.textContent = info.codec.toUpperCase();
  infoSize.textContent = formatFileSize(info.file_size);
}

// ===== Timeline rendering =====
let thumbnailImages: HTMLImageElement[] = [];
let videoDuration = 0;

function resizeTimeline() {
  const container = timelineCanvas.parentElement!;
  const dpr = window.devicePixelRatio || 1;
  timelineCanvas.width = container.clientWidth * dpr;
  timelineCanvas.height = container.clientHeight * dpr;
  timelineCanvas.style.width = `${container.clientWidth}px`;
  timelineCanvas.style.height = `${container.clientHeight}px`;
  drawTimeline();
}

function loadThumbnails(videoId: string, urls: string[]) {
  thumbnailImages = [];
  const backendUrl = "http://127.0.0.1:8765";

  for (const url of urls) {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.src = `${backendUrl}${url}`;
    img.onload = () => drawTimeline();
    thumbnailImages.push(img);
  }
}

function drawTimeline() {
  const ctx = timelineCanvas.getContext("2d");
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  const w = timelineCanvas.width;
  const h = timelineCanvas.height;

  ctx.clearRect(0, 0, w, h);

  // Background
  ctx.fillStyle = "#16213e";
  ctx.fillRect(0, 0, w, h);

  if (thumbnailImages.length === 0 || videoDuration <= 0) {
    // Empty state
    ctx.fillStyle = "#6a6a80";
    ctx.font = `${12 * dpr}px -apple-system, sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText("타임라인", w / 2, h / 2 + 4 * dpr);
    return;
  }

  // Draw thumbnails
  const thumbHeight = h - 24 * dpr; // leave space for time markers
  const thumbWidth = (thumbHeight / 180) * 320; // maintain 320:180 aspect
  const totalThumbs = thumbnailImages.length;
  const interval = 5; // seconds per thumbnail
  const pxPerSecond = w / videoDuration;

  for (let i = 0; i < totalThumbs; i++) {
    const img = thumbnailImages[i];
    if (!img.complete || img.naturalWidth === 0) continue;

    const x = i * interval * pxPerSecond;
    const drawW = Math.min(thumbWidth, interval * pxPerSecond);
    ctx.drawImage(img, x, 0, drawW, thumbHeight);
  }

  // Highlight overlays
  if (highlights.length > 0 && videoDuration > 0) {
    for (let idx = 0; idx < highlights.length; idx++) {
      const seg = highlights[idx];
      const hx = seg.start * pxPerSecond;
      const hw = (seg.end - seg.start) * pxPerSecond;

      // Manual = blue, auto = orange
      ctx.fillStyle = seg.manual
        ? "rgba(52, 152, 219, 0.4)"
        : "rgba(243, 156, 18, 0.4)";
      ctx.fillRect(hx, 0, hw, thumbHeight);

      // Selected segment border
      if (idx === selectedSegmentIdx) {
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2 * dpr;
        ctx.strokeRect(hx, 0, hw, thumbHeight);

        // Resize handles (6px wide bars at edges)
        const handleW = 6 * dpr;
        ctx.fillStyle = "rgba(255, 255, 255, 0.7)";
        ctx.fillRect(hx - handleW / 2, 0, handleW, thumbHeight);
        ctx.fillRect(hx + hw - handleW / 2, 0, handleW, thumbHeight);
      }
    }
  }

  // Time markers
  ctx.fillStyle = "#a0a0b0";
  ctx.font = `${10 * dpr}px -apple-system, sans-serif`;
  ctx.textAlign = "center";

  const markerInterval = videoDuration > 300 ? 30 : videoDuration > 60 ? 10 : 5;
  for (let t = 0; t <= videoDuration; t += markerInterval) {
    const x = t * pxPerSecond;
    // Tick
    ctx.strokeStyle = "#3a3a5a";
    ctx.beginPath();
    ctx.moveTo(x, thumbHeight);
    ctx.lineTo(x, thumbHeight + 4 * dpr);
    ctx.stroke();
    // Label
    ctx.fillText(formatDuration(t), x, h - 4 * dpr);
  }
}

window.addEventListener("resize", () => {
  if (currentScreen === "main") resizeTimeline();
});

// ===== Undo/Redo =====
function pushUndo() {
  undoStack.push(JSON.parse(JSON.stringify(highlights)));
  redoStack = [];
}

function undo() {
  if (undoStack.length === 0) return;
  redoStack.push(JSON.parse(JSON.stringify(highlights)));
  highlights = undoStack.pop()!;
  selectedSegmentIdx = -1;
  renderHighlightList();
  drawTimeline();
  debounceSave();
}

function redo() {
  if (redoStack.length === 0) return;
  undoStack.push(JSON.parse(JSON.stringify(highlights)));
  highlights = redoStack.pop()!;
  selectedSegmentIdx = -1;
  renderHighlightList();
  drawTimeline();
  debounceSave();
}

// ===== Debounced save to backend =====
function debounceSave() {
  if (saveTimeout) clearTimeout(saveTimeout);
  saveTimeout = setTimeout(async () => {
    if (!currentVideoId) return;
    try {
      await fetch(`${BACKEND_URL}/api/video/${currentVideoId}/highlights`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(highlights),
      });
    } catch (e) {
      console.warn("Failed to save highlights:", e);
    }
  }, 500);
}

// ===== Timeline mouse helpers =====
function canvasTimeFromX(clientX: number): number {
  const rect = timelineCanvas.getBoundingClientRect();
  const x = clientX - rect.left;
  return (x / rect.width) * videoDuration;
}

function segmentAtTime(t: number): number {
  for (let i = 0; i < highlights.length; i++) {
    if (t >= highlights[i].start && t <= highlights[i].end) return i;
  }
  return -1;
}

function isNearEdge(clientX: number, segIdx: number, edge: "left" | "right"): boolean {
  const rect = timelineCanvas.getBoundingClientRect();
  const pxPerSec = rect.width / videoDuration;
  const seg = highlights[segIdx];
  const edgeX = edge === "left"
    ? (seg.start * pxPerSec) + rect.left
    : (seg.end * pxPerSec) + rect.left;
  return Math.abs(clientX - edgeX) < 8;
}

// ===== Timeline mouse events =====
timelineCanvas.addEventListener("mousedown", (e) => {
  if (videoDuration <= 0) return;
  const t = canvasTimeFromX(e.clientX);
  const idx = segmentAtTime(t);

  if (idx >= 0) {
    selectedSegmentIdx = idx;

    if (isNearEdge(e.clientX, idx, "left")) {
      mouseMode = "resizing_left";
    } else if (isNearEdge(e.clientX, idx, "right")) {
      mouseMode = "resizing_right";
    } else {
      mouseMode = "dragging_segment";
    }

    dragSegmentIdx = idx;
    dragStartX = e.clientX;
    dragOrigStart = highlights[idx].start;
    dragOrigEnd = highlights[idx].end;
    pushUndo();
  } else {
    // Click empty area → add new 5s manual segment
    selectedSegmentIdx = -1;
    const newStart = Math.max(0, t - 2.5);
    const newEnd = Math.min(videoDuration, t + 2.5);

    pushUndo();
    highlights.push({ start: round2(newStart), end: round2(newEnd), score: 0, manual: true });
    highlights.sort((a, b) => a.start - b.start);
    selectedSegmentIdx = highlights.findIndex(h => h.start === round2(newStart) && h.end === round2(newEnd));
    renderHighlightList();
    debounceSave();
  }

  drawTimeline();
});

timelineCanvas.addEventListener("mousemove", (e) => {
  if (mouseMode === "idle" || dragSegmentIdx < 0) {
    // Update cursor based on hover
    if (videoDuration > 0) {
      const t = canvasTimeFromX(e.clientX);
      const idx = segmentAtTime(t);
      if (idx >= 0 && (isNearEdge(e.clientX, idx, "left") || isNearEdge(e.clientX, idx, "right"))) {
        timelineCanvas.style.cursor = "ew-resize";
      } else if (idx >= 0) {
        timelineCanvas.style.cursor = "grab";
      } else {
        timelineCanvas.style.cursor = "crosshair";
      }
    }
    return;
  }

  const rect = timelineCanvas.getBoundingClientRect();
  const pxPerSec = rect.width / videoDuration;
  const deltaTime = (e.clientX - dragStartX) / pxPerSec;
  const seg = highlights[dragSegmentIdx];

  if (mouseMode === "resizing_left") {
    seg.start = round2(Math.max(0, Math.min(dragOrigStart + deltaTime, seg.end - 0.5)));
  } else if (mouseMode === "resizing_right") {
    seg.end = round2(Math.min(videoDuration, Math.max(dragOrigEnd + deltaTime, seg.start + 0.5)));
  } else if (mouseMode === "dragging_segment") {
    const dur = dragOrigEnd - dragOrigStart;
    let newStart = dragOrigStart + deltaTime;
    newStart = Math.max(0, Math.min(newStart, videoDuration - dur));
    seg.start = round2(newStart);
    seg.end = round2(newStart + dur);
  }

  drawTimeline();
  renderHighlightList();
});

timelineCanvas.addEventListener("mouseup", () => {
  if (mouseMode !== "idle") {
    mouseMode = "idle";
    dragSegmentIdx = -1;
    debounceSave();
  }
});

timelineCanvas.addEventListener("mouseleave", () => {
  if (mouseMode !== "idle") {
    mouseMode = "idle";
    dragSegmentIdx = -1;
    debounceSave();
  }
});

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

// ===== Keyboard shortcuts =====
document.addEventListener("keydown", (e) => {
  if (currentScreen !== "main") return;

  // Delete selected segment
  if (e.key === "Delete" && selectedSegmentIdx >= 0) {
    pushUndo();
    highlights.splice(selectedSegmentIdx, 1);
    selectedSegmentIdx = -1;
    renderHighlightList();
    drawTimeline();
    debounceSave();
    return;
  }

  // Ctrl+Z = Undo
  if (e.ctrlKey && e.key === "z") {
    e.preventDefault();
    undo();
    return;
  }

  // Ctrl+Y = Redo
  if (e.ctrlKey && e.key === "y") {
    e.preventDefault();
    redo();
    return;
  }
});

// ===== RPC setup =====
const rpc = Electroview.defineRPC<VayaRPC>({
  handlers: {
    requests: {
      updateStatus: ({ text, ready }) => {
        // Legacy handler — no-op in new UI
      },
    },
    messages: {
      backendReady: ({ status, gpu_available, nvenc_available }) => {
        gpuAvailable = gpu_available;
        nvencAvailable = nvenc_available;
        updateGpuText();
        showScreen("drop");
      },
      backendError: ({ error }) => {
        errorMessage.textContent = error || "백엔드 연결 실패";
        showScreen("error");
      },
    },
  },
});

const electroview = new Electroview({ rpc });

// ===== Retry button =====
retryBtn.addEventListener("click", () => {
  showScreen("loading");
  // Request backend status check
  electroview.rpc.request.getBackendStatus({}).then((health) => {
    if (health.status === "ok") {
      gpuAvailable = health.gpu_available;
      nvencAvailable = health.nvenc_available;
      updateGpuText();
      showScreen("drop");
    } else {
      errorMessage.textContent = "백엔드가 아직 준비되지 않았습니다";
      showScreen("error");
    }
  }).catch(() => {
    errorMessage.textContent = "백엔드 연결 실패";
    showScreen("error");
  });
});

// ===== Drop zone events =====
browseBtn.addEventListener("click", async (e) => {
  e.stopPropagation();
  const filePath = await electroview.rpc.request.openFileDialog({});
  if (filePath) {
    await handleFileSelected(filePath);
  }
});

dropZone.addEventListener("click", (e) => {
  if (e.target === browseBtn) return;
  browseBtn.click();
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", async (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");

  const file = e.dataTransfer?.files[0];
  if (file) {
    const path = (file as any).path;
    if (path) {
      await handleFileSelected(path);
    } else {
      showToast("드래그&드롭 경로를 가져올 수 없습니다. 파일 선택 버튼을 사용해주세요.", "warning");
    }
  }
});

// ===== WebSocket progress =====
function connectProgressWs(videoId: string) {
  if (wsConnection) {
    wsConnection.close();
    wsConnection = null;
  }

  const ws = new WebSocket(`${WS_URL}/ws/progress/${videoId}`);
  wsConnection = ws;

  ws.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data);
      updateProgress(data.stage, data.percent, data.message);

      if (data.stage === "complete") {
        progressBanner.classList.add("hidden");
        fetchHighlights(videoId);
        fetchSubtitles(videoId);
        enableExportButton();
      } else if (data.stage === "export_complete") {
        progressBanner.classList.add("hidden");
        // Fetch export results
        try {
          const statusRes = await fetch(`${BACKEND_URL}/api/video/${videoId}/export/status`);
          if (statusRes.ok) {
            const statusData = await statusRes.json();
            showExportComplete(statusData.files || []);
          }
        } catch (e) {
          console.warn("Failed to get export status:", e);
        }
      } else if (data.stage === "error") {
        progressBanner.classList.add("hidden");
        showToast(data.message, "error");
        exportBtn.disabled = !analysisComplete;
      }
    } catch (e) {
      console.warn("WS parse error:", e);
    }
  };

  ws.onerror = () => {
    console.warn("WebSocket error");
  };

  ws.onclose = () => {
    wsConnection = null;
    // Auto-reconnect after 2 seconds if we still have a video
    if (currentVideoId && currentScreen === "main") {
      setTimeout(() => {
        if (!wsConnection && currentVideoId) {
          console.log("WebSocket reconnecting...");
          connectProgressWs(currentVideoId);
        }
      }, 2000);
    }
  };
}

function updateProgress(stage: string, percent: number, message: string) {
  progressBanner.classList.remove("hidden");
  progressStage.textContent = message;
  progressPercent.textContent = `${Math.round(percent)}%`;
  progressBar.style.width = `${percent}%`;
}

// ===== Analysis auto-start =====
async function startAnalysis(videoId: string) {
  // Connect WebSocket first
  connectProgressWs(videoId);

  // Show progress banner
  updateProgress("init", 0, "분석 준비 중...");

  try {
    const res = await fetch(`${BACKEND_URL}/api/video/${videoId}/analyze`, {
      method: "POST",
    });
    if (!res.ok) {
      const err = await res.json();
      showToast(`분석 시작 실패: ${err.detail}`, "error");
      progressBanner.classList.add("hidden");
    }
  } catch (e) {
    showToast(`분석 시작 실패: ${e}`, "error");
    progressBanner.classList.add("hidden");
  }
}

// ===== Fetch & display highlights =====
async function fetchHighlights(videoId: string) {
  try {
    const res = await fetch(`${BACKEND_URL}/api/video/${videoId}/highlights`);
    if (!res.ok) return;

    highlights = await res.json();

    // If no highlights, set full video as 1 segment
    if (highlights.length === 0 && videoDuration > 0) {
      highlights = [{ start: 0, end: videoDuration, score: 0 }];
      showToast("하이라이트 구간이 감지되지 않아 전체 영상을 1개 구간으로 설정했습니다.", "warning");
    }

    renderHighlightList();
    drawTimeline();
  } catch (e) {
    console.warn("Failed to fetch highlights:", e);
  }
}

function renderHighlightList() {
  let html = "";

  if (highlights.length === 0) {
    html = '<p class="placeholder-text">하이라이트 구간 없음</p>';
  } else {
    html = highlights
      .map((h, i) => {
        const duration = h.end - h.start;
        const selected = i === selectedSegmentIdx ? " selected" : "";
        const typeClass = h.manual ? " manual" : " auto";
        return `<div class="highlight-item${selected}${typeClass}" data-idx="${i}">
          <span class="highlight-num">#${i + 1}</span>
          <span class="highlight-time">${formatDuration(h.start)} - ${formatDuration(h.end)}</span>
          <span class="highlight-duration">${duration.toFixed(1)}s</span>
          <button class="highlight-delete" data-idx="${i}" title="삭제">\u00d7</button>
        </div>`;
      })
      .join("");
  }

  html += '<button class="btn-add-segment" id="add-segment-btn">+ 구간 추가</button>';
  highlightList.innerHTML = html;

  // Event: click highlight item → select
  highlightList.querySelectorAll(".highlight-item").forEach((el) => {
    el.addEventListener("click", (e) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains("highlight-delete")) return;
      const idx = parseInt(el.getAttribute("data-idx") || "-1");
      selectedSegmentIdx = idx;
      renderHighlightList();
      drawTimeline();
    });
  });

  // Event: click delete button
  highlightList.querySelectorAll(".highlight-delete").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const idx = parseInt((btn as HTMLElement).getAttribute("data-idx") || "-1");
      if (idx >= 0) {
        pushUndo();
        highlights.splice(idx, 1);
        if (selectedSegmentIdx >= highlights.length) selectedSegmentIdx = -1;
        renderHighlightList();
        drawTimeline();
        debounceSave();
      }
    });
  });

  // Event: add segment button
  const addBtn = document.getElementById("add-segment-btn");
  if (addBtn) {
    addBtn.addEventListener("click", () => {
      pushUndo();
      const start = videoDuration > 5 ? videoDuration / 2 - 2.5 : 0;
      const end = Math.min(videoDuration, start + 5);
      highlights.push({ start: round2(start), end: round2(end), score: 0, manual: true });
      highlights.sort((a, b) => a.start - b.start);
      selectedSegmentIdx = highlights.findIndex(h => h.start === round2(start));
      renderHighlightList();
      drawTimeline();
      debounceSave();
    });
  }
}

// ===== Settings panel =====
const settingSliders = {
  audioWeight: document.getElementById("setting-audio-weight") as HTMLInputElement,
  videoWeight: document.getElementById("setting-video-weight") as HTMLInputElement,
  topPercent: document.getElementById("setting-top-percent") as HTMLInputElement,
  minClip: document.getElementById("setting-min-clip") as HTMLInputElement,
  maxClip: document.getElementById("setting-max-clip") as HTMLInputElement,
  thresholdDb: document.getElementById("setting-threshold-db") as HTMLInputElement,
  whisperModel: document.getElementById("setting-whisper-model") as HTMLSelectElement,
};

const settingValues = {
  audioWeight: document.getElementById("val-audio-weight")!,
  videoWeight: document.getElementById("val-video-weight")!,
  topPercent: document.getElementById("val-top-percent")!,
  minClip: document.getElementById("val-min-clip")!,
  maxClip: document.getElementById("val-max-clip")!,
  thresholdDb: document.getElementById("val-threshold-db")!,
};

let settingsDebounce: ReturnType<typeof setTimeout> | null = null;

function setupSettingsListeners() {
  const updateDisplay = () => {
    settingValues.audioWeight.textContent = settingSliders.audioWeight.value;
    settingValues.videoWeight.textContent = settingSliders.videoWeight.value;
    settingValues.topPercent.textContent = `${settingSliders.topPercent.value}%`;
    settingValues.minClip.textContent = `${settingSliders.minClip.value}s`;
    settingValues.maxClip.textContent = `${settingSliders.maxClip.value}s`;
    settingValues.thresholdDb.textContent = `${settingSliders.thresholdDb.value}dB`;
  };

  const onSettingChange = () => {
    updateDisplay();
    if (settingsDebounce) clearTimeout(settingsDebounce);
    settingsDebounce = setTimeout(() => saveSettingsAndReanalyze(), 300);
  };

  for (const slider of Object.values(settingSliders)) {
    slider.addEventListener("input", onSettingChange);
  }
}

async function loadSettings() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/settings`);
    if (!res.ok) return;
    const cfg = await res.json();

    settingSliders.audioWeight.value = String(cfg.highlight?.audio_weight ?? 0.6);
    settingSliders.videoWeight.value = String(cfg.highlight?.video_weight ?? 0.4);
    settingSliders.topPercent.value = String(cfg.highlight?.top_percent ?? 30);
    settingSliders.minClip.value = String(cfg.highlight?.min_clip_duration ?? 3);
    settingSliders.maxClip.value = String(cfg.highlight?.max_clip_duration ?? 60);
    settingSliders.thresholdDb.value = String(cfg.silence?.threshold_db ?? -40);
    settingSliders.whisperModel.value = cfg.subtitle?.model ?? "medium";

    // Update display values
    settingValues.audioWeight.textContent = settingSliders.audioWeight.value;
    settingValues.videoWeight.textContent = settingSliders.videoWeight.value;
    settingValues.topPercent.textContent = `${settingSliders.topPercent.value}%`;
    settingValues.minClip.textContent = `${settingSliders.minClip.value}s`;
    settingValues.maxClip.textContent = `${settingSliders.maxClip.value}s`;
    settingValues.thresholdDb.textContent = `${settingSliders.thresholdDb.value}dB`;
  } catch (e) {
    console.warn("Failed to load settings:", e);
  }
}

async function saveSettingsAndReanalyze() {
  if (!currentVideoId) return;

  const settings = {
    highlight: {
      audio_weight: parseFloat(settingSliders.audioWeight.value),
      video_weight: parseFloat(settingSliders.videoWeight.value),
      top_percent: parseInt(settingSliders.topPercent.value),
      min_clip_duration: parseInt(settingSliders.minClip.value),
      max_clip_duration: parseInt(settingSliders.maxClip.value),
      merge_gap: 2,
    },
    silence: {
      threshold_db: parseInt(settingSliders.thresholdDb.value),
      min_silence_duration: 1.5,
      padding: 0.3,
    },
    subtitle: {
      model: settingSliders.whisperModel.value,
      language: "ko",
      font_size: 24,
      font_color: "white",
      outline_color: "black",
      position: "bottom",
    },
  };

  try {
    // Save settings
    await fetch(`${BACKEND_URL}/api/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });

    // Preserve manual segments
    const manualSegments = highlights.filter(h => h.manual);
    showToast("수동 구간은 유지됩니다. 자동 구간만 재계산됩니다.", "warning", 2000);

    // Re-analyze
    startAnalysis(currentVideoId);
  } catch (e) {
    showToast(`설정 저장 실패: ${e}`, "error");
  }
}

setupSettingsListeners();

// ===== Subtitle display =====
const subtitleList = document.getElementById("subtitle-list")!;

async function fetchSubtitles(videoId: string) {
  try {
    const res = await fetch(`${BACKEND_URL}/api/video/${videoId}/subtitles`);
    if (!res.ok) return;
    const subs = await res.json();
    renderSubtitleList(subs);
  } catch (e) {
    console.warn("Failed to fetch subtitles:", e);
  }
}

function renderSubtitleList(subs: Array<{ start: number; end: number; text: string }>) {
  if (subs.length === 0) {
    subtitleList.innerHTML = '<p class="placeholder-text">자막 없음</p>';
    return;
  }

  subtitleList.innerHTML = subs
    .map(s => `<div class="subtitle-item">
      <span class="subtitle-time">${formatDuration(s.start)}</span>
      <span class="subtitle-text">${s.text}</span>
    </div>`)
    .join("");
}

// ===== Export panel =====
const exportYoutube = document.getElementById("export-youtube") as HTMLInputElement;
const exportShorts = document.getElementById("export-shorts") as HTMLInputElement;
const exportSubtitles = document.getElementById("export-subtitles") as HTMLInputElement;
const exportCropOffset = document.getElementById("export-crop-offset") as HTMLInputElement;
const valCropOffset = document.getElementById("val-crop-offset")!;
const offsetRow = document.getElementById("offset-row")!;
const exportBtn = document.getElementById("export-btn") as HTMLButtonElement;
const exportComplete = document.getElementById("export-complete")!;
const exportFileList = document.getElementById("export-file-list")!;
const openFolderBtn = document.getElementById("open-folder-btn")!;
let analysisComplete = false;

// Show/hide crop offset when Shorts is checked
exportShorts.addEventListener("change", () => {
  offsetRow.classList.toggle("hidden", !exportShorts.checked);
});

exportCropOffset.addEventListener("input", () => {
  valCropOffset.textContent = exportCropOffset.value;
});

// Enable export button when analysis completes
function enableExportButton() {
  analysisComplete = true;
  exportBtn.disabled = false;
}

exportBtn.addEventListener("click", async () => {
  if (!currentVideoId || !analysisComplete) return;

  exportBtn.disabled = true;
  exportComplete.classList.add("hidden");

  try {
    const res = await fetch(`${BACKEND_URL}/api/video/${currentVideoId}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        youtube: exportYoutube.checked,
        shorts: exportShorts.checked,
        subtitles: exportSubtitles.checked,
        crop_offset: parseInt(exportCropOffset.value),
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(`내보내기 실패: ${err.detail}`, "error");
      exportBtn.disabled = false;
      return;
    }

    // Progress will come via WebSocket
    updateProgress("export", 0, "내보내기 시작...");
  } catch (e) {
    showToast(`내보내기 실패: ${e}`, "error");
    exportBtn.disabled = false;
  }
});

function showExportComplete(files: Array<{ format: string; path: string; size: number }>) {
  exportComplete.classList.remove("hidden");

  exportFileList.innerHTML = files
    .map(f => {
      const name = f.path.split(/[\\/]/).pop() || f.path;
      return `<div class="export-file-item">
        <span class="export-file-name">${name}</span>
        <span class="export-file-size">${formatFileSize(f.size)}</span>
      </div>`;
    })
    .join("");

  exportBtn.disabled = false;
}

openFolderBtn.addEventListener("click", async () => {
  try {
    await electroview.rpc.request.openFolder({ path: "storage/output" });
  } catch (e) {
    console.warn("Failed to open folder:", e);
  }

  // Return to drop screen
  currentVideoId = null;
  highlights = [];
  selectedSegmentIdx = -1;
  thumbnailImages = [];
  videoDuration = 0;
  analysisComplete = false;
  exportBtn.disabled = true;
  exportComplete.classList.add("hidden");
  showScreen("drop");
});

// ===== File selection handler =====
async function handleFileSelected(filePath: string) {
  // Check file extension client-side first
  const ext = filePath.split(".").pop()?.toLowerCase() || "";
  const supported = ["mp4", "mkv", "mov", "webm", "avi"];
  if (!supported.includes(ext)) {
    showToast(`지원하지 않는 형식: ${extractFilename(filePath)} (.${ext})`, "error");
    return;
  }

  try {
    const result = await electroview.rpc.request.uploadVideo({ filePath });
    const info = result.info;

    // Check if video is longer than 1 hour (3600 seconds)
    if (info.duration > 3600) {
      const hours = (info.duration / 3600).toFixed(1);
      const proceed = await showModal(
        "긴 영상 경고",
        `이 영상은 약 ${hours}시간입니다. 분석에 상당한 시간이 소요될 수 있습니다.`
      );
      if (!proceed) return;
    }

    // Transition to main screen
    currentVideoId = result.id;
    videoDuration = info.duration;
    displayVideoInfo(info, filePath);
    showScreen("main");

    // Load thumbnails
    if (result.thumbnail_count > 0) {
      try {
        const thumbRes = await fetch(`${BACKEND_URL}/api/video/${result.id}/thumbnails`);
        if (thumbRes.ok) {
          const thumbData = await thumbRes.json();
          loadThumbnails(result.id, thumbData.thumbnails);
        }
      } catch (e) {
        console.warn("Failed to load thumbnails:", e);
      }
    }

    // Warn if NVENC not available
    if (!nvencAvailable) {
      showToast("NVENC를 사용할 수 없어 libx264로 인코딩됩니다. 내보내기가 느릴 수 있습니다.", "warning", 5000);
    }

    // Load settings and auto-start analysis
    loadSettings();
    startAnalysis(result.id);
  } catch (err) {
    const errMsg = String(err);
    if (errMsg.includes("404") || errMsg.includes("not found")) {
      showToast(`파일을 찾을 수 없습니다: ${extractFilename(filePath)}`, "error");
    } else if (errMsg.includes("400") || errMsg.includes("Unsupported")) {
      showToast(`지원하지 않는 형식: ${extractFilename(filePath)}`, "error");
    } else {
      showToast(`업로드 실패: ${errMsg}`, "error");
    }
  }
}
