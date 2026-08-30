<template>
  <div class="legend-filter" aria-label="图谱图例筛选">
    <div><strong>关系类型</strong><button v-for="item in relationItems" :key="item.value" :class="{ off: !relationTypes.includes(item.value) }" @click="toggle('relation', item.value)"><i :class="['line', item.line]" />{{ item.label }}</button></div>
    <div><strong>置信等级</strong><button v-for="item in confidenceItems" :key="item" :class="{ off: !confidences.includes(item) }" @click="toggle('confidence', item)">{{ item }}</button></div>
    <div><strong>图层</strong><button :class="{ off: !showReviewLayer }" @click="emit('update:showReviewLayer', !showReviewLayer)">D / 待审层</button></div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ relationTypes: string[]; confidences: string[]; showReviewLayer: boolean }>();
const emit = defineEmits<{
  "update:relationTypes": [value: string[]];
  "update:confidences": [value: string[]];
  "update:showReviewLayer": [value: boolean];
}>();
const relationItems = [
  { value: "formal", label: "正式", line: "solid" },
  { value: "candidate", label: "候选", line: "dashed" },
  { value: "dependency", label: "视图依赖", line: "dotted" }
];
const confidenceItems = ["A", "B", "C", "D"];
function toggle(kind: "relation" | "confidence", value: string) {
  const current = kind === "relation" ? props.relationTypes : props.confidences;
  const next = current.includes(value) ? current.filter(item => item !== value) : [...current, value];
  if (kind === "relation") emit("update:relationTypes", next);
  else emit("update:confidences", next);
}
</script>

<style scoped>
.legend-filter { display:flex; flex-wrap:wrap; gap:10px 18px; padding:8px 10px; border:1px solid #e2e8f0; border-radius:8px; background:#fff; font-size:12px; }
.legend-filter>div { display:flex; align-items:center; gap:6px; }
button { display:inline-flex; align-items:center; gap:5px; padding:3px 8px; border:1px solid #cbd5e1; border-radius:999px; background:#f8fafc; color:#334155; cursor:pointer; }
button.off { opacity:.35; filter:grayscale(1); }
.line { width:18px; border-top:2px solid #3f7cac; }
.line.dashed { border-top-style:dashed; }
.line.dotted { border-top-style:dotted; }
</style>
