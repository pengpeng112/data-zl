import path from "node:path";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// 119 号 S3：最小复现构建。只打包图谱组件 + 生产脱敏响应，不加载主应用。
export default defineConfig({
  root: __dirname,
  plugins: [vue()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "../src") }
  },
  build: {
    outDir: "dist",
    emptyOutDir: true
  }
});
