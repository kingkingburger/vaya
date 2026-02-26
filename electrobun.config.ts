import type { ElectrobunConfig } from "electrobun";
import pkg from "./package.json";

export default {
  app: {
    name: "Vaya",
    identifier: "com.vaya.app",
    version: pkg.version,
  },
  build: {
    bun: {
      entrypoint: "src/bun/index.ts",
    },
    views: {
      main: {
        entrypoint: "src/views/main/main.ts",
      },
    },
    copy: {
      "src/views/main/index.html": "views/main/index.html",
      "src/views/main/style.css": "views/main/style.css",
    },
    win: {
      bundleCEF: false,
      defaultRenderer: "native",
    },
  },
  runtime: {
    exitOnLastWindowClosed: true,
  },
} satisfies ElectrobunConfig;
