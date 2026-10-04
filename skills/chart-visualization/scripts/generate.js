#!/usr/bin/env node

const fs = require("fs");

// Chart type mapping, consistent with src/utils/callTool.ts
const CHART_TYPE_MAP = {
  generate_area_chart: "area",
  generate_bar_chart: "bar",
  generate_boxplot_chart: "boxplot",
  generate_column_chart: "column",
  generate_district_map: "district-map",
  generate_dual_axes_chart: "dual-axes",
  generate_fishbone_diagram: "fishbone-diagram",
  generate_flow_diagram: "flow-diagram",
  generate_funnel_chart: "funnel",
  generate_histogram_chart: "histogram",
  generate_line_chart: "line",
  generate_liquid_chart: "liquid",
  generate_mind_map: "mind-map",
  generate_network_graph: "network-graph",
  generate_organization_chart: "organization-chart",
  generate_path_map: "path-map",
  generate_pie_chart: "pie",
  generate_pin_map: "pin-map",
  generate_radar_chart: "radar",
  generate_sankey_chart: "sankey",
  generate_scatter_chart: "scatter",
  generate_treemap_chart: "treemap",
  generate_venn_chart: "venn",
  generate_violin_chart: "violin",
  generate_word_cloud_chart: "word-cloud",
};

function getVisRequestServer() {
  return (
    process.env.VIS_REQUEST_SERVER ||
    "https://antv-studio.alipay.com/api/gpt-vis"
  );
}

function getServiceIdentifier() {
  return process.env.SERVICE_ID;
}

async function httpPost(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }

  return response.json();
}

async function generateChartUrl(chartType, options) {
  const url = getVisRequestServer();
  const payload = {
    type: chartType,
    source: "chart-visualization-creator",
    ...options,
  };

  const data = await httpPost(url, payload);

  if (!data.success) {
    throw new Error(data.errorMessage || "Unknown error");
  }

  return data.resultObj;
}

async function generateMap(tool, inputData) {
  const url = getVisRequestServer();
  const payload = {
    serviceId: getServiceIdentifier(),
    tool,
    input: inputData,
    source: "chart-visualization-creator",
  };

  const data = await httpPost(url, payload);

  if (!data.success) {
    throw new Error(data.errorMessage || "Unknown error");
  }

  return data.resultObj;
}

async function main() {
  if (process.argv.length < 3) {
    console.error("Usage: node generate.js <spec_json_or_file>");
    process.exit(1);
  }

  const specArg = process.argv[2];
  let spec;

  try {
    if (fs.existsSync(specArg)) {
      const fileContent = fs.readFileSync(specArg, "utf-8");
      spec = JSON.parse(fileContent);
    } else {
      spec = JSON.parse(specArg);
    }
  } catch (e) {
    console.error(`Error parsing spec: ${e.message}`);
    process.exit(1);
  }

  const specs = Array.isArray(spec) ? spec : [spec];

  for (const item of specs) {
    const tool = item.tool;
    const args = item.args || {};

    if (!tool) {
      console.error(
        `Error: 'tool' field missing in spec: ${JSON.stringify(item)}`,
      );
      continue;
    }

    const chartType = CHART_TYPE_MAP[tool];
    if (!chartType) {
      console.error(`Error: Unknown tool '${tool}'`);
      continue;
    }

    const isMapChartTool = [
      "generate_district_map",
      "generate_path_map",
      "generate_pin_map",
    ].includes(tool);

    try {
      // 饼图：确保每条数据有 category 字段（AntV 不识别 name）；总和不足 100 时补齐"其他"
      if (chartType === "pie" && Array.isArray(args.data)) {
        args.data = args.data.map((item) => {
          if (item.category === undefined && item.name !== undefined) {
            const { name, ...rest } = item;
            return { ...rest, category: name };
          }
          return item;
        });
        const total = args.data.reduce((sum, item) => sum + (item.value || 0), 0);
        if (total > 0 && total < 99.5 && total < 100) {
          args.data.push({ category: "其他", value: +(100 - total).toFixed(1) });
        }
      }

      // 雷达图：AntV 要求每条数据必须带 group 字段，缺失时自动补充
      if (chartType === "radar" && Array.isArray(args.data)) {
        const hasGroup = args.data.some(
          (item) => item.group !== undefined && item.group !== null
        );
        if (!hasGroup) {
          args.data = args.data.map((item) => ({
            ...item,
            group: item.group ?? "default",
          }));
        }
      }

      // 柱状图：AntV 要求 {category, value} 格式
      // LLM 有时生成 {time/month/date, value/return} 等非标准字段名
      if (chartType === "column" && Array.isArray(args.data) && args.data.length > 0) {
        const hasCategory = args.data.some((item) => item.category !== undefined);
        if (!hasCategory) {
          args.data = args.data.map((item) => {
            // 找 category 替代字段
            const catKey = Object.keys(item).find((k) =>
              /^(category|cat|label|name|月份|时间|x)$/i.test(k) ||
              (typeof item[k] === "string" && /^\d{4}[-/]\d{2}/.test(item[k]))
            );
            // 找 value 替代字段
            const valKey = Object.keys(item).find((k) =>
              /^(value|val|y|收益|return|return_rate)$/i.test(k)
            );
            const numericKeys = catKey
              ? Object.keys(item).filter(
                  (k) => k !== catKey && typeof item[k] === "number" && isFinite(item[k])
                )
              : [];
            const category = catKey ? item[catKey] : String(args.data.indexOf(item) + 1);
            const value = valKey ? item[valKey] : (numericKeys[0] ? item[numericKeys[0]] : 0);
            const group = item.group;
            return group !== undefined
              ? { category, value, group }
              : { category, value };
          });
        }
      }

      // 折线图/面积图：AntV 要求 long format {time, value, group}
      // LLM 有时生成 wide format [{date, 收盘价: 10, MA5: 9.8, ...}]，需要转为 long format
      if ((chartType === "line" || chartType === "area") && Array.isArray(args.data) && args.data.length > 0) {
        const hasValue = args.data.some((item) => item.value !== undefined);
        if (!hasValue) {
          const sample = args.data[0];
          // 找 time/date 字段
          const timeKey = Object.keys(sample).find((k) =>
            /^(time|date|日期|时间|x)$/i.test(k) ||
            (typeof sample[k] === "string" && /^\d{4}[-/]\d{2}/.test(sample[k]))
          );
          // 找数值字段（即各系列）
          const numericKeys = Object.keys(sample).filter(
            (k) => k !== timeKey && typeof sample[k] === "number" && isFinite(sample[k])
          );
          if (timeKey && numericKeys.length > 0) {
            const normalized = [];
            for (const item of args.data) {
              const t = item[timeKey];
              for (const key of numericKeys) {
                normalized.push({ time: t, value: item[key], group: key });
              }
            }
            args.data = normalized;
          }
        }
      }

      // 双轴图：AntV 要求 series 必须包含至少一个 column 类型，全是 line 会报错
      // 自动将第一条 line 改为 column；同时将 name 转为 axisYTitle（name 会导致报错）
      if (chartType === "dual-axes" && Array.isArray(args.series)) {
        const hasColumn = args.series.some((s) => s.type === "column");
        if (!hasColumn && args.series.length >= 1) {
          args.series[0] = { ...args.series[0], type: "column" };
        }
        for (let i = 0; i < args.series.length; i++) {
          const s = args.series[i];
          if (s.name && !s.axisYTitle) {
            args.series[i] = { ...s, axisYTitle: s.name };
            delete args.series[i].name;
          }
        }
      }

      if (isMapChartTool) {
        const result = await generateMap(tool, args);
        if (result && result.content) {
          for (const contentItem of result.content) {
            if (contentItem.type === "text") {
              console.log(contentItem.text);
            }
          }
        } else {
          console.log(JSON.stringify(result));
        }
      } else {
        const url = await generateChartUrl(chartType, args);
        console.log(url);
      }
    } catch (e) {
      console.error(`Error generating chart for ${tool}: ${e.message}`);
    }
  }
}

if (require.main === module) {
  main().catch((err) => {
    console.error(err.message);
    process.exit(1);
  });
}

// Export functions for testing
module.exports = { generateChartUrl, generateMap, httpPost, CHART_TYPE_MAP };
