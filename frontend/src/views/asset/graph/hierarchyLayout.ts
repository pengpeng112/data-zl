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

/** Neo4j 式散布：小规模单环，较多节点用同心圆，保证相邻间距。 */
export function computeCircularSpreadPositions(
  nodes: HierarchyNodeLike[],
  options: { nodeSize?: number; gap?: number } = {}
): HierarchyLayoutResult {
  const ids = nodes.map(n => String(n.id));
  const n = ids.length;
  const nodeSize = Math.max(48, options.nodeSize ?? 160);
  const gap = Math.max(16, options.gap ?? 56);
  const pitch = nodeSize + gap;
  const positions = new Map<string, HierarchyPosition>();
  if (n === 0) return { positions, width: 960, height: 640 };
  if (n === 1) {
    positions.set(ids[0], { x: 480, y: 320 });
    return { positions, width: 960, height: 640 };
  }

  const rings: string[][] = [];
  const remaining = [...ids];
  let ringIndex = 0;
  while (remaining.length) {
    const radius = Math.max(pitch, (ringIndex + 1) * pitch);
    const capacity = Math.max(6, Math.floor((2 * Math.PI * radius) / pitch));
    rings.push(remaining.splice(0, capacity));
    ringIndex += 1;
  }

  rings.forEach((ring, ri) => {
    const radius = Math.max(pitch, (ri + 1) * pitch);
    const count = ring.length;
    const start = -Math.PI / 2;
    ring.forEach((id, i) => {
      const angle = start + (2 * Math.PI * i) / count;
      positions.set(id, {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius
      });
    });
  });

  const xs = [...positions.values()].map(p => p.x);
  const ys = [...positions.values()].map(p => p.y);
  const pad = nodeSize;
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const dx = pad - minX;
  const dy = pad - minY;
  positions.forEach(p => {
    p.x += dx;
    p.y += dy;
  });
  return {
    positions,
    width: Math.max(...xs) - minX + pad * 2,
    height: Math.max(...ys) - minY + pad * 2
  };
}

function distance(a: HierarchyPosition, b: HierarchyPosition) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

export function minSpreadDistance(positions: Map<string, HierarchyPosition>): number {
  const pts = [...positions.values()];
  let min = Number.POSITIVE_INFINITY;
  for (let i = 0; i < pts.length; i += 1) {
    for (let j = i + 1; j < pts.length; j += 1) {
      min = Math.min(min, distance(pts[i], pts[j]));
    }
  }
  return Number.isFinite(min) ? min : 0;
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
