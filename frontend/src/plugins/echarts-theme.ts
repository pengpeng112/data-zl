import echarts from "@/plugins/echarts";

export const assetPlatformTheme = {
  color: [
    "#0EA5E9",
    "#0D9488",
    "#6366F1",
    "#F59E0B",
    "#E11D48",
    "#8B5CF6",
    "#14B8A6",
    "#F97316"
  ],
  backgroundColor: "transparent",
  textStyle: {
    fontFamily: "inherit"
  },
  legend: {
    textStyle: {
      color: "#94A3B8"
    }
  },
  tooltip: {
    backgroundColor: "rgba(15, 23, 42, 0.92)",
    borderColor: "rgba(148, 163, 184, 0.2)",
    borderRadius: 8,
    padding: 12,
    textStyle: {
      color: "#F1F5F9"
    },
    extraCssText:
      "backdrop-filter: blur(8px); box-shadow: 0 8px 24px rgba(0,0,0,0.25);"
  },
  grid: {
    left: 40,
    right: 20,
    top: 36,
    bottom: 28,
    containLabel: true
  },
  xAxis: {
    axisLine: {
      lineStyle: {
        color: "rgba(148, 163, 184, 0.24)"
      }
    },
    axisLabel: {
      color: "#94A3B8"
    },
    splitLine: {
      show: false
    }
  },
  yAxis: {
    axisLine: {
      show: false
    },
    axisLabel: {
      color: "#94A3B8"
    },
    splitLine: {
      lineStyle: {
        color: "rgba(148, 163, 184, 0.12)"
      }
    }
  }
};

echarts.registerTheme("asset-platform", assetPlatformTheme);

export default assetPlatformTheme;
