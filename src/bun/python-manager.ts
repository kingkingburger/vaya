import { spawn, type Subprocess } from "bun";
import { join, dirname } from "path";
import { existsSync } from "fs";

let pythonProcess: Subprocess | null = null;

const BACKEND_URL = "http://127.0.0.1:8765";
const HEALTH_ENDPOINT = `${BACKEND_URL}/api/health`;
const MAX_HEALTH_RETRIES = 20;
const HEALTH_RETRY_INTERVAL = 500;

/**
 * Resolve the project root directory.
 * In dev mode, import.meta.dir is inside the build directory:
 *   {projectRoot}/build/dev-win-x64/AppName-dev/Resources/app/bun/
 * We detect the /build/ segment and extract the project root.
 * In source mode (not built), we go up from src/bun/.
 */
function getProjectRoot(): string {
  const dir = import.meta.dir.replace(/\\/g, "/");
  const buildIndex = dir.indexOf("/build/");
  if (buildIndex !== -1) {
    return dir.substring(0, buildIndex);
  }
  // Source mode: src/bun/ -> project root
  return join(import.meta.dir, "../..");
}

/**
 * Find uv executable path.
 * Check common locations on Windows.
 */
function findUvPath(): string {
  const candidates = [
    "uv", // PATH
    join(process.env.USERPROFILE || "", ".local", "bin", "uv.exe"),
    join(process.env.LOCALAPPDATA || "", "uv", "uv.exe"),
  ];
  for (const candidate of candidates) {
    try {
      const result = Bun.spawnSync({ cmd: [candidate, "--version"] });
      if (result.exitCode === 0) {
        console.log(`[python-manager] Found uv at: ${candidate}`);
        return candidate;
      }
    } catch {
      // Not found, try next
    }
  }
  return "uv"; // Default, hope it's in PATH
}

/**
 * Check if an existing server is already running on the backend port.
 * If so, try to reuse it instead of spawning a new process.
 */
async function checkExistingServer(): Promise<boolean> {
  try {
    const res = await fetch(HEALTH_ENDPOINT);
    if (res.ok) {
      console.log("[python-manager] Existing backend server found, reusing it");
      return true;
    }
  } catch {
    // No existing server
  }
  return false;
}

export async function spawnPython(): Promise<boolean> {
  // First, check if a server is already running on the port
  if (await checkExistingServer()) {
    return true;
  }

  const projectRoot = getProjectRoot();
  const backendDir = join(projectRoot, "backend");

  console.log(`[python-manager] Project root: ${projectRoot}`);
  console.log(`[python-manager] Backend dir: ${backendDir}`);

  // Try uv run first (preferred)
  const uvPath = findUvPath();
  try {
    console.log(`[python-manager] Starting backend via ${uvPath} run...`);
    pythonProcess = spawn({
      cmd: [uvPath, "run", "python", "main.py"],
      cwd: backendDir,
      stdout: "inherit",
      stderr: "inherit",
    });
  } catch {
    // Fallback: direct venv python
    const venvPython = join(backendDir, ".venv", "Scripts", "python.exe");
    console.log(`[python-manager] uv failed, trying venv: ${venvPython}`);
    if (!existsSync(venvPython)) {
      console.error(`[python-manager] venv python not found: ${venvPython}`);
      return false;
    }
    try {
      pythonProcess = spawn({
        cmd: [venvPython, "main.py"],
        cwd: backendDir,
        stdout: "inherit",
        stderr: "inherit",
      });
    } catch (e) {
      console.error("[python-manager] Failed to start Python backend:", e);
      return false;
    }
  }

  // Poll health endpoint
  for (let i = 0; i < MAX_HEALTH_RETRIES; i++) {
    try {
      const res = await fetch(HEALTH_ENDPOINT);
      if (res.ok) {
        const data = await res.json();
        console.log("[python-manager] Backend ready:", data);
        return true;
      }
    } catch {
      // Server not ready yet
    }
    await Bun.sleep(HEALTH_RETRY_INTERVAL);
  }

  console.error("[python-manager] Backend failed to start within timeout");
  return false;
}

export function killPython(): void {
  if (pythonProcess) {
    console.log("[python-manager] Killing Python backend...");
    pythonProcess.kill();
    pythonProcess = null;
  }
}

export async function getBackendHealth(): Promise<{
  status: string;
  gpu_available: boolean;
  nvenc_available: boolean;
} | null> {
  try {
    const res = await fetch(HEALTH_ENDPOINT);
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Backend not reachable
  }
  return null;
}

export function getBackendUrl(): string {
  return BACKEND_URL;
}
