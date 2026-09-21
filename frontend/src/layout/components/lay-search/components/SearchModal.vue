<script setup lang="ts">
import { match } from "pinyin-pro";
import { getConfig } from "@/config";
import { useRouter } from "vue-router";
import SearchResult from "./SearchResult.vue";
import SearchFooter from "./SearchFooter.vue";
import { useNav } from "@/layout/hooks/useNav";
import SearchHistory from "./SearchHistory.vue";
import type { optionsItem, dragItem } from "../types";
import { ref, computed, shallowRef, watch } from "vue";
import { useDebounceFn, onKeyStroke } from "@vueuse/core";
import { usePermissionStoreHook } from "@/store/modules/permission";
import { cloneDeep, isAllEmpty } from "@pureadmin/utils";
import {
  purgeLegacyKeys,
  searchCollect,
  searchHistory,
  titleMatchesAlias
} from "@/utils/menuPreferences";
import SearchIcon from "~icons/ri/search-line";

interface Props {
  /** 弹窗显隐 */
  value: boolean;
}

interface Emits {
  (e: "update:value", val: boolean): void;
}

const { device } = useNav();
const emit = defineEmits<Emits>();
const props = withDefaults(defineProps<Props>(), {});

const router = useRouter();

const HISTORY_TYPE = "history";
const COLLECT_TYPE = "collect";
// 186 N2：历史/收藏改为按平台环境+用户+schema 隔离的键（utils/menuPreferences）
const historyStore = searchHistory;
const collectStore = searchCollect;

const keyword = ref("");
const resultRef = ref();
const historyRef = ref();
const scrollbarRef = ref();
const activePath = ref("");
const historyPath = ref("");
const resultOptions = shallowRef([]);
const historyOptions = shallowRef([]);
const handleSearch = useDebounceFn(search, 300);
const historyNum = getConfig().MenuSearchHistory;
const inputRef = ref<HTMLInputElement | null>(null);

/** 菜单树形结构 */
const menusData = computed(() => {
  return cloneDeep(usePermissionStoreHook().wholeMenus);
});

const show = computed({
  get() {
    return props.value;
  },
  set(val: boolean) {
    emit("update:value", val);
  }
});

watch(
  () => props.value,
  newValue => {
    if (newValue) getHistory();
  }
);

const showSearchResult = computed(() => {
  return keyword.value && resultOptions.value.length > 0;
});

const showSearchHistory = computed(() => {
  return !keyword.value && historyOptions.value.length > 0;
});

const showEmpty = computed(() => {
  return (
    (!keyword.value && historyOptions.value.length === 0) ||
    (keyword.value && resultOptions.value.length === 0)
  );
});

function getStorageItem(kind: "history" | "collect") {
  const list = kind === "history" ? historyStore.read() : collectStore.read();
  return Array.isArray(list) ? list : [];
}

function setStorageItem(kind: "history" | "collect", value) {
  if (kind === "history") historyStore.write(value);
  else collectStore.write(value);
}

/** 将菜单树形结构扁平化为一维数组，用于菜单查询；
 * 186 N2：附带归属分区标题（parentTitle）供结果显示 */
function flatTree(arr, parentTitle = "") {
  const res = [];
  function deep(arr, parentTitle) {
    arr.forEach(item => {
      if (item.meta && item.meta.parentTitle === undefined) {
        item.meta.parentTitle = parentTitle;
      }
      res.push(item);
      item.children && deep(item.children, item.meta?.title ?? parentTitle);
    });
  }
  deep(arr, parentTitle);
  return res;
}

/** 查询（186 N2：标题/拼音之外，旧中文名别名也命中） */
function search() {
  const flatMenusData = flatTree(menusData.value);
  const kw = keyword.value.trim();
  resultOptions.value = flatMenusData.filter(menu =>
    kw
      ? menu.meta?.title
          .toLocaleLowerCase()
          .includes(kw.toLocaleLowerCase()) ||
        titleMatchesAlias(menu.meta?.title ?? "", kw) ||
        !isAllEmpty(
          match(menu.meta?.title.toLocaleLowerCase(), kw.toLocaleLowerCase())
        )
      : false
  );
  activePath.value =
    resultOptions.value?.length > 0 ? resultOptions.value[0].path : "";
}

function handleClose() {
  show.value = false;
  /** 延时处理防止用户看到某些操作 */
  setTimeout(() => {
    resultOptions.value = [];
    historyPath.value = "";
    keyword.value = "";
  }, 200);
}

function scrollTo(index) {
  const ref = resultOptions.value.length ? resultRef.value : historyRef.value;
  const scrollTop = ref.handleScroll(index);
  scrollbarRef.value.setScrollTop(scrollTop);
}

/** 获取当前选项和路径 */
function getCurrentOptionsAndPath() {
  const isResultOptions = resultOptions.value.length > 0;
  const options = isResultOptions ? resultOptions.value : historyOptions.value;
  const currentPath = isResultOptions ? activePath.value : historyPath.value;
  return { options, currentPath, isResultOptions };
}

/** 更新路径并滚动到指定项 */
function updatePathAndScroll(newIndex, isResultOptions) {
  if (isResultOptions) {
    activePath.value = resultOptions.value[newIndex].path;
  } else {
    historyPath.value = historyOptions.value[newIndex].path;
  }
  scrollTo(newIndex);
}

/** key up */
function handleUp() {
  const { options, currentPath, isResultOptions } = getCurrentOptionsAndPath();
  if (options.length === 0) return;
  const index = options.findIndex(item => item.path === currentPath);
  const prevIndex = (index - 1 + options.length) % options.length;
  updatePathAndScroll(prevIndex, isResultOptions);
}

/** key down */
function handleDown() {
  const { options, currentPath, isResultOptions } = getCurrentOptionsAndPath();
  if (options.length === 0) return;
  const index = options.findIndex(item => item.path === currentPath);
  const nextIndex = (index + 1) % options.length;
  updatePathAndScroll(nextIndex, isResultOptions);
}

/** key enter */
function handleEnter() {
  const { options, currentPath, isResultOptions } = getCurrentOptionsAndPath();
  if (options.length === 0 || currentPath === "") return;
  const index = options.findIndex(item => item.path === currentPath);
  if (index === -1) return;
  if (isResultOptions) {
    saveHistory();
  } else {
    updateHistory();
  }
  router.push(options[index].path);
  handleClose();
}

/** 删除历史记录 */
function handleDelete(item) {
  const key = item.type === HISTORY_TYPE ? "history" : "collect";
  let list = getStorageItem(key);
  list = list.filter(listItem => listItem.path !== item.path);
  setStorageItem(key, list);
  getHistory();
}

/** 收藏历史记录 */
function handleCollect(item) {
  let searchHistoryList = getStorageItem("history");
  let searchCollectList = getStorageItem("collect");
  searchHistoryList = searchHistoryList.filter(
    historyItem => historyItem.path !== item.path
  );
  setStorageItem("history", searchHistoryList);
  if (!searchCollectList.some(collectItem => collectItem.path === item.path)) {
    searchCollectList.unshift({ ...item, type: COLLECT_TYPE });
    setStorageItem("collect", searchCollectList);
  }
  getHistory();
}

/** 存储搜索记录 */
function saveHistory() {
  const { path, meta } = resultOptions.value.find(
    item => item.path === activePath.value
  );
  const searchHistoryList = getStorageItem("history");
  const searchCollectList = getStorageItem("collect");
  const isCollected = searchCollectList.some(item => item.path === path);
  const existingIndex = searchHistoryList.findIndex(item => item.path === path);
  if (!isCollected) {
    if (existingIndex !== -1) searchHistoryList.splice(existingIndex, 1);
    if (searchHistoryList.length >= historyNum) searchHistoryList.pop();
    searchHistoryList.unshift({ path, meta, type: HISTORY_TYPE });
    setStorageItem("history", searchHistoryList);
  }
}

/** 更新存储的搜索记录 */
function updateHistory() {
  let searchHistoryList = getStorageItem("history");
  const historyIndex = searchHistoryList.findIndex(
    item => item.path === historyPath.value
  );
  if (historyIndex !== -1) {
    const [historyItem] = searchHistoryList.splice(historyIndex, 1);
    searchHistoryList.unshift(historyItem);
    setStorageItem("history", searchHistoryList);
  }
}

/** 获取本地历史记录（186 N2：与当前可访问路由求交，标题从当前 meta
 * 重建；权限撤回后失效项立即消失，不依赖重新登录） */
function getHistory() {
  purgeLegacyKeys();
  const accessible = flatTree(menusData.value);
  const byPath = new Map(accessible.map(item => [item.path, item]));
  const revalidate = list =>
    (Array.isArray(list) ? list : [])
      .filter(item => item?.path && byPath.has(item.path))
      .map(item => ({
        ...item,
        meta: {
          ...(item.meta ?? {}),
          ...byPath.get(item.path).meta
        }
      }));
  const searchHistoryList = revalidate(getStorageItem("history"));
  const searchCollectList = revalidate(getStorageItem("collect"));
  setStorageItem("history", searchHistoryList);
  setStorageItem("collect", searchCollectList);
  historyOptions.value = [...searchHistoryList, ...searchCollectList];
  historyPath.value = historyOptions.value[0]?.path;
}

/** 拖拽改变收藏顺序 */
function handleDrag(item: dragItem) {
  const searchCollectList = getStorageItem("collect");
  const [reorderedItem] = searchCollectList.splice(item.oldIndex, 1);
  searchCollectList.splice(item.newIndex, 0, reorderedItem);
  setStorageItem("collect", searchCollectList);
  historyOptions.value = [
    ...getStorageItem("history"),
    ...getStorageItem("collect")
  ];
  historyPath.value = reorderedItem.path;
}

onKeyStroke("Enter", handleEnter);
onKeyStroke("ArrowUp", handleUp);
onKeyStroke("ArrowDown", handleDown);
</script>

<template>
  <el-dialog
    v-model="show"
    top="5vh"
    class="pure-search-dialog"
    :show-close="false"
    :width="device === 'mobile' ? '80vw' : '40vw'"
    :before-close="handleClose"
    :style="{
      borderRadius: '6px'
    }"
    append-to-body
    @opened="inputRef.focus()"
    @closed="inputRef.blur()"
  >
    <el-input
      ref="inputRef"
      v-model="keyword"
      size="large"
      clearable
      placeholder="搜索菜单（支持拼音搜索）"
      @input="handleSearch"
    >
      <template #prefix>
        <IconifyIconOffline
          :icon="SearchIcon"
          class="text-primary w-[24px] h-[24px]"
        />
      </template>
    </el-input>
    <div class="search-content">
      <el-scrollbar ref="scrollbarRef" max-height="calc(90vh - 140px)">
        <el-empty v-if="showEmpty" description="暂无搜索结果" />
        <SearchHistory
          v-if="showSearchHistory"
          ref="historyRef"
          v-model:value="historyPath"
          :options="historyOptions"
          @click="handleEnter"
          @delete="handleDelete"
          @collect="handleCollect"
          @drag="handleDrag"
        />
        <SearchResult
          v-if="showSearchResult"
          ref="resultRef"
          v-model:value="activePath"
          :options="resultOptions"
          @click="handleEnter"
        />
      </el-scrollbar>
    </div>
    <template #footer>
      <SearchFooter :total="resultOptions.length" />
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.search-content {
  margin-top: 12px;
}
</style>
