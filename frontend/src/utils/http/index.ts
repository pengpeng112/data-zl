import Axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type CustomParamsSerializer
} from "axios";
import type {
  PureHttpError,
  RequestMethods,
  PureHttpResponse,
  PureHttpRequestConfig
} from "./types.d";
import { stringify } from "qs";
import Cookies from "js-cookie";
import {
  getToken,
  formatToken,
  multipleTabsKey,
  removeToken
} from "@/utils/auth";
import { useUserStoreHook } from "@/store/modules/user";

function removeTokenQuietly() {
  try {
    removeToken();
  } catch {
    // ignore
  }
}

// 相关配置请参考：www.axios-js.com/zh-cn/docs/#axios-request-config-1

const defaultConfig: AxiosRequestConfig = {
  // 请求超时时间
  timeout: 10000,
  // Refresh Cookie 跨端口需要
  withCredentials: true,
  headers: {
    Accept: "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest"
  },
  // 数组格式参数序列化（https://github.com/axios/axios/issues/5142）
  paramsSerializer: {
    serialize: stringify as unknown as CustomParamsSerializer
  }
};

class PureHttp {
  constructor() {
    this.httpInterceptorsRequest();
    this.httpInterceptorsResponse();
  }

  /** `token`过期后，暂存待执行的请求 */
  private static requests = [];

  /** 防止重复刷新`token` */
  private static isRefreshing = false;

  /** 初始化配置对象 */
  private static initConfig: PureHttpRequestConfig = {};

  /** 保存当前`Axios`实例对象 */
  private static axiosInstance: AxiosInstance = Axios.create(defaultConfig);

  /** 重连原始请求；refresh 失败时用 reject 解除挂起，避免界面一直转圈 */
  private static retryOriginalRequest(config: PureHttpRequestConfig) {
    return new Promise((resolve, reject) => {
      PureHttp.requests.push((token: string | null, err?: unknown) => {
        if (!token) {
          reject(err || new Error("refresh failed"));
          return;
        }
        config.headers["Authorization"] = formatToken(token);
        resolve(config);
      });
    });
  }

  private static flushRefreshQueue(token: string | null, err?: unknown) {
    PureHttp.requests.forEach(cb => cb(token, err));
    PureHttp.requests = [];
  }

  /** 请求拦截 */
  private httpInterceptorsRequest(): void {
    PureHttp.axiosInstance.interceptors.request.use(
      async (config: PureHttpRequestConfig): Promise<any> => {
        // 优先判断post/get等方法是否传入回调，否则执行初始化设置等回调
        if (typeof config.beforeRequestCallback === "function") {
          config.beforeRequestCallback(config);
          return config;
        }
        if (PureHttp.initConfig.beforeRequestCallback) {
          PureHttp.initConfig.beforeRequestCallback(config);
          return config;
        }
        /** 请求白名单：登录/刷新不带 Access Token，避免死循环 */
        const whiteList = [
          "/api/v1/auth/login",
          "/api/v1/auth/refresh",
          "/login",
          "/refresh-token"
        ];
        const isWhite = whiteList.some(url => (config.url || "").includes(url));
        const devToken = import.meta.env.DEV
          ? import.meta.env.VITE_DEV_API_TOKEN
          : undefined;
        if (devToken && !config.headers.Authorization && !isWhite) {
          config.headers["Authorization"] = `Bearer ${devToken}`;
        }
        return isWhite
          ? config
          : new Promise(resolve => {
              const data = getToken();
              const now = new Date().getTime();
              const expiresTs = Number(data?.expires) || 0;
              const tokenExpired =
                !!data?.accessToken && expiresTs > 0 && expiresTs - now <= 0;
              const hasSessionHint = Boolean(
                Cookies.get(multipleTabsKey) || data?.username
              );
              if (data?.accessToken && !tokenExpired) {
                config.headers["Authorization"] = formatToken(data.accessToken);
                resolve(config);
                return;
              }
              // 页面刷新后续期：有会话标记但无内存 Token，或 Token 已过期
              if (
                (tokenExpired || (!data?.accessToken && hasSessionHint)) &&
                hasSessionHint
              ) {
                if (!PureHttp.isRefreshing) {
                  PureHttp.isRefreshing = true;
                  useUserStoreHook()
                    .handRefreshToken()
                    .then(res => {
                      const token = res.data?.accessToken;
                      if (!token) throw new Error("empty access token");
                      config.headers["Authorization"] = formatToken(token);
                      PureHttp.flushRefreshQueue(token);
                    })
                    .catch(err => {
                      PureHttp.flushRefreshQueue(null, err);
                      removeTokenQuietly();
                    })
                    .finally(() => {
                      PureHttp.isRefreshing = false;
                    });
                }
                resolve(PureHttp.retryOriginalRequest(config));
                return;
              }
              resolve(config);
            });
      },
      error => {
        return Promise.reject(error);
      }
    );
  }

  /** 响应拦截 */
  private httpInterceptorsResponse(): void {
    const instance = PureHttp.axiosInstance;
    instance.interceptors.response.use(
      (response: PureHttpResponse) => {
        const $config = response.config;
        if (typeof $config.beforeResponseCallback === "function") {
          $config.beforeResponseCallback(response);
          return response.data;
        }
        if (PureHttp.initConfig.beforeResponseCallback) {
          PureHttp.initConfig.beforeResponseCallback(response);
          return response.data;
        }
        return response.data;
      },
      (error: PureHttpError) => {
        const $error = error as PureHttpError & {
          config?: PureHttpRequestConfig & { _assetTokenRetry?: boolean };
        };
        $error.isCancelRequest = Axios.isCancel($error);
        const status = $error.response?.status;
        const config = $error.config;
        // 401：单次 refresh，失败回登录
        if (
          status === 401 &&
          config &&
          !config._assetTokenRetry &&
          !(config.url || "").includes("/api/v1/auth/login") &&
          !(config.url || "").includes("/api/v1/auth/refresh")
        ) {
          config._assetTokenRetry = true;
          if (!PureHttp.isRefreshing) {
            PureHttp.isRefreshing = true;
            return useUserStoreHook()
              .handRefreshToken()
              .then(res => {
                const token = res.data?.accessToken;
                if (!token) throw new Error("empty access token");
                if (!config.headers) {
                  config.headers = {} as any;
                }
                (config.headers as any)["Authorization"] = formatToken(token);
                PureHttp.flushRefreshQueue(token);
                return instance.request(config);
              })
              .catch(err => {
                PureHttp.flushRefreshQueue(null, err);
                try {
                  useUserStoreHook().logOut();
                } catch {
                  removeTokenQuietly();
                }
                return Promise.reject(err);
              })
              .finally(() => {
                PureHttp.isRefreshing = false;
              });
          }
          return PureHttp.retryOriginalRequest(config).then(cfg =>
            instance.request(cfg as PureHttpRequestConfig)
          );
        }
        if (status === 403) {
          // 无权限不循环刷新
          return Promise.reject($error);
        }
        return Promise.reject($error);
      }
    );
  }

  /** 通用请求工具函数 */
  public request<T>(
    method: RequestMethods,
    url: string,
    param?: AxiosRequestConfig,
    axiosConfig?: PureHttpRequestConfig
  ): Promise<T> {
    const config = {
      method,
      url,
      ...param,
      ...axiosConfig
    } as PureHttpRequestConfig;

    // 单独处理自定义请求/响应回调
    return new Promise((resolve, reject) => {
      PureHttp.axiosInstance
        .request(config)
        .then((response: undefined) => {
          resolve(response);
        })
        .catch(error => {
          reject(error);
        });
    });
  }

  /** 单独抽离的`post`工具函数 */
  public post<T, P>(
    url: string,
    params?: AxiosRequestConfig<P>,
    config?: PureHttpRequestConfig
  ): Promise<T> {
    return this.request<T>("post", url, params, config);
  }

  /** 单独抽离的`get`工具函数 */
  public get<T, P>(
    url: string,
    params?: AxiosRequestConfig<P>,
    config?: PureHttpRequestConfig
  ): Promise<T> {
    return this.request<T>("get", url, params, config);
  }

  public patch<T, P>(
    url: string,
    params?: AxiosRequestConfig<P>,
    config?: PureHttpRequestConfig
  ): Promise<T> {
    return this.request<T>("patch", url, params, config);
  }

  public put<T, P>(
    url: string,
    params?: AxiosRequestConfig<P>,
    config?: PureHttpRequestConfig
  ): Promise<T> {
    return this.request<T>("put", url, params, config);
  }

  public delete<T, P>(
    url: string,
    params?: AxiosRequestConfig<P>,
    config?: PureHttpRequestConfig
  ): Promise<T> {
    return this.request<T>("delete", url, params, config);
  }
}

export const http = new PureHttp();
