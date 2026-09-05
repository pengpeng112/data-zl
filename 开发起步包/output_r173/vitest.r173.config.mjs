import { fileURLToPath } from "node:url";
export default {
  test: {
    root: fileURLToPath(new URL(".", import.meta.url)),
    include: ["vtests/**/*.test.ts"],
    environment: "node",
  },
};
