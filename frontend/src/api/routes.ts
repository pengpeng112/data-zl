import { http } from "@/utils/http";

type Result = {
  success: boolean;
  data: Array<any>;
};

/**
 * 动态路由接口。
 * 本平台菜单来自前端静态 modules，后端暂无 /get-async-routes；
 * 请求失败或无数据时回落为空数组，避免登录后 initRouter 崩溃转圈。
 */
export const getAsyncRoutes = async (): Promise<Result> => {
  try {
    const res = await http.request<Result>("get", "/get-async-routes");
    const data = Array.isArray(res?.data) ? res.data : [];
    return { success: true, data };
  } catch {
    return { success: true, data: [] };
  }
};
