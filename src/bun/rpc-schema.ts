import type { RPCSchema } from "electrobun/bun";

export type VayaRPC = {
  bun: RPCSchema<{
    requests: {
      getBackendStatus: {
        params: {};
        response: {
          status: string;
          gpu_available: boolean;
          nvenc_available: boolean;
        };
      };
      openFileDialog: {
        params: { filter?: string };
        response: string | null;
      };
      uploadVideo: {
        params: { filePath: string };
        response: {
          id: string;
          info: {
            duration: number;
            width: number;
            height: number;
            fps: number;
            codec: string;
            file_size: number;
          };
          thumbnail_count: number;
        };
      };
      openFolder: {
        params: { path: string };
        response: boolean;
      };
    };
    messages: {
      log: { msg: string };
    };
  }>;

  webview: RPCSchema<{
    requests: {
      updateStatus: {
        params: { text: string; ready: boolean };
        response: void;
      };
    };
    messages: {
      backendReady: {
        status: string;
        gpu_available: boolean;
        nvenc_available: boolean;
      };
      backendError: { error: string };
    };
  }>;
};
