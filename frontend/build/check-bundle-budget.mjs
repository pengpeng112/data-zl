/**
 * 111 号 S8：gzip 体积预算门禁。
 * 在 `pnpm build` 之后运行，对『主入口 JS』『图谱异步包（G6 大图引擎那批）』
 * 与『全部 CSS』计算 gzip 后体积，任一超限即退出码 1（CI 失败关闭）。
 *
 * 用法：`node build/check-bundle-budget.mjs [dist目录]`
 * 预算可通过环境变量覆盖：BUDGET_MAIN_JS_GZ / BUDGET_GRAPH_JS_GZ / BUDGET_CSS_GZ。
 *
 * 设计原则：
 * - 只读扫描 dist，不修改任何产物；
 * - 主入口 JS 从 dist/index.html 的 <script> 入口解析，图谱异步包按稳定的
 *   AdvancedRelationGraph chunk 名识别（不把任意最大 JS 误当图谱包），CSS 合计全部 gzip；
 * - 缺省预算为 2026-08-03 实际基线，未来只允许收紧不允许放宽，防回归。
 */

import { readdir, readFile, stat } from "node:fs/promises";
import { createGzip } from "node:zlib";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const distDir = process.argv[2] || path.resolve(scriptDir, "..", "dist");

const DEFAULTS = {
  // 主入口 gzip 上限（字节）。2026-08-03 基线 ~671KB。
  mainJsGz: 700 * 1024,
  // 图谱 async 包（G6 引擎那页）gzip 上限。基线 ~413KB。
  graphJsGz: 430 * 1024,
  // 全部 CSS 的 gzip 合计上限。基线 ~96KB。
  cssGz: 110 * 1024
};

function envBudget(name, fallback) {
  const raw = process.env[name];
  if (!raw) return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

const BUDGET = {
  mainJsGz: envBudget("BUDGET_MAIN_JS_GZ", DEFAULTS.mainJsGz),
  graphJsGz: envBudget("BUDGET_GRAPH_JS_GZ", DEFAULTS.graphJsGz),
  cssGz: envBudget("BUDGET_CSS_GZ", DEFAULTS.cssGz)
};

/** 计算单个文件的 gzip 后字节数 */
async function gzBytes(filePath) {
  const data = await readFile(filePath);
  return new Promise((resolve, reject) => {
    const g = createGzip({ level: 9 });
    const chunks = [];
    g.on("data", c => chunks.push(c));
    g.on("end", () => resolve(Buffer.concat(chunks).length));
    g.on("error", reject);
    g.end(data);
  });
}

async function listJs() {
  const jsDir = path.join(distDir, "static", "js");
  const names = await readdir(jsDir).catch(() => []);
  const out = [];
  for (const name of names) {
    if (!name.endsWith(".js")) continue;
    const st = await stat(path.join(jsDir, name));
    out.push({ name, full: path.join(jsDir, name), size: st.size });
  }
  return out.sort((a, b) => b.size - a.size);
}

async function listCss() {
  const cssDir = path.join(distDir, "static", "css");
  const out = [];
  const walk = async dir => {
    const entries = await readdir(dir, { withFileTypes: true }).catch(() => []);
    for (const e of entries) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) await walk(full);
      else if (e.name.endsWith(".css")) out.push(full);
    }
  };
  await walk(cssDir);
  return out;
}

async function main() {
  const js = await listJs();
  if (!js.length) {
    console.error(`\u2715 未找到 dist/static/js，请先执行 pnpm build。distDir=${distDir}`);
    process.exit(1);
  }

  const indexHtmlPath = path.join(distDir, "index.html");
  const indexHtml = await readFile(indexHtmlPath, "utf8").catch(() => "");
  const entryMatch = indexHtml.match(/<script[^>]+src="([^"]+\.js)"/);
  const entryName = entryMatch ? entryMatch[1].split("/").pop() : null;

  const entry = entryName
    ? js.find(f => f.name === entryName)
    : js.find(f => f.name.startsWith("index-"));

  const graphCandidates = js.filter(f => f !== entry && /AdvancedRelationGraph/i.test(f.name));
  const graph = graphCandidates.sort((a, b) => b.size - a.size)[0] || null;

  const entryGz = entry ? await gzBytes(entry.full) : 0;
  const graphGz = graph ? await gzBytes(graph.full) : 0;

  const cssFiles = await listCss();
  let cssGzTotal = 0;
  for (const f of cssFiles) cssGzTotal += await gzBytes(f);

  const results = [
    ["main entry js", entryGz, BUDGET.mainJsGz],
    ["graph async js", graphGz, BUDGET.graphJsGz],
    ["total css", cssGzTotal, BUDGET.cssGz]
  ];

  let allOk = true;
  console.log("111 号 S8 gzip 体积预算检查：");
  for (const [label, value, budget] of results) {
    const ok = value <= budget;
    if (!ok) allOk = false;
    console.log(
      `  ${ok ? "PASS" : "FAIL"}  ${label.padEnd(16)} gz=${(value / 1024).toFixed(1).padStart(8)} KB  budget<=${(budget / 1024).toFixed(1).padStart(8)} KB`
    );
  }
  if (entry) console.log(`  entry = ${entry.name}`);
  if (graph) console.log(`  graph(AdvancedRelationGraph) = ${graph.name}`);

  if (!allOk) {
    console.error("\n\u2715 体积预算超限。主入口 / 图谱异步包 / CSS 任一超限，构建视为失败。");
    process.exit(1);
  }
  console.log("\n\u2713 主入口 / 图谱异步包 / CSS 均在 gzip 预算内。");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
