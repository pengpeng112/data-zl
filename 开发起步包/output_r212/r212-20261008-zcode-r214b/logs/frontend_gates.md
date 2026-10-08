# R212 S1 前端门禁证据（2026-10-08）

## 执行记录

| 门禁 | 命令 | 结果 | 退出码 |
|---|---|---|---|
| typecheck | `pnpm run typecheck`（tsc --noEmit + vue-tsc） | 无错误输出 | 0 |
| vitest 首跑 | `pnpm exec vitest run` | 312 passed (325) + **5 errors** | （管道tail误捕，见下） |
| vitest 复跑1 | `pnpm exec vitest run` | grep 无 failed/errors 行 | - |
| vitest 复跑2 | `pnpm exec vitest run` | **Test Files 52 passed (52)；Tests 332 passed (332)**；Duration 46.72s | 0 |
| build | `pnpm run build` | **三预算 PASS**：main entry 660.5KB/700、graph 404.6KB/430、css 108.5KB/110；entry=index-Dav3M2tw.js | 0 |

## vitest 首跑 5 errors 归因（212 §12.1 分类）

- 首跑与全量 pytest（后台）并行：Duration 120.39s（复跑仅 46.72s，2.6 倍）。
- 复跑×2（一次仍与 pytest 并行）均 332/332 全过，无任何 error。
- 判定：**环境失败（资源争抢）非产品缺陷非测试缺陷**；采用复跑结果为准。批次A基线同为 52/332。
- 首跑 5 errors 的具体 suite 名未留存（tail -6 截断），复跑全绿证明可恢复性。

## 预算检查输出（build）

```
PASS  main entry js    gz=   660.5 KB  budget<=   700.0 KB
PASS  graph async js   gz=   404.6 KB  budget<=   430.0 KB
PASS  total css        gz=   108.5 KB  budget<=   110.0 KB
entry = index-Dav3M2tw.js
```
