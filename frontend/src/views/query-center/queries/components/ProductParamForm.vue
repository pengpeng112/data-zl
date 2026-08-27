<template>
  <div class="product-param-form">
    <el-form
      v-if="fields.length"
      ref="formRef"
      :model="model"
      label-width="140px"
      size="small"
    >
      <el-form-item
        v-for="field in fields"
        :key="field.name"
        :label="field.label"
        :prop="field.name"
        :rules="field.rules"
      >
        <el-date-picker
          v-if="field.type === 'date'"
          v-model="model[field.name]"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          style="width: 100%"
        />
        <el-date-picker
          v-else-if="field.type === 'month'"
          v-model="model[field.name]"
          type="month"
          value-format="YYYY-MM"
          placeholder="选择月份"
          style="width: 100%"
        />
        <el-select
          v-else-if="field.type === 'enum'"
          v-model="model[field.name]"
          placeholder="请选择"
          style="width: 100%"
        >
          <el-option
            v-for="opt in field.options"
            :key="String(opt)"
            :label="String(opt)"
            :value="opt"
          />
        </el-select>
        <el-input-number
          v-else-if="field.type === 'number'"
          v-model="model[field.name]"
          :min="field.minimum"
          :max="field.maximum"
          style="width: 100%"
        />
        <el-input
          v-else
          v-model="model[field.name]"
          :placeholder="`请输入${field.label}`"
        />
      </el-form-item>
    </el-form>
    <el-empty
      v-else
      description="该产品无参数，可直接执行"
      :image-size="60"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import type { FormInstance } from "element-plus";

interface ParamField {
  name: string;
  label: string;
  type: "string" | "number" | "date" | "month" | "enum";
  required: boolean;
  options?: Array<string | number>;
  minimum?: number;
  maximum?: number;
  rules: Array<Record<string, unknown>>;
}

const props = defineProps<{
  parameterSchema?: Record<string, unknown> | null;
}>();

const emit = defineEmits<{ (e: "validation", valid: boolean): void }>();

const formRef = ref<FormInstance>();
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const model = reactive<Record<string, any>>({});

const fields = computed<ParamField[]>(() => {
  const schema = props.parameterSchema;
  if (!schema || typeof schema !== "object") return [];
  const props_ = (schema as { properties?: Record<string, Record<string, unknown>> }).properties ?? {};
  const required = new Set(((schema as { required?: string[] }).required ?? []) as string[]);
  return Object.entries(props_).map(([name, spec]) => {
    const type = String(spec.type ?? "string");
    let kind: ParamField["type"] = "string";
    if (type === "integer" || type === "number") kind = "number";
    else if (Array.isArray(spec.enum) && spec.enum.length) kind = "enum";
    else if (/date/.test(String(spec.format ?? ""))) kind = "date";
    else if (/month|period/.test(name.toLowerCase())) kind = "month";
    const rules: Array<Record<string, unknown>> = [];
    if (required.has(name) || spec.required) {
      rules.push({ required: true, message: `${name} 为必填项`, trigger: "blur" });
    }
    return {
      name,
      label: String(spec.title ?? name),
      type: kind,
      required: required.has(name) || Boolean(spec.required),
      options: Array.isArray(spec.enum) ? (spec.enum as Array<string | number>) : undefined,
      minimum: typeof spec.minimum === "number" ? spec.minimum : undefined,
      maximum: typeof spec.maximum === "number" ? spec.maximum : undefined,
      rules,
    } satisfies ParamField;
  });
});

watch(
  fields,
  (next) => {
    for (const f of next) {
      if (!(f.name in model)) model[f.name] = undefined;
    }
  },
  { immediate: true }
);

async function validate(): Promise<boolean> {
  if (!formRef.value || !fields.value.length) {
    emit("validation", true);
    return true;
  }
  const ok = await formRef.value.validate().then(() => true).catch(() => false);
  emit("validation", ok);
  return ok;
}

function getValues(): Record<string, unknown> {
  return { ...model };
}

defineExpose({ validate, getValues });
</script>
