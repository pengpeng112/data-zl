function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function liveDisplayText(raw?: string | null): string {
  const text = String(raw || "").trim();
  if (!text) return "正在把所选问题发给院内模型…";
  if (text.startsWith("{") && !text.includes("【") && !text.includes("结论")) {
    return "正在整理成中文说明…";
  }
  return text;
}

export function renderReportHtml(raw?: string | null): string {
  const text = String(raw || "").replace(/\r\n/g, "\n").trim();
  if (!text) return "<p>暂无报告正文</p>";
  const lines = text.split("\n");
  const html: string[] = [];
  let inList = false;

  const closeList = () => {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  };

  const inline = (line: string) =>
    escapeHtml(line).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      closeList();
      continue;
    }
    const heading = trimmed.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      closeList();
      const level = Math.min(heading[1].length + 1, 4);
      html.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      continue;
    }
    if (/^[-*]\s+/.test(trimmed)) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${inline(trimmed.replace(/^[-*]\s+/, ""))}</li>`);
      continue;
    }
    closeList();
    html.push(`<p>${inline(trimmed)}</p>`);
  }
  closeList();
  return html.join("");
}

export function severityLabel(value?: string | null) {
  return ({ critical: "严重", major: "重要", minor: "一般", info: "提示" } as Record<string, string>)[String(value || "")] || value || "-";
}

export function statusLabel(value?: string | null) {
  return ({ open: "待处理", assigned: "已分派", acknowledged: "已确认", resolved: "已解决", ignored: "已忽略" } as Record<string, string>)[String(value || "")] || value || "-";
}

export function objectText(row: {
  table_name_cn?: string | null;
  table_name?: string | null;
  schema_name?: string | null;
  column_name?: string | null;
  related_table?: string | null;
  related_field?: string | null;
  target_display?: string | null;
  target_ref?: string | null;
  target_type?: string | null;
}) {
  const table = row.table_name_cn || row.table_name;
  if (table) {
    const left = [row.schema_name, table, row.column_name].filter(Boolean).join(".");
    if (row.related_table) {
      return `${left} → ${[row.related_table, row.related_field].filter(Boolean).join(".")}`;
    }
    return left;
  }
  if (row.target_display && row.target_display !== "-") return row.target_display;
  if (row.target_type === "relation") return row.target_ref || "关系级问题，未落到单表字段";
  return "规则级/目录级问题，没有单表字段";
}
