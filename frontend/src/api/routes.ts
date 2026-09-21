import { http } from "@/utils/http";

type Result = {
  success: boolean;
  data: Array<any>;
};

/**
 * 动态路由接口。
 * 186 N3：本平台菜单来自前端静态 modules，后端从未提供 /get-async-routes。
 * 静态模式下直接返回空动态路由——不再对不存在的接口发起注定失败的请求
 * （E05：每次登录都会产生一条 404 噪声请求）。
 * 若未来启用后端菜单，删除此短路并恢复请求分支即可。
 */
export const getAsyncRoutes = async (): Promise<Result> => {
  if (typeof import.meta.env.VITE_ENABLE_ASYNC_ROUTES === "string") {
    // 显式开关隔离：只有配置了该环境变量才走动态请求（当前平台未支持）
    try {
      const res = await http.request<Result>("get", "/get-async-routes");
      const data = Array.isArray(res?.data) ? res.data : [];
      return { success: true, data };
    } catch {
      // 真实动态请求失败不包装成成功——保留故障可见性（区别于静态短路）
      return { success: false, data: [] };
    }
  }
  return { success: true, data: [] };
};
