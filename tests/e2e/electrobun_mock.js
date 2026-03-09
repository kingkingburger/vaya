// Mock Electroview class for E2E testing
// Replaces Electrobun's WebSocket-based RPC with direct HTTP calls to backend
// Note: BACKEND_URL is already defined in the app code (var BACKEND_URL = "http://127.0.0.1:8765")

class Electroview {
  constructor(config) {
    this.rpc = config.rpc;
    this._init();
  }

  _init() {
    const self = this;

    // Set up transport that handles requests via direct HTTP
    this.rpc.setTransport({
      send(message) {
        if (message.type === 'request') {
          self._handleRequest(message);
        }
      },
      registerHandler(handler) {
        self._rpcHandler = handler;
      }
    });

    // Simulate backend ready message after connection
    setTimeout(async () => {
      try {
        const res = await fetch(BACKEND_URL + '/api/health');
        const health = await res.json();
        if (self._rpcHandler) {
          // RPC message format: {type: 'message', id: messageName, payload: data}
          self._rpcHandler({
            type: 'message',
            id: 'backendReady',
            payload: {
              status: health.status || 'ok',
              gpu_available: health.gpu_available || false,
              nvenc_available: health.nvenc_available || false
            }
          });
        }
      } catch (e) {
        if (self._rpcHandler) {
          self._rpcHandler({
            type: 'message',
            id: 'backendError',
            payload: { error: 'Backend connection failed' }
          });
        }
      }
    }, 300);
  }

  async _handleRequest(message) {
    let result;
    try {
      switch (message.method) {
        case 'getBackendStatus': {
          const res = await fetch(BACKEND_URL + '/api/health');
          result = await res.json();
          break;
        }
        case 'openFileDialog': {
          // Return the test file path set by Playwright via window.__testFilePath
          result = window.__testFilePath || null;
          break;
        }
        case 'uploadVideo': {
          const res = await fetch(BACKEND_URL + '/api/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: message.params.filePath })
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Upload failed');
          }
          result = await res.json();
          break;
        }
        case 'openFolder': {
          result = true;
          break;
        }
        default:
          throw new Error('Unknown RPC method: ' + message.method);
      }

      if (this._rpcHandler) {
        // RPC response format: {type: 'response', id, success: true, payload: data}
        this._rpcHandler({ type: 'response', id: message.id, success: true, payload: result });
      }
    } catch (err) {
      if (this._rpcHandler) {
        this._rpcHandler({
          type: 'response',
          id: message.id,
          success: false,
          error: err.message || String(err)
        });
      }
    }
  }

  // Static method used by the frontend code — delegates to defineElectrobunRPC
  // which properly registers message handlers (backendReady, backendError)
  static defineRPC(config) {
    return defineElectrobunRPC('webview', {
      ...config,
      // Default is 1000ms — uploads with FFmpeg thumbnails can exceed this
      maxRequestTime: 30000
    });
  }
}
