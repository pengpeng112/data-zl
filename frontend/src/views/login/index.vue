<script setup lang="ts">
import Motion from "./utils/motion";
import { useRouter } from "vue-router";
import { message } from "@/utils/message";
import { loginRules, REGEXP_PWD } from "./utils/rule";
import { ref, reactive } from "vue";
import { debounce } from "@pureadmin/utils";
import { useNav } from "@/layout/hooks/useNav";
import { useEventListener } from "@vueuse/core";
import type { FormInstance } from "element-plus";
import { useLayout } from "@/layout/hooks/useLayout";
import { useUserStoreHook } from "@/store/modules/user";
import { initRouter, getTopMenu } from "@/router/utils";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import { useDataThemeChange } from "@/layout/hooks/useDataThemeChange";
import { getPublicStats } from "@/api/asset";

import dayIcon from "@/assets/svg/day.svg?component";
import darkIcon from "@/assets/svg/dark.svg?component";
import Lock from "~icons/ri/lock-fill";
import User from "~icons/ri/user-3-fill";

// 登录页展示指标：资产对象/治理关系从后端公开接口实时同步，质量规则保持文案
const commandMetrics = ref([
  { label: "资产对象", value: "-" },
  { label: "治理关系", value: "-" },
  { label: "质量规则", value: "运行中" }
]);

// 千分位格式化
function fmtNum(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return n.toLocaleString("zh-CN");
}

async function loadPublicStats() {
  try {
    const res = await getPublicStats();
    const d = res.data;
    commandMetrics.value = [
      { label: "资产对象", value: fmtNum(d.tables) },
      { label: "治理关系", value: fmtNum(d.confirmed_relations) },
      { label: "质量规则", value: "运行中" }
    ];
  } catch {
    // 接口不可用时保持占位“-”，不阻断登录
  }
}

const capabilityItems = ["源库只读探查", "关系图谱分析", "质量规则执行"];

defineOptions({
  name: "Login"
});

const router = useRouter();
const loading = ref(false);
const disabled = ref(false);
const ruleFormRef = ref<FormInstance>();

const { initStorage } = useLayout();
initStorage();

const { dataTheme, overallStyle, dataThemeChange } = useDataThemeChange();
dataThemeChange(overallStyle.value);
const { title, subTitle, getHospitalFullLogo } = useNav();

const ruleForm = reactive({
  username: "",
  password: ""
});

const mustChangeVisible = ref(false);
const changePwdForm = reactive({
  old_password: "",
  new_password: "",
  confirm_password: ""
});
const changePwdLoading = ref(false);

const onLogin = async (formEl: FormInstance | undefined) => {
  if (!formEl) return;
  await formEl.validate(valid => {
    if (valid) {
      loading.value = true;
      useUserStoreHook()
        .loginByUsername({
          username: ruleForm.username,
          password: ruleForm.password
        })
        .then(res => {
          if (res.success) {
            if (res.data?.must_change_password) {
              mustChangeVisible.value = true;
              message("首次登录请修改密码", { type: "warning" });
              return;
            }
            disabled.value = true;
            return initRouter()
              .then(() => {
                const top = getTopMenu(true);
                const path = top?.path || "/welcome";
                return router.push(path).then(() => {
                  message("登录成功", { type: "success" });
                });
              })
              .catch(() => {
                // 动态路由失败时仍进入首页，避免卡在登录转圈
                return router.push("/welcome").then(() => {
                  message("登录成功", { type: "success" });
                });
              })
              .finally(() => {
                disabled.value = false;
              });
          } else {
            message(res.message || "登录失败", { type: "error" });
          }
        })
        .catch((err: any) => {
          const status = err?.response?.status;
          const detail =
            err?.response?.data?.detail ||
            err?.response?.data?.message ||
            err?.message;
          if (status === 429) {
            message("尝试过于频繁，请稍后再试", { type: "error" });
          } else if (status === 401 || status === 403) {
            message("账号或密码错误，或账号已锁定", { type: "error" });
          } else if (!err?.response) {
            message("网络错误，无法连接服务器", { type: "error" });
          } else {
            message(detail || "登录失败", { type: "error" });
          }
        })
        .finally(() => (loading.value = false));
    }
  });
};

const submitChangePassword = async () => {
  if (!loginRules.password || !REGEXP_PWD.test(changePwdForm.new_password)) {
    message("密码格式应为8-18位数字、字母、符号的任意两种组合", {
      type: "error"
    });
    return;
  }
  if (changePwdForm.new_password !== changePwdForm.confirm_password) {
    message("两次输入的新密码不一致", { type: "error" });
    return;
  }
  changePwdLoading.value = true;
  try {
    const { changePasswordApi } = await import("@/api/user");
    await changePasswordApi({
      old_password: changePwdForm.old_password || ruleForm.password,
      new_password: changePwdForm.new_password
    });
    message("密码已修改，请使用新密码重新登录", { type: "success" });
    mustChangeVisible.value = false;
    useUserStoreHook().logOut();
  } catch (err: any) {
    const detail =
      err?.response?.data?.detail ||
      err?.response?.data?.message ||
      "修改密码失败";
    message(String(detail), { type: "error" });
  } finally {
    changePwdLoading.value = false;
  }
};

const immediateDebounce: any = debounce(
  formRef => onLogin(formRef),
  1000,
  true
);

useEventListener(document, "keydown", ({ code }) => {
  if (
    ["Enter", "NumpadEnter"].includes(code) &&
    !disabled.value &&
    !loading.value
  )
    immediateDebounce(ruleFormRef.value);
});

// 进入登录页即拉取真实资产/关系数（失败不阻断登录）
loadPublicStats();
</script>

<template>
  <main class="login-page select-none">
    <div class="login-bg-grid" />
    <div class="login-orb login-orb-a" />
    <div class="login-orb login-orb-b" />

    <div class="theme-switch">
      <el-switch
        v-model="dataTheme"
        inline-prompt
        :active-icon="dayIcon"
        :inactive-icon="darkIcon"
        @change="dataThemeChange"
      />
    </div>

    <section class="brand-panel">
      <Motion>
        <img
          class="hospital-logo"
          :src="getHospitalFullLogo()"
          alt="山东省第二人民医院"
        />
      </Motion>
      <Motion :delay="80">
        <div class="brand-copy">
          <p class="eyebrow">Hospital Data Asset Command Center</p>
          <h1>{{ title }} {{ subTitle }}</h1>
          <p class="brand-desc">
            让医院数据资产看得见、管得住、用得好，支撑源库探查、治理导入、质量分析与关系图谱协同运行。
          </p>
        </div>
      </Motion>
      <Motion :delay="160">
        <div class="metric-row">
          <div v-for="item in commandMetrics" :key="item.label" class="metric-item">
            <strong>{{ item.value }}</strong>
            <span>{{ item.label }}</span>
          </div>
        </div>
      </Motion>
      <Motion :delay="220">
        <div class="capability-row">
          <span v-for="item in capabilityItems" :key="item">{{ item }}</span>
        </div>
      </Motion>
    </section>

    <section class="login-card-wrap">
      <Motion :delay="120">
        <div class="login-card">
          <div class="login-card-header">
            <span class="card-kicker">安全登录</span>
            <h2>进入数据资产平台</h2>
            <p>使用平台账号登录，所有生产源库操作保持只读审计。</p>
          </div>

          <el-form
            ref="ruleFormRef"
            class="login-form"
            :model="ruleForm"
            :rules="loginRules"
            size="large"
          >
            <el-form-item
              :rules="[
                {
                  required: true,
                  message: '请输入账号',
                  trigger: 'blur'
                }
              ]"
              prop="username"
            >
              <el-input
                v-model="ruleForm.username"
                clearable
                placeholder="账号"
                :prefix-icon="useRenderIcon(User)"
              />
            </el-form-item>

            <el-form-item prop="password">
              <el-input
                v-model="ruleForm.password"
                clearable
                show-password
                placeholder="密码"
                :prefix-icon="useRenderIcon(Lock)"
              />
            </el-form-item>

            <el-button
              class="login-button"
              size="large"
              type="primary"
              :loading="loading"
              :disabled="disabled"
              @click="onLogin(ruleFormRef)"
            >
              登录
            </el-button>
          </el-form>
        </div>
      </Motion>
    </section>

    <el-dialog
      v-model="mustChangeVisible"
      title="首次登录修改密码"
      width="420px"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <el-form label-width="100px">
        <el-form-item label="原密码">
          <el-input
            v-model="changePwdForm.old_password"
            type="password"
            show-password
            placeholder="默认可用登录密码"
          />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="changePwdForm.new_password"
            type="password"
            show-password
            placeholder="8-18位，数字/字母/符号任意两类"
          />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input
            v-model="changePwdForm.confirm_password"
            type="password"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="changePwdLoading" @click="submitChangePassword">
          确认修改
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>

<style scoped>
@import url("@/style/login.css");
</style>

<style lang="scss" scoped>
:deep(.el-input-group__append, .el-input-group__prepend) {
  padding: 0;
}
</style>
