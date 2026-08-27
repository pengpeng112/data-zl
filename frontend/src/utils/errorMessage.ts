/**
 * Unified, sanitized error detail extraction (146 D1).
 *
 * Order: response.data.detail -> response.data.message -> response.data.error_summary_masked
 * -> error.message. Credential-looking fragments are masked before display.
 */

const SENSITIVE_PATTERNS: RegExp[] = [
  /(password|passwd|pwd|secret|token|api[_-]?key)\s*[=:]\s*["']?[^\s"',;]+/gi,
  /\b(?:bearer|basic)\s+[a-z0-9\-._~+/]+=*/gi,
  /postgres(?:ql)?(?:\+\w+)?:\/\/[^\s@]+@[^\s]+/gi,
  /[a-f0-9]{32,}/gi
];

const MAX_LENGTH = 300;

export function maskSensitiveText(text: string, limit = MAX_LENGTH): string {
  let masked = String(text ?? "");
  for (const pattern of SENSITIVE_PATTERNS) {
    masked = masked.replace(pattern, match => {
      const key = match.split(/[=:]/)[0];
      return `${key}=***`;
    });
  }
  if (masked.length > limit) {
    masked = `${masked.slice(0, limit)}…`;
  }
  return masked;
}

interface ErrorLike {
  message?: unknown;
  response?: {
    data?: {
      detail?: unknown;
      message?: unknown;
      error_summary_masked?: unknown;
    };
  };
}

function asText(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value;
  if (value && typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return null;
    }
  }
  return null;
}

/** Extract a user-safe detail message from an HTTP/unknown error. */
export function extractErrorDetail(error: unknown, fallback = "操作失败，请稍后重试"): string {
  const err = (error || {}) as ErrorLike;
  const data = err.response?.data ?? {};
  const raw =
    asText(data.detail)
    ?? asText(data.message)
    ?? asText(data.error_summary_masked)
    ?? asText(err.message);
  if (!raw) return fallback;
  return maskSensitiveText(raw) || fallback;
}

/** Distinguish expected cancellations/downgrades from real failures. */
export function isExpectedQuietError(error: unknown): boolean {
  const message = String((error as ErrorLike)?.message ?? "");
  return /cancel|abort/i.test(message);
}
