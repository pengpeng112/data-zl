/**
 * 153 F6：分页列表五件套 + 请求序号守卫（试点 6 页：dict/general、tables、
 * relation-review、sync-diffs×2、relation-rates）。
 *
 * 五件套 = items / total / page / loading / loadData；附带：
 * - doSearch：搜索入口统一重置 page=1（E6 语义对齐）；
 * - 请求序号守卫：并发触发时仅最后一次请求的结果生效（E7 语义对齐）；
 * - 错误处理：catch 后经 extractErrorDetail（脱敏）提示，可用 onError 覆盖。
 */
import { ref, type Ref } from "vue";
import { ElMessage } from "element-plus";
import { extractErrorDetail } from "@/utils/errorMessage";

export interface PagedListOptions<T, P extends { page: number; page_size: number }> {
  /** 取数函数：接收含 page/page_size 的查询参数，返回 { items, total }。 */
  fetcher: (params: P) => Promise<{ items: T[]; total: number }>;
  /** 附加查询参数（不含分页字段）。 */
  extraParams?: () => Partial<P>;
  /** 默认错误提示文案。 */
  errorText?: string;
  /** 覆盖默认错误处理（返回 false 时不走默认提示）。 */
  onError?: (error: unknown) => boolean | void;
}

export function usePagedList<T, P extends { page: number; page_size: number }>(
  options: PagedListOptions<T, P> & { pageSize?: number },
) {
  const items: Ref<T[]> = ref([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(options.pageSize ?? 20);
  const loading = ref(false);
  let seq = 0;

  async function loadData(targetPage?: number) {
    if (targetPage !== undefined) page.value = targetPage;
    const current = ++seq;
    loading.value = true;
    try {
      const extra = (options.extraParams?.() ?? {}) as Partial<P>;
      const res = await options.fetcher({
        ...extra,
        page: page.value,
        page_size: pageSize.value,
      } as P);
      if (current !== seq) return;
      items.value = res.items || [];
      total.value = res.total || 0;
    } catch (error) {
      if (current !== seq) return;
      const handled = options.onError?.(error);
      if (handled !== false) {
        ElMessage.error(extractErrorDetail(error, options.errorText ?? "列表加载失败"));
      }
    } finally {
      if (current === seq) {
        loading.value = false;
      }
    }
  }

  function doSearch() {
    page.value = 1;
    loadData();
  }

  return { items, total, page, pageSize, loading, loadData, doSearch };
}
