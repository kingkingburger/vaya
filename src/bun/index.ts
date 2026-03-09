import { BrowserWindow, BrowserView } from "electrobun/bun";
import type { VayaRPC } from "./rpc-schema";
import { spawnPython, killPython, getBackendHealth, getBackendUrl } from "./python-manager";

// Define RPC handlers for bun side
const rpc = BrowserView.defineRPC<VayaRPC>({
  maxRequestTime: 10000,
  handlers: {
    requests: {
      getBackendStatus: async () => {
        const health = await getBackendHealth();
        if (health) {
          return health;
        }
        return {
          status: "unavailable",
          gpu_available: false,
          nvenc_available: false,
        };
      },

      openFileDialog: async ({ filter }) => {
        const { openFileDialog } = await import("electrobun/bun");
        const result = await openFileDialog({
          allowedFileTypes: filter
            ? [filter]
            : ["mp4", "mkv", "avi", "mov", "webm"],
        });
        return result ?? null;
      },

      openFolder: async ({ path }) => {
        const { exec } = await import("child_process");
        // Open folder in OS file explorer
        const cmd = process.platform === "win32"
          ? `explorer "${path}"`
          : process.platform === "darwin"
            ? `open "${path}"`
            : `xdg-open "${path}"`;
        exec(cmd);
        return true;
      },

      uploadVideo: async ({ filePath }) => {
        const res = await fetch(`${getBackendUrl()}/api/upload`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ file_path: filePath }),
        });
        if (!res.ok) {
          throw new Error(`Upload failed: ${res.statusText}`);
        }
        return await res.json();
      },
    },
    messages: {
      log: ({ msg }) => console.log("[webview]:", msg),
    },
  },
});

// Create the main window
const win = new BrowserWindow({
  title: "Vaya",
  url: "views://main/index.html",
  frame: { width: 1280, height: 800 },
  rpc,
});

// Start Python backend
console.log("[main] Starting Vaya...");

const backendReady = await spawnPython();
const health = backendReady ? await getBackendHealth() : null;

// The webview now pulls backend status via getBackendStatus RPC request on init.
// This push is kept as a best-effort fallback only.
async function sendStatusToWebview() {
  await Bun.sleep(2000);
  try {
    if (health) {
      win.webview.rpc.backendReady({
        status: health.status,
        gpu_available: health.gpu_available,
        nvenc_available: health.nvenc_available,
      });
      console.log("[main] Status pushed to webview (fallback)");
    } else {
      win.webview.rpc.backendError({ error: "Failed to start backend server" });
    }
  } catch (e) {
    console.log("[main] Fallback push failed (webview will pull status via RPC)");
  }
}

sendStatusToWebview();

// Cleanup on window close
win.on("close", () => {
  killPython();
});
