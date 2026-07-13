<script setup lang="ts">
import echarts from "@/plugins/echarts";
import ReEmptyState from "@/components/ReEmptyState/index.vue";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { EChartsCoreOption } from "echarts/core";
import type { PropType } from "vue";

const props = defineProps({
  option: {
    type: Object as PropType<EChartsCoreOption>,
    required: true
  },
  height: {
    type: String,
    default: "280px"
  },
  loading: {
    type: Boolean,
    default: false
  },
  empty: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ""
  },
  dark: {
    type: Boolean,
    default: true
  }
});

const chartEl = ref<HTMLDivElement>();
let chart: ReturnType<typeof echarts.init> | null = null;
let resizeObserver: ResizeObserver | null = null;

const renderChart = async () => {
  await nextTick();
  if (!chartEl.value || props.empty || props.error) return;
  if (!chart) chart = echarts.init(chartEl.value, "asset-platform");
  chart.setOption(props.option, true);
  if (props.loading) chart.showLoading();
  else chart.hideLoading();
};

onMounted(() => {
  renderChart();
  if (chartEl.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize());
    resizeObserver.observe(chartEl.value);
  }
});

watch(
  () => [props.option, props.loading, props.empty, props.error],
  () => renderChart(),
  { deep: true }
);

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="re-chart" :class="{ 'is-dark': dark }" :style="{ height }">
    <ReEmptyState
      v-if="error"
      title="图表加载失败"
      :description="error"
    />
    <ReEmptyState v-else-if="empty" title="暂无图表数据" />
    <div v-else ref="chartEl" class="chart-canvas" />
  </div>
</template>

<style scoped lang="scss">
.re-chart {
  position: relative;
  width: 100%;
  min-height: 180px;
}

.chart-canvas {
  width: 100%;
  height: 100%;
}

.is-dark :deep(.re-empty-state) {
  color: var(--dark-text-primary);

  h3 {
    color: var(--dark-text-primary);
  }

  p {
    color: var(--dark-text-secondary);
  }
}
</style>
