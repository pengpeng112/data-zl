# R3③ 深度（depth）控件选择器实验记录（文档性，171 §2 R3）

- 控件位置：`frontend/src/views/asset/components/GraphToolbar.vue:24`
- 控件类型：`el-segmented`（Element Plus 分段器），非 el-select/el-slider
- 选项：`depthOptions = [{1 跳},{2 跳},{3 跳}]`（GraphToolbar.vue:177），类型约束 `depth: 1 | 2 | 3`
- 交互行为：
  - `:disabled="!locate.physical_key"` —— 未聚焦节点时禁用（默认 overview 模式不可用）；
  - `@change="emit('load-chain')"` —— 切换档位即重查链路；
  - 默认值 depth=2（graph/index.vue:301），重置过滤器时回 2（index.vue:927）。
- 实验结论：现行 segmented 三档控件语义清晰、无歧义（1/2/3 跳互斥选择），**无需更换控件类型**；若后续要支持 >3 跳（后端 path 模式 max_hops 已支持 8），再评估改 el-input-number。
- GraphToolbar.vue 工作区无未提交改动（git diff 为空），本记录纯登记。
