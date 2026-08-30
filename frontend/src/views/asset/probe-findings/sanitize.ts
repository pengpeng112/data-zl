/**
 * 166 F4：evidence_sql / error_summary 渲染前脱敏管道（kimi#12）。
 *
 * 与后端 app/services/data_masking.sanitize_text 同规则的前端镜像：
 * 连接串/密码/令牌/长密钥材料折叠 + 空白折叠 + 长度上限。
 * 渲染一律走文本插值（Vue 自动转义），本仓禁 v-html——XSS 断言测试锁死。
 */

const SECRET_PATTERNS: RegExp[] = [
  /(password|passwd|pwd|token|secret|api[_-]?key)\s*[:=]\s*\S+/gi,
  /:\/\/[^\s/@:]+:[^\s/@:]+@/gi, // user:pass@host 连接串
  /(authorization|auth|bearer)\s*[:=]\s*\S+/gi,
  /(dsn|connect.?string|jdbc:oracle|postgresql:\/\/|mysql:\/\/|sqlserver:\/\/)[^\s;,)]+/gi,
  /\b(ak|sk|access_key|private_key)\b\s*[:=]\s*\S+/gi,
  /\b(params?|bind)\s*[:=]\s*\{[^}]{0,400}\}/gi,
  // 长 hex / base64 片段（签名内容、密钥材料）折叠
  /\b[A-Za-z0-9+/_-]{48,}={0,2}\b/g
];

export function sanitizeEvidenceText(raw: string | null | undefined, limit = 4000): string {
  if (!raw) return "";
  let cleaned = raw;
  for (const pattern of SECRET_PATTERNS) {
    cleaned = cleaned.replace(pattern, "[REDACTED]");
  }
  // 折叠纯空白为单个空格（保留 SQL 可读性的换行在 collapse 之外处理）
  cleaned = cleaned.replace(/[ \t]+/g, " ").trim();
  if (cleaned.length > limit) {
    cleaned = cleaned.slice(0, limit) + "...";
  }
  return cleaned;
}
