export const CAPTURE_QUERY_VALUE = "1";

type CaptureQuery = Record<string, unknown>;

/**
 * 比赛/汇报截图模式仅改变页面外壳，不改变业务数据与权限。
 * 支持 `?capture=1`，同时保留 `?presentation=1` 兼容语义。
 */
export function isCompetitionCaptureQuery(
  query: CaptureQuery,
  locationSearch = ""
): boolean {
  const search = new URLSearchParams(locationSearch);
  return (
    query.capture === CAPTURE_QUERY_VALUE ||
    query.presentation === CAPTURE_QUERY_VALUE ||
    search.get("capture") === CAPTURE_QUERY_VALUE ||
    search.get("presentation") === CAPTURE_QUERY_VALUE
  );
}
