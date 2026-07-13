<script setup lang="ts">
import { getTopMenu } from "@/router/utils";
import { useNav } from "@/layout/hooks/useNav";

defineProps({
  collapse: Boolean
});

const { title, subTitle, getHospitalEmblem } = useNav();
</script>

<template>
  <div class="sidebar-logo-container" :class="{ collapses: collapse }">
    <transition name="sidebarLogoFade">
      <router-link
        v-if="collapse"
        key="collapse"
        :title="`${title} · ${subTitle}`"
        class="sidebar-logo-link"
        :to="getTopMenu()?.path ?? '/'"
      >
        <img :src="getHospitalEmblem()" alt="logo" />
      </router-link>
      <router-link
        v-else
        key="expand"
        :title="`${title} · ${subTitle}`"
        class="sidebar-logo-link"
        :to="getTopMenu()?.path ?? '/'"
      >
        <img :src="getHospitalEmblem()" alt="logo" />
        <div class="sidebar-title-wrap">
          <span class="sidebar-title">{{ title }}</span>
          <span class="sidebar-subtitle">{{ subTitle }}</span>
        </div>
      </router-link>
    </transition>
  </div>
</template>

<style lang="scss" scoped>
.sidebar-logo-container {
  position: relative;
  width: 100%;
  height: 48px;
  overflow: hidden;

  .sidebar-logo-link {
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    height: 100%;
    padding-left: 10px;

    img {
      display: inline-block;
      height: 32px;
      flex-shrink: 0;
    }

    .sidebar-title-wrap {
      display: inline-flex;
      flex-direction: column;
      justify-content: center;
      height: 32px;
      margin-left: 10px;
      overflow: hidden;
    }

    .sidebar-title {
      height: 18px;
      overflow: hidden;
      text-overflow: ellipsis;
      font-size: 14px;
      font-weight: 600;
      line-height: 18px;
      color: var(--pure-theme-sub-menu-active-text);
      white-space: nowrap;
    }

    .sidebar-subtitle {
      height: 14px;
      overflow: hidden;
      font-size: 12px;
      font-weight: 400;
      line-height: 14px;
      color: var(--pure-theme-sub-menu-text);
      opacity: 0.7;
      white-space: nowrap;
    }
  }

  /** 折叠态：居中显示院徽 */
  &.collapses {
    .sidebar-logo-link {
      justify-content: center;
      padding-left: 0;

      img {
        height: 28px;
      }
    }
  }
}
</style>
