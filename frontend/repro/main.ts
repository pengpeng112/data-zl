import { createApp, h } from "vue";
import AdvancedRelationGraph from "@/views/asset/components/AdvancedRelationGraph.vue";
import RelationGraph from "@/views/asset/components/RelationGraph.vue";

declare global {
  interface Window {
    __repro: Record<string, unknown>;
  }
}

window.__repro = { mounted: false, renderError: false, engine: "" };

const params = new URLSearchParams(location.search);
const engine = params.get("engine") === "svg" ? "svg" : "g6";
window.__repro.engine = engine;

async function boot() {
  const res = await fetch("./graph_prod_sample.json");
  const payload = await res.json();
  const data = payload.graph.data;
  const component = engine === "svg" ? RelationGraph : AdvancedRelationGraph;
  const app = createApp({
    render() {
      return h(component as never, {
        nodes: data.nodes,
        edges: data.edges,
        height: "620px",
        groupBy: "schema",
        layoutMode: "layered",
        viewMode: "table",
        onRenderError: () => {
          window.__repro.renderError = true;
        }
      });
    }
  });
  app.mount("#app");
  window.__repro.mounted = true;
  window.__repro.nodeCount = data.nodes.length;
  window.__repro.edgeCount = data.edges.length;
}

boot().catch(err => {
  window.__repro.bootError = String(err && (err.stack || err.message || err));
});
