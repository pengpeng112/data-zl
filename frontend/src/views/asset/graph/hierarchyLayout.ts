/**
 * 129号：分层树状布局（业务系统 → 数据连接 → Schema → 表 逐级展开）。
 *
 * G6 版与 SVG 版共用同一套坐标算法，保证两种引擎下分层效果一致：
 * - 包含边（relation_type === "hierarchy"）决定树的父子关系与层深
 * - 根节点（无包含父节点）在第 0 层，子节点逐层向下
 * - 层内顺序按父节点先序排列（同一父节点的子节点相邻），各层水平居中
 * - 关系边（非包含边）不参与分层，仅作为同层/跨层连接展示
 */

export interface HierarchyNodeLike {
  id: string | number;
}

export interface HierarchyEdgeLike {
  source: string | number;
  target: string | number;
  relation_type?: string | null;
}

export interface HierarchyPosition {
  x: number;
  y: number;
}

export interface HierarchyLayoutResult {
  positions: Map<string, HierarchyPosition>;
  width: number;
  height: number;
}

export function computeHierarchyPositions(
  nodes: HierarchyNodeLike[],
  edges: HierarchyEdgeLike[],
  options: { xGap?: number; yGap?: number; topMargin?: number; maxPerRow?: number } = {}
): HierarchyLayoutResult {
  const xGap = options.xGap ?? 200;
  const yGap = options.yGap ?? 150;
  const topMargin = options.topMargin ?? 80;
  // 129号：单层节点过多时折行（如表层 80 张表），避免整行过宽导致视口只露出中间几个节点
  const maxPerRow = Math.max(1, options.maxPerRow ?? 12);

  const ids = nodes.map(n => String(n.id));
  const idSet = new Set(ids);

  // 包含关系树
  const children = new Map<string, string[]>();
  const hasParent = new Set<string>();
  edges.forEach(edge => {
    if (edge.relation_type !== "hierarchy") return;
    const s = String(edge.source);
    const t = String(edge.target);
    if (!idSet.has(s) || !idSet.has(t) || s === t) return;
    if (!children.has(s)) children.set(s, []);
    children.get(s)!.push(t);
    hasParent.add(t);
  });

  const roots = ids.filter(id => !hasParent.has(id));

  // 层深：从各根节点 BFS（ containment 是森林；visited 防御成环数据）
  const depth = new Map<string, number>();
  const queue: Array<[string, number]> = roots.map(id => [id, 0]);
  while (queue.length) {
    const [id, d] = queue.shift()!;
    if (depth.has(id) && depth.get(id)! >= d) continue;
    depth.set(id, d);
    (children.get(id) || []).forEach(c => queue.push([c, d + 1]));
  }
  // 成环/不可达节点兜底到第 0 层
  ids.forEach(id => {
    if (!depth.has(id)) depth.set(id, 0);
  });

  // 层内顺序：先序遍历（父先子后、同父相邻）
  const ordered: string[] = [];
  const visit = (id: string) => {
    ordered.push(id);
    (children.get(id) || []).forEach(visit);
  };
  roots.forEach(visit);
  ids.forEach(id => {
    if (!ordered.includes(id)) ordered.push(id);
  });
  const orderIndex = new Map(ordered.map((id, i) => [id, i] as const));

  const layers = new Map<number, string[]>();
  depth.forEach((d, id) => {
    if (!layers.has(d)) layers.set(d, []);
    layers.get(d)!.push(id);
  });
  layers.forEach(list => list.sort((a, b) => (orderIndex.get(a) ?? 0) - (orderIndex.get(b) ?? 0)));

  const maxCount = Math.max(1, ...Array.from(layers.values()).map(l => l.length));
  const perRow = Math.min(maxCount, maxPerRow);
  const totalWidth = perRow * xGap;

  // 逐层落位：超过 perRow 的层折成多个视觉行（同层内折行，行高相同）
  const positions = new Map<string, HierarchyPosition>();
  let y = topMargin;
  const sortedDepths = Array.from(layers.keys()).sort((a, b) => a - b);
  sortedDepths.forEach(d => {
    const list = layers.get(d)!;
    for (let i = 0; i < list.length; i += perRow) {
      const row = list.slice(i, i + perRow);
      const rowWidth = row.length * xGap;
      const startX = (totalWidth - rowWidth) / 2 + xGap / 2;
      row.forEach((id, j) => {
        positions.set(id, { x: startX + j * xGap, y });
      });
      y += yGap;
    }
  });

  return { positions, width: totalWidth + 100, height: y + 40 };
}
