import { defineStore } from "pinia";
import {
  type userType,
  store,
  router,
  resetRouter,
  routerArrays,
  storageLocal
} from "../utils";
import {
  type UserResult,
  type RefreshTokenResult,
  getLogin,
  refreshTokenApi,
  logoutApi
} from "@/api/user";
import { useMultiTagsStoreHook } from "./multiTags";
import { getMyPermissions } from "@/api/permissions";
import { type DataInfo, setToken, removeToken, userKey } from "@/utils/auth";

export const useUserStore = defineStore("pure-user", {
  state: (): userType => ({
    avatar: storageLocal().getItem<DataInfo<number>>(userKey)?.avatar ?? "",
    username: storageLocal().getItem<DataInfo<number>>(userKey)?.username ?? "",
    nickname: storageLocal().getItem<DataInfo<number>>(userKey)?.nickname ?? "",
    roles: storageLocal().getItem<DataInfo<number>>(userKey)?.roles ?? [],
    permissions:
      storageLocal().getItem<DataInfo<number>>(userKey)?.permissions ?? [],
    isRemembered: false,
    loginDay: 7
  }),
  actions: {
    SET_AVATAR(avatar: string) {
      this.avatar = avatar;
    },
    SET_USERNAME(username: string) {
      this.username = username;
    },
    SET_NICKNAME(nickname: string) {
      this.nickname = nickname;
    },
    SET_ROLES(roles: Array<string>) {
      this.roles = roles;
    },
    SET_PERMS(permissions: Array<string>) {
      this.permissions = permissions;
    },
    async syncPermissionProfile() {
      try {
        const res = await getMyPermissions();
        const roles = res?.data?.roles ?? [];
        const permissions = res?.data?.permissions ?? [];
        if (!roles.length && !permissions.length) return;
        this.SET_ROLES(roles);
        this.SET_PERMS(permissions);
        const current: Partial<DataInfo<number>> =
          storageLocal().getItem<DataInfo<number>>(userKey) ?? {};
        storageLocal().setItem(userKey, {
          ...current,
          accessToken: "",
          username:
            res.data.user_identifier ?? current.username ?? this.username,
          roles,
          permissions
        });
      } catch {
        // Keep login payload if permission profile is unavailable.
      }
    },
    SET_ISREMEMBERED(bool: boolean) {
      this.isRemembered = bool;
    },
    SET_LOGINDAY(value: number) {
      this.loginDay = Number(value);
    },
    /** 登入 */
    async loginByUsername(data) {
      return new Promise<UserResult>((resolve, reject) => {
        getLogin(data)
          .then(async data => {
            const ok = data?.success === true || data?.code === 0;
            if (ok && data?.data) {
              setToken(data.data as any);
              await this.syncPermissionProfile();
              // normalize success flag for login page
              (data as UserResult).success = true;
            } else {
              (data as UserResult).success = false;
            }
            resolve(data);
          })
          .catch(error => {
            reject(error);
          });
      });
    },
    /** 登出（尽量调用后端撤销会话） */
    async logOut() {
      try {
        await logoutApi();
      } catch {
        // ignore network errors on logout
      }
      this.username = "";
      this.roles = [];
      this.permissions = [];
      removeToken();
      useMultiTagsStoreHook().handleTags("equal", [...routerArrays]);
      resetRouter();
      router.push("/login");
    },
    /** 刷新 token（Cookie + 单次） */
    async handRefreshToken(data?: object) {
      return new Promise<RefreshTokenResult>((resolve, reject) => {
        refreshTokenApi(data)
          .then(data => {
            const ok = data?.success === true || data?.code === 0;
            if (ok && data?.data) {
              setToken(data.data as any);
              (data as RefreshTokenResult).success = true;
              resolve(data);
            } else {
              reject(data);
            }
          })
          .catch(error => {
            reject(error);
          });
      });
    }
  }
});

export function useUserStoreHook() {
  return useUserStore(store);
}
