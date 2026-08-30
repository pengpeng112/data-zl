/**
 * 166 D1：测试专用 localStorage 内存实现。
 *
 * 本机 Node 22+ 注入了原生 globalThis.localStorage（--localstorage-file 警告），
 * 它在 vitest jsdom 环境里没有 getItem 等方法，遮蔽了 jsdom 实现；任何导入期
 * 触碰 localStorage 的模块链（pinia→@vue/devtools-kit）都会 TypeError。
 * 在测试文件**首个 import** 本模块即可恢复标准行为。
 */
export function installMemoryLocalStorage(): void {
  const store = new Map<string, string>();
  const impl: Storage = {
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
    clear: () => {
      store.clear();
    },
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size;
    }
  } as Storage;
  Object.defineProperty(globalThis, "localStorage", {
    value: impl,
    configurable: true,
    writable: true
  });
}

installMemoryLocalStorage();
