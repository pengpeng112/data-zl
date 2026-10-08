// 209 S0.7 (v2): 前端路由盘点——逐行扫描 src/router/modules/*.ts 全部 path: 出现，
// 覆盖嵌套 children 路由（v1 正则只抓顶层对象，漏 /quality/issues 等）。
import fs from "node:fs";
import path from "node:path";

const dir = path.resolve(process.argv[2], "src/router/modules");
const files = fs.readdirSync(dir).filter((f) => f.endsWith(".ts"));
const routes = [];
for (const f of files) {
  const lines = fs.readFileSync(path.join(dir, f), "utf8").split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const pm = lines[i].match(/^\s*path:\s*["'`]([^"'`]+)["'`]/);
    if (!pm) continue;
    // 在随后 12 行（或下一个 path 前）找 name/title/showLink
    let name = "", title = "", showLink = "";
    for (let j = i + 1; j < Math.min(i + 13, lines.length); j++) {
      if (/^\s*path:\s*["'`]/.test(lines[j])) break;
      const nm = lines[j].match(/^\s*name:\s*["'`]([^"'`]+)["'`]/); if (nm) name = nm[1];
      const tm = lines[j].match(/title:\s*["'`]([^"'`]+)["'`]/); if (tm) title = tm[1];
      const sm = lines[j].match(/showLink:\s*(true|false)/); if (sm) showLink = sm[1];
    }
    routes.push({ module: f, path: pm[1], name, title, showLink });
  }
}
const paths = routes.map((r) => r.path);
const names = routes.map((r) => r.name).filter(Boolean);
const count = (a) => a.reduce((m, x) => ((m[x] ||= []), m), {});
const dupP = Object.entries(count(paths)).filter(([, v]) => v.length > 1);
const dupN = Object.entries(count(names)).filter(([, v]) => v.length > 1);
const out = {
  method: "line-scan v2 over src/router/modules/*.ts (covers nested children)",
  module_file_count: files.length,
  route_object_count: routes.length,
  path_count: new Set(paths).size,
  dynamic_param_routes: routes.filter((r) => r.path.includes(":")),
  duplicate_paths: Object.fromEntries(dupP),
  duplicate_names: Object.fromEntries(dupN),
  routes,
};
console.log(JSON.stringify(out, null, 1));
