import { Electroview } from "electrobun/view";
import type { VayaRPC } from "../../bun/rpc-schema";

// DOM elements
const statusIndicator = document.querySelector(".status-indicator")!;
const statusText = document.getElementById("status-text")!;
const gpuInfo = document.getElementById("gpu-info")!;
const gpuStatus = document.getElementById("gpu-status")!;
const nvencStatus = document.getElementById("nvenc-status")!;
const uploadArea = document.getElementById("upload-area")!;
const browseBtn = document.getElementById("browse-btn")!;

// Define webview RPC handlers
const rpc = Electroview.defineRPC<VayaRPC>({
  handlers: {
    requests: {
      updateStatus: ({ text, ready }) => {
        statusText.textContent = text;
        statusIndicator.className = `status-indicator ${ready ? "ready" : "connecting"}`;
      },
    },
    messages: {
      backendReady: ({ status, gpu_available, nvenc_available }) => {
        statusIndicator.className = "status-indicator ready";
        statusText.textContent = "Backend ready";

        // Show GPU info
        gpuInfo.style.display = "flex";
        gpuStatus.textContent = `GPU: ${gpu_available ? "Available" : "Not available"}`;
        gpuStatus.className = gpu_available ? "available" : "unavailable";
        nvencStatus.textContent = `NVENC: ${nvenc_available ? "Available" : "Not available"}`;
        nvencStatus.className = nvenc_available ? "available" : "unavailable";

        // Show upload area
        uploadArea.style.display = "flex";
      },
      backendError: ({ error }) => {
        statusIndicator.className = "status-indicator error";
        statusText.textContent = `Backend error: ${error}`;
      },
    },
  },
});

const electroview = new Electroview({ rpc });

// Browse button — primary file selection method (openFileDialog via RPC)
browseBtn.addEventListener("click", async () => {
  const filePath = await electroview.rpc.request.openFileDialog({});
  if (filePath) {
    handleFileSelected(filePath);
  }
});

// Upload area click also opens file dialog
uploadArea.addEventListener("click", (e) => {
  if (e.target === browseBtn) return;
  browseBtn.click();
});

// Drag-and-drop visual feedback (path extraction may not work on WebView2)
uploadArea.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadArea.classList.add("dragover");
});

uploadArea.addEventListener("dragleave", () => {
  uploadArea.classList.remove("dragover");
});

uploadArea.addEventListener("drop", async (e) => {
  e.preventDefault();
  uploadArea.classList.remove("dragover");

  // Try to get file path from drop event (may not work on WebView2)
  const file = e.dataTransfer?.files[0];
  if (file) {
    // Attempt path extraction (Electron-style, may be undefined on WebView2)
    const path = (file as any).path;
    if (path) {
      handleFileSelected(path);
    } else {
      // Fallback: prompt user to use Browse button
      statusText.textContent = "Drag-and-drop path not supported. Please use Browse button.";
      statusIndicator.className = "status-indicator connecting";
    }
  }
});

async function handleFileSelected(filePath: string) {
  statusText.textContent = `Uploading: ${filePath.split(/[\\/]/).pop()}...`;
  statusIndicator.className = "status-indicator connecting";

  try {
    const result = await electroview.rpc.request.uploadVideo({ filePath });
    statusText.textContent = `Loaded: ${filePath.split(/[\\/]/).pop()}`;
    statusIndicator.className = "status-indicator ready";
    console.log("Upload result:", result);
  } catch (err) {
    statusText.textContent = `Upload failed: ${err}`;
    statusIndicator.className = "status-indicator error";
  }
}
