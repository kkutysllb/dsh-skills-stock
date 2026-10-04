window.__ModuleLoader__.load({ id: "dsh-skills-stock", factory: (require) => {
var module = { exports: {} }; var exports = module.exports;
"use strict";
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name2 in all)
    __defProp(target, name2, { get: all[name2], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/client/index.tsx
var index_exports = {};
__export(index_exports, {
  apply: () => apply,
  createWorkbenchRuntime: () => createWorkbenchRuntime,
  inject: () => inject,
  name: () => name
});
module.exports = __toCommonJS(index_exports);

// src/client/WorkbenchView.tsx
var import_react3 = require("react");

// src/client/protocol.ts
function unwrapRpcResult(response) {
  const typed = response;
  if (typed !== void 0 && typed !== null && typeof typed === "object" && "ok" in typed) {
    if (typed.ok === true) return typed.value;
    throw new Error(typed.error?.message ?? String(typed.error?.code ?? "rpc failed"));
  }
  throw new Error("\u6295\u7814\u5DE5\u4F5C\u53F0\u901A\u9053\u8FD4\u56DE\u4E86\u65E0\u6CD5\u8BC6\u522B\u7684\u7ED3\u679C (unexpected rpc result shape)");
}

// src/client/runtime.ts
var RPC_CHANNEL = "/dsh-skills-stock";
var LIBRARY_TABS = ["strategies", "factors", "selections"];
var WORKBENCH_TABS = ["strategies", "factors", "selections", "reports"];
function createWorkbenchRuntime(deps) {
  let state = { phase: "idle" };
  let refreshPromise;
  const listeners = /* @__PURE__ */ new Set();
  const publish = (next) => {
    state = next;
    for (const listener of [...listeners]) listener();
  };
  const patch = (partial) => {
    publish({ ...state, ...partial });
  };
  const source = {
    getSnapshot: () => state,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    }
  };
  const loadLibrary = async (kind) => {
    const items = unwrapRpcResult(
      await deps.rpc.call(RPC_CHANNEL, "library_list", { kind })
    ).items;
    const libraries = state.libraries ?? {
      strategies: { loaded: false, items: [] },
      factors: { loaded: false, items: [] },
      selections: { loaded: false, items: [] }
    };
    patch({ libraries: { ...libraries, [kind]: { loaded: true, items } } });
  };
  const refresh = async () => {
    if (refreshPromise !== void 0) return refreshPromise;
    const previous = { status: state.status, catalog: state.catalog };
    publish(previous.status === void 0 && previous.catalog === void 0 ? { phase: "loading" } : { ...state, phase: "loading" });
    refreshPromise = (async () => {
      try {
        const [status, catalog] = await Promise.all([
          deps.rpc.call(RPC_CHANNEL, "status"),
          deps.rpc.call(RPC_CHANNEL, "skills")
        ]);
        patch({
          phase: "ready",
          status: unwrapRpcResult(status),
          catalog: unwrapRpcResult(catalog),
          error: void 0,
          refreshedAt: Date.now()
        });
      } catch (error) {
        patch({
          phase: "error",
          error: error instanceof Error ? error.message : String(error),
          refreshedAt: Date.now()
        });
      } finally {
        refreshPromise = void 0;
      }
    })();
    return refreshPromise;
  };
  return {
    source,
    refresh,
    async loadLibrary(kind) {
      try {
        await loadLibrary(kind);
      } catch (error) {
        const libraries = state.libraries ?? {
          strategies: { loaded: false, items: [] },
          factors: { loaded: false, items: [] },
          selections: { loaded: false, items: [] }
        };
        patch({ libraries: { ...libraries, [kind]: { loaded: true, items: [] } }, error: error instanceof Error ? error.message : String(error) });
      }
    },
    async openDetail(kind, objectId) {
      patch({ detailLoading: true });
      try {
        const data = unwrapRpcResult(
          await deps.rpc.call(RPC_CHANNEL, "library_detail", { kind, object_id: objectId })
        );
        patch({ detail: { kind, data }, detailLoading: false });
      } catch (error) {
        patch({
          detailLoading: false,
          error: error instanceof Error ? error.message : String(error)
        });
      }
    },
    closeDetail() {
      patch({ detail: void 0 });
    },
    async loadRuns(kind, objectId, runIds) {
      const value = unwrapRpcResult(
        await deps.rpc.call(RPC_CHANNEL, "library_runs", { kind, object_id: objectId, run_ids: [...runIds] })
      );
      return value.runs;
    },
    async loadReports() {
      try {
        const items = unwrapRpcResult(
          await deps.rpc.call(RPC_CHANNEL, "reports_list", {})
        ).items;
        patch({ reports: { loaded: true, items } });
      } catch (error) {
        patch({ reports: { loaded: true, items: [] }, error: error instanceof Error ? error.message : String(error) });
      }
    },
    async openReport(reportId) {
      patch({ reportLoading: true });
      try {
        const data = unwrapRpcResult(
          await deps.rpc.call(RPC_CHANNEL, "reports_get", { report_id: reportId, content: true })
        );
        patch({ reportDetail: { data }, reportLoading: false });
      } catch (error) {
        patch({ reportLoading: false, error: error instanceof Error ? error.message : String(error) });
      }
    },
    closeReport() {
      patch({ reportDetail: void 0 });
    },
    async saveSecrets(input) {
      patch({ saving: true, saveError: void 0, savedKeys: void 0 });
      try {
        const payload = {};
        if (input.tushareToken !== void 0 && input.tushareToken !== "") payload["TUSHARE_TOKEN"] = input.tushareToken;
        if (input.iwencaiKey !== void 0 && input.iwencaiKey !== "") payload["IWENCAI_API_KEY"] = input.iwencaiKey;
        const value = unwrapRpcResult(
          await deps.rpc.call(RPC_CHANNEL, "save_secrets", payload)
        );
        const pending = refreshPromise;
        if (pending !== void 0) await pending.catch(() => void 0);
        await refresh();
        patch({ saving: false, savedKeys: value.saved, saveError: void 0 });
        return value;
      } catch (error) {
        patch({
          saving: false,
          saveError: error instanceof Error ? error.message : String(error)
        });
        throw error;
      }
    },
    clearFeedback() {
      patch({ savedKeys: void 0, saveError: void 0 });
    }
  };
}

// src/client/RunCompare.tsx
var import_react = require("react");
var import_jsx_runtime = require("react/jsx-runtime");
var RUN_COLORS = ["#e8a33d", "#5ab0ff", "#22a06b", "#c792ea", "#e64646", "#8ee6c8"];
var CHART_WIDTH = 560;
var CHART_HEIGHT = 240;
var PAD_LEFT = 46;
var PAD_RIGHT = 12;
var PAD_TOP = 14;
var PAD_BOTTOM = 26;
function runIdOf(run) {
  return typeof run["run_id"] === "string" ? run["run_id"] : "";
}
function versionOf(run) {
  return typeof run["version"] === "number" ? run["version"] : 0;
}
function normalizeEquity(raw) {
  let values = [];
  if (Array.isArray(raw)) {
    const asObjects = raw.every((item) => typeof item === "object" && item !== null && typeof item["equity"] === "number");
    if (asObjects) {
      values = raw.map((item) => item["equity"]);
    } else {
      values = raw.filter((item) => typeof item === "number");
    }
  } else if (typeof raw === "object" && raw !== null) {
    const record = raw;
    const candidate = Array.isArray(record["values"]) ? record["values"] : record["equity_values"];
    if (Array.isArray(candidate)) values = candidate.filter((v) => typeof v === "number");
  }
  const base = values[0];
  if (base === void 0 || !Number.isFinite(base) || base <= 0) return values;
  return values.map((value) => value / base);
}
function cumulativeIc(raw) {
  let values = [];
  if (Array.isArray(raw)) {
    const asObjects = raw.every((item) => typeof item === "object" && item !== null && typeof item["ic"] === "number");
    if (asObjects) {
      values = raw.map((item) => item["ic"]);
    } else {
      values = raw.filter((item) => typeof item === "number");
    }
  }
  const out = [];
  let acc = 0;
  for (const value of values) {
    acc += Number.isFinite(value) ? value : 0;
    out.push(acc);
  }
  return out;
}
function bounds(values) {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const value of values) {
    if (value < min) min = value;
    if (value > max) max = value;
  }
  return { min, max };
}
function CurveOverlay(props) {
  const drawable = props.series.filter((item) => item.values.length >= 2);
  if (drawable.length === 0) return null;
  const flat = drawable.flatMap((item) => item.values);
  const data = bounds(flat);
  const min = props.includeBaseline ? Math.min(data.min, props.baseline) : data.min;
  const max = props.includeBaseline ? Math.max(data.max, props.baseline) : data.max;
  const span = max - min || 1;
  const maxLen = drawable.reduce((acc, item) => Math.max(acc, item.values.length), 0);
  const x = (index, length) => PAD_LEFT + index / Math.max(1, length - 1) * (CHART_WIDTH - PAD_LEFT - PAD_RIGHT);
  const y = (value) => PAD_TOP + (1 - (value - min) / span) * (CHART_HEIGHT - PAD_BOTTOM - PAD_TOP);
  return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("svg", { className: "kss-curve-svg", viewBox: `0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`, role: "img", "aria-label": props.ariaLabel, children: [
    /* @__PURE__ */ (0, import_jsx_runtime.jsx)("line", { className: "kss-curve-grid", x1: PAD_LEFT, y1: y(props.baseline), x2: CHART_WIDTH - PAD_RIGHT, y2: y(props.baseline) }),
    /* @__PURE__ */ (0, import_jsx_runtime.jsx)("text", { className: "kss-curve-axis", x: PAD_LEFT - 6, y: y(props.baseline) + 4, textAnchor: "end", children: props.baselineLabel }),
    /* @__PURE__ */ (0, import_jsx_runtime.jsx)("text", { className: "kss-curve-axis", x: PAD_LEFT - 6, y: y(max) + 4, textAnchor: "end", children: max.toFixed(2) }),
    /* @__PURE__ */ (0, import_jsx_runtime.jsx)("text", { className: "kss-curve-axis", x: PAD_LEFT - 6, y: y(min) + 4, textAnchor: "end", children: min.toFixed(2) }),
    drawable.map((item) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)(
      "polyline",
      {
        className: "kss-curve-line",
        style: { stroke: item.color },
        points: item.values.map((value, index) => `${x(index, item.values.length)},${y(value)}`).join(" ")
      },
      item.label
    )),
    drawable.map((item, row) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("g", { children: [
      /* @__PURE__ */ (0, import_jsx_runtime.jsx)("rect", { x: PAD_LEFT + row * 120, y: CHART_HEIGHT - 14, width: 10, height: 10, fill: item.color }),
      /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("text", { className: "kss-curve-legend", x: PAD_LEFT + row * 120 + 15, y: CHART_HEIGHT - 5, children: [
        item.label,
        "\uFF08",
        item.values.length === maxLen ? `${item.values.length}${props.unit}` : `${item.values.length}/${maxLen}${props.unit}`,
        "\uFF09"
      ] })
    ] }, `legend-${item.label}`))
  ] });
}
function metricKeysOf(tab) {
  return tab === "strategies" ? ["total_return_pct", "annual_return_pct", "sharpe_ratio", "max_drawdown_pct", "win_rate_pct", "trade_count"] : tab === "factors" ? ["ic_mean", "ir", "ic_positive_pct", "n_periods", "long_short_spread_pct"] : ["hit_count", "strategy_count", "consensus_count", "top_n"];
}
function RunCompare(props) {
  const { t, tab, objectId, runs, loadRuns } = props;
  const curveTab = tab === "strategies" || tab === "factors";
  const idsKey = runs.map(runIdOf).join("|");
  const [fullRuns, setFullRuns] = (0, import_react.useState)(void 0);
  const [curveError, setCurveError] = (0, import_react.useState)(void 0);
  const loadRunsRef = (0, import_react.useRef)(loadRuns);
  loadRunsRef.current = loadRuns;
  (0, import_react.useEffect)(() => {
    if (!curveTab) return;
    let active = true;
    setFullRuns(void 0);
    setCurveError(void 0);
    loadRunsRef.current(idsKey.split("|")).then((value) => {
      if (active) setFullRuns(value);
    }).catch((error) => {
      if (active) setCurveError(error instanceof Error ? error.message : String(error));
    });
    return () => {
      active = false;
    };
  }, [curveTab, objectId, idsKey]);
  const curveSeries = (0, import_react.useMemo)(() => {
    if (fullRuns === void 0) return [];
    const versionSet = new Set(fullRuns.map(versionOf));
    const duplicated = versionSet.size !== fullRuns.length;
    return fullRuns.map((run, index) => ({
      label: duplicated ? `v${versionOf(run)}\xB7${runIdOf(run).slice(-4)}` : `v${versionOf(run)}`,
      values: tab === "strategies" ? normalizeEquity(run["equity"]) : cumulativeIc(run["ic_series"]),
      color: RUN_COLORS[index % RUN_COLORS.length]
    }));
  }, [fullRuns, tab]);
  const num2 = (value) => typeof value === "number" ? String(value) : "\u2014";
  return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { className: "kss-compare", children: [
    /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("h3", { className: "kss-group-title", children: [
      t("compare"),
      "\uFF08",
      t("compareHint"),
      "\uFF09"
    ] }),
    /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("table", { className: "kss-table", children: [
      /* @__PURE__ */ (0, import_jsx_runtime.jsx)("thead", { children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tr", { children: [
        /* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {}),
        runs.map((run) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", { className: "kss-mono", children: runIdOf(run).slice(0, 10) }, runIdOf(run)))
      ] }) }),
      /* @__PURE__ */ (0, import_jsx_runtime.jsx)("tbody", { children: metricKeysOf(tab).map((key) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tr", { children: [
        /* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", { className: "kss-field-hint", children: key }),
        runs.map((run) => {
          const metrics = typeof run["metrics"] === "object" && run["metrics"] !== null ? run["metrics"] : {};
          return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", { children: num2(metrics[key]) }, runIdOf(run));
        })
      ] }, key)) })
    ] }),
    curveTab && (curveError !== void 0 ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", { className: "kss-error", children: curveError }) : fullRuns === void 0 ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", { className: "kss-card-hint", children: t("curveLoading") }) : curveSeries.some((item) => item.values.length >= 2) ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { className: "kss-curve-block", children: [
      /* @__PURE__ */ (0, import_jsx_runtime.jsx)("h4", { className: "kss-group-title", children: tab === "strategies" ? t("curveEquity") : t("curveCumIc") }),
      /* @__PURE__ */ (0, import_jsx_runtime.jsx)(
        CurveOverlay,
        {
          ariaLabel: tab === "strategies" ? "\u51C0\u503C\u66F2\u7EBF\u53E0\u52A0\u5BF9\u6BD4" : "\u7D2F\u8BA1 IC \u66F2\u7EBF\u53E0\u52A0\u5BF9\u6BD4",
          baseline: tab === "strategies" ? 1 : 0,
          baselineLabel: tab === "strategies" ? "1.00" : "0",
          includeBaseline: tab !== "strategies",
          series: curveSeries,
          unit: tab === "strategies" ? "pt" : "\u671F"
        }
      )
    ] }) : /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", { className: "kss-card-hint", children: tab === "strategies" ? t("curveMissingEquity") : t("curveMissingIc") }))
  ] });
}

// src/client/SettingsView.tsx
var import_react2 = require("react");
var import_jsx_runtime2 = require("react/jsx-runtime");
function usePanelState(runtime) {
  return (0, import_react2.useSyncExternalStore)(runtime.source.subscribe, runtime.source.getSnapshot, runtime.source.getSnapshot);
}
function KeyBadge(props) {
  const { t, ok, label } = props;
  return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: `kss-badge ${ok ? "is-ok" : "is-miss"}`, title: label, children: [
    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { "aria-hidden": "true", children: ok ? "\u25CF" : "\u25CB" }),
    label,
    " \xB7 ",
    ok ? t("configured") : t("notConfigured")
  ] });
}
function DataSourcesSettingsView(props) {
  const { t, runtime } = props;
  const state = usePanelState(runtime);
  useEffectOnce(() => {
    void runtime.refresh();
  }, [runtime]);
  if (state.phase === "loading" || state.phase === "idle") {
    return /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "kss-root", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "kss-state", children: t("refreshing") }) });
  }
  if (state.phase === "error" && state.status === void 0) {
    return /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("div", { className: "kss-root", children: /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "kss-state", children: [
      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { children: t("errorLoad") }),
      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "kss-error", children: state.error }),
      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("button", { type: "button", className: "kss-btn", onClick: () => {
        void runtime.refresh();
      }, children: t("retry") })
    ] }) });
  }
  const status = state.status;
  return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "kss-root", children: [
    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "kss-card", children: [
      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { className: "kss-card-title", children: t("navDataSources") }),
      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "kss-card-hint", children: t("settingsIntro") }),
      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)(
        "form",
        {
          id: "kss-secrets-form",
          className: "kss-fields",
          onSubmit: (event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = new FormData(form);
            void runtime.saveSecrets({
              tushareToken: String(data.get("tushare") ?? ""),
              iwencaiKey: String(data.get("iwencai") ?? "")
            }).then(() => {
              form.reset();
            }).catch(() => void 0);
          },
          children: [
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("label", { className: "kss-field", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "kss-field-head", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "kss-label", children: t("tushareLabel") }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(KeyBadge, { t, ok: status?.keys.TUSHARE_TOKEN === true, label: "Tushare" })
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                "input",
                {
                  className: "kss-input",
                  name: "tushare",
                  type: "password",
                  autoComplete: "off",
                  spellCheck: false,
                  placeholder: status?.keys.TUSHARE_TOKEN === true ? t("keepBlank") : ""
                }
              ),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "kss-field-hint", children: t("tushareHint") })
            ] }),
            /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("label", { className: "kss-field", children: [
              /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "kss-field-head", children: [
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "kss-label", children: t("iwencaiLabel") }),
                /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(KeyBadge, { t, ok: status?.keys.IWENCAI_API_KEY === true, label: "iWenCai" })
              ] }),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(
                "input",
                {
                  className: "kss-input",
                  name: "iwencai",
                  type: "password",
                  autoComplete: "off",
                  spellCheck: false,
                  placeholder: status?.keys.IWENCAI_API_KEY === true ? t("keepBlank") : ""
                }
              ),
              /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "kss-field-hint", children: t("iwencaiHint") })
            ] })
          ]
        }
      ),
      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("div", { className: "kss-actions", children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("button", { type: "submit", form: "kss-secrets-form", className: "kss-btn is-primary", disabled: state.saving === true, children: state.saving === true ? t("saving") : t("save") }),
        state.savedKeys !== void 0 && state.savedKeys.length > 0 && /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "kss-feedback is-ok", children: t("saved", { keys: state.savedKeys.join(", ") }) }),
        state.saveError !== void 0 && /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("span", { className: "kss-feedback is-err", children: [
          t("saveFailed"),
          "\uFF1A",
          state.saveError
        ] }),
        status?.secretsWritable === false && /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("span", { className: "kss-feedback is-err", children: t("secretsUnavailable", { home: status.stockHome }) })
      ] }),
      /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("p", { className: "kss-card-hint", children: [
        /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("code", { className: "kss-path", children: status?.secretsPath ?? "~/.dsh-stock/secrets.env" }),
        " ",
        t("dataSourceHint")
      ] })
    ] }),
    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)(NotesCard, { t })
  ] });
}
function useEffectOnce(fn, deps) {
  (0, import_react2.useEffect)(fn, deps);
}
function NotesCard(props) {
  const { t } = props;
  return /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("section", { className: "kss-card", children: [
    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("h2", { className: "kss-card-title", children: t("sectionNotes") }),
    /* @__PURE__ */ (0, import_jsx_runtime2.jsxs)("ol", { className: "kss-notes", children: [
      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: t("note1") }),
      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: t("note2") }),
      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: t("note3") }),
      /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("li", { children: t("note4") })
    ] }),
    /* @__PURE__ */ (0, import_jsx_runtime2.jsx)("p", { className: "kss-footer", children: t("disclaimer") })
  ] });
}

// src/client/WorkbenchView.tsx
var import_jsx_runtime3 = require("react/jsx-runtime");
var TAB_LABEL = {
  strategies: "tabStrategies",
  factors: "tabFactors",
  selections: "tabSelections",
  reports: "tabReports"
};
var TOOL_PREFIX = {
  strategies: "strategy",
  factors: "factor",
  selections: "selection"
};
function usePanelState2(runtime) {
  return (0, import_react3.useSyncExternalStore)(runtime.source.subscribe, runtime.source.getSnapshot, runtime.source.getSnapshot);
}
function str(value) {
  return typeof value === "string" ? value : "";
}
function num(value) {
  return typeof value === "number" ? String(value) : "\u2014";
}
function isLibraryTab(tab) {
  return LIBRARY_TABS.includes(tab);
}
function WorkbenchView(props) {
  const { t, runtime, bridge } = props;
  const state = usePanelState2(runtime);
  const [tab, setTab] = (0, import_react3.useState)("strategies");
  const [deliverNote, setDeliverNote] = (0, import_react3.useState)(void 0);
  (0, import_react3.useEffect)(() => {
    void runtime.refresh();
  }, [runtime]);
  (0, import_react3.useEffect)(() => {
    if (tab === "reports") void runtime.loadReports();
    else void runtime.loadLibrary(tab);
  }, [runtime, tab]);
  (0, import_react3.useEffect)(() => () => {
    runtime.closeDetail();
    runtime.closeReport();
  }, [runtime]);
  if (state.phase === "error" && state.status === void 0) {
    return /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("div", { className: "kss-panel", children: /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("div", { className: "kss-state", children: [
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { children: t("errorLoad") }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-error", children: state.error }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("button", { type: "button", className: "kss-btn", onClick: () => {
        void runtime.refresh();
      }, children: t("retry") })
    ] }) });
  }
  const libraries = state.libraries;
  const reportList = state.reports ?? { loaded: false, items: [] };
  const reportDetail = state.reportDetail?.data;
  const list = isLibraryTab(tab) ? libraries?.[tab] ?? { loaded: false, items: [] } : { loaded: false, items: [] };
  const detail = state.detail?.kind === tab && isLibraryTab(tab) ? state.detail.data : void 0;
  const deliver = (text) => {
    void bridge.send(text).then((result) => {
      setDeliverNote(result === "submitted" ? void 0 : result === "copied" ? t("sendFailed") : t("sendFailed"));
      setTimeout(() => setDeliverNote(void 0), 4e3);
    });
  };
  return /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("div", { className: "kss-panel", children: [
    /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("header", { className: "kss-header", children: [
      /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("div", { children: [
        /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("h1", { className: "kss-title", children: t("title") }),
        /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("p", { className: "kss-subtitle", children: t("subtitle") })
      ] }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("div", { className: "kss-badges", children: /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("button", { type: "button", className: "kss-btn", onClick: () => {
        void runtime.refresh();
        if (tab === "reports") void runtime.loadReports();
        else void runtime.loadLibrary(tab);
      }, children: state.phase === "loading" ? t("refreshing") : t("refresh") }) })
    ] }),
    /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("div", { className: "kss-tabs", children: [
      WORKBENCH_TABS.map((kind) => /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(
        "button",
        {
          type: "button",
          className: `kss-tab ${tab === kind ? "is-active" : ""}`,
          onClick: () => {
            runtime.closeDetail();
            runtime.closeReport();
            setTab(kind);
          },
          children: t(TAB_LABEL[kind])
        },
        kind
      )),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-tabs-spacer" }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(
        "button",
        {
          type: "button",
          className: "kss-btn is-primary",
          onClick: () => {
            deliver(t("researchTaskPrompt", { label: t(TAB_LABEL[tab]) }));
          },
          children: t("newResearch")
        }
      )
    ] }),
    deliverNote !== void 0 && /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("p", { className: "kss-feedback is-warn", children: deliverNote }),
    tab === "reports" ? reportDetail !== void 0 ? /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(ReportDetailViewPane, { t, runtime, detail: reportDetail }) : /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(ReportListTab, { t, runtime, list: reportList }) : detail === void 0 ? /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(LibraryListTab, { t, runtime, tab, list }) : /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(
      LibraryDetailViewPane,
      {
        t,
        runtime,
        tab,
        detail,
        bridge
      }
    ),
    /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(NotesCard, { t })
  ] });
}
function LibraryListTab(props) {
  const { t, runtime, tab, list } = props;
  if (!list.loaded) return /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("div", { className: "kss-state", children: t("refreshing") });
  if (list.items.length === 0) return /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("p", { className: "kss-card-hint", children: t("emptyLibrary") });
  return /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("div", { className: "kss-grid", children: list.items.map((item) => /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("article", { className: "kss-skill", children: [
    /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("div", { className: "kss-skill-head", children: [
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-skill-name", children: str(item["name"]) }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(
        "button",
        {
          type: "button",
          className: "kss-skill-copy",
          onClick: () => {
            void runtime.openDetail(tab, item.object_id);
          },
          children: t("openDetail")
        }
      )
    ] }),
    /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("p", { className: "kss-skill-desc", children: str(item["hypothesis"]) !== "" ? str(item["hypothesis"]) : str(item["criteria"]) }),
    /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("div", { className: "kss-skill-meta", children: [
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: `kss-badge ${str(item["status"]) === "researching" || str(item["status"]) === "watching" ? "is-ok" : "is-miss"}`, children: str(item["status"]) }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("span", { className: "kss-field-hint", children: [
        "v",
        num(item["current_version"])
      ] }),
      item["latest_run"] !== void 0 && /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-field-hint", children: summarizeRun(item["latest_run"]) })
    ] })
  ] }, item.object_id)) });
}
function summarizeRun(latestRun) {
  if (typeof latestRun !== "object" || latestRun === null) return "";
  const run = latestRun;
  const metrics = typeof run["metrics"] === "object" && run["metrics"] !== null ? run["metrics"] : {};
  const parts = [];
  if (typeof metrics["total_return_pct"] === "number") parts.push(`\u6536\u76CA ${metrics["total_return_pct"]}%`);
  if (typeof metrics["sharpe_ratio"] === "number") parts.push(`\u590F\u666E ${metrics["sharpe_ratio"]}`);
  if (typeof metrics["ic_mean"] === "number") parts.push(`IC ${metrics["ic_mean"]}`);
  if (typeof metrics["hit_count"] === "number") parts.push(`\u547D\u4E2D ${metrics["hit_count"]}`);
  return parts.join(" \xB7 ");
}
function LibraryDetailViewPane(props) {
  const { t, runtime, tab, detail, bridge } = props;
  const [checked, setChecked] = (0, import_react3.useState)([]);
  const versions = detail.versions ?? [];
  const runs = detail.runs ?? [];
  const rerunPrompt = (version) => t("rerunPrompt", {
    library: t(TAB_LABEL[tab]),
    name: detail.name,
    object_id: detail.object_id,
    toolPrefix: TOOL_PREFIX[tab],
    version,
    label: t(TAB_LABEL[tab])
  });
  const toggleRun = (runId) => {
    setChecked((prev) => prev.includes(runId) ? prev.filter((id) => id !== runId) : prev.length >= 4 ? prev : [...prev, runId]);
  };
  return /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("section", { className: "kss-card", children: [
    /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("div", { className: "kss-skill-head", children: [
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("button", { type: "button", className: "kss-btn", onClick: () => {
        runtime.closeDetail();
      }, children: t("backToList") }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-skill-name", children: detail.name }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-badge", children: detail.status }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("span", { className: "kss-field-hint", children: [
        "v",
        detail.current_version
      ] }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-tabs-spacer" }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("button", { type: "button", className: "kss-btn is-primary", onClick: () => {
        bridge.send(rerunPrompt(detail.current_version));
      }, children: t("rerun") })
    ] }),
    (detail.hypothesis !== void 0 || detail.criteria !== void 0) && /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("p", { className: "kss-card-hint", children: detail.hypothesis !== void 0 ? `${t("hypothesis")}\uFF1A${detail.hypothesis}` : `${t("criteria")}\uFF1A${detail.criteria}` }),
    /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("h3", { className: "kss-group-title", children: t("versions") }),
    /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("div", { className: "kss-versions", children: [...versions].reverse().map((version) => {
      const v = typeof version["version"] === "number" ? version["version"] : 0;
      return /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("div", { className: "kss-version-row", children: [
        /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("span", { className: "kss-version-tag", children: [
          "v",
          v
        ] }),
        /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-field-hint", children: str(version["created_at"]).slice(0, 16).replace("T", " ") }),
        /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-skill-desc", children: str(version["change_note"]) }),
        v === detail.current_version && /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-badge is-ok", children: t("latest") }),
        /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-tabs-spacer" }),
        /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("button", { type: "button", className: "kss-skill-copy", onClick: () => {
          bridge.send(rerunPrompt(v));
        }, children: t("rerun") })
      ] }, v);
    }) }),
    /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("h3", { className: "kss-group-title", children: t("runs") }),
    runs.length === 0 ? /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("p", { className: "kss-card-hint", children: t("noRuns", { label: t(TAB_LABEL[tab]) }) }) : /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("table", { className: "kss-table", children: [
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("thead", { children: /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("tr", { children: [
        /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("th", {}),
        /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("th", { children: "run" }),
        /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("th", { children: "v" }),
        /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("th", { children: metricsHeaderLabel(tab) }),
        /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("th", {})
      ] }) }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("tbody", { children: runs.map((run) => {
        const runId = str(run["run_id"]);
        return /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("tr", { children: [
          /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("td", { children: /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(
            "input",
            {
              type: "checkbox",
              "aria-label": runId,
              checked: checked.includes(runId),
              onChange: () => {
                toggleRun(runId);
              }
            }
          ) }),
          /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("td", { className: "kss-mono", children: runId.slice(0, 10) }),
          /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("td", { children: [
            "v",
            num(run["version"])
          ] }),
          /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("td", { children: summarizeRun(run) }),
          /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("td", { children: str(run["created_at"]).slice(0, 16).replace("T", " ") })
        ] }, runId);
      }) })
    ] }),
    checked.length >= 2 && /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(
      RunCompare,
      {
        t,
        tab,
        objectId: detail.object_id,
        runs: runs.filter((run) => checked.includes(str(run["run_id"]))),
        loadRuns: (ids) => runtime.loadRuns(tab, detail.object_id, ids)
      }
    )
  ] });
}
function metricsHeaderLabel(tab) {
  return tab === "strategies" ? "\u6536\u76CA/\u590F\u666E" : tab === "factors" ? "IC/IR" : "\u547D\u4E2D";
}
function formatBytes(bytes) {
  if (typeof bytes !== "number" || !Number.isFinite(bytes)) return "\u2014";
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${bytes} B`;
}
function ReportListTab(props) {
  const { t, runtime, list } = props;
  if (!list.loaded) return /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("div", { className: "kss-state", children: t("refreshing") });
  if (list.items.length === 0) return /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("p", { className: "kss-card-hint", children: t("emptyReports") });
  return /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("div", { className: "kss-grid", children: list.items.map((item) => /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("article", { className: "kss-skill", children: [
    /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("div", { className: "kss-skill-head", children: [
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-skill-name", children: str(item["title"]) }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(
        "button",
        {
          type: "button",
          className: "kss-skill-copy",
          onClick: () => {
            void runtime.openReport(str(item["report_id"]));
          },
          children: t("openDetail")
        }
      )
    ] }),
    /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("p", { className: "kss-skill-desc", children: [
      str(item["symbol"]) !== "" ? `${str(item["symbol"])} \xB7 ` : "",
      str(item["report_type"]),
      str(item["coverage_status"]) === "partial" ? " \xB7 \u6570\u636E\u90E8\u5206\u8986\u76D6" : ""
    ] }),
    /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("div", { className: "kss-skill-meta", children: [
      str(item["risk_level"]) !== "" && /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("span", { className: `kss-badge ${str(item["risk_level"]) === "\u9AD8" ? "is-miss" : "is-ok"}`, children: [
        t("reportRisk"),
        " ",
        str(item["risk_level"])
      ] }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-field-hint", children: formatBytes(item["size_bytes"]) }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-field-hint", children: str(item["updated_at"]).slice(0, 16).replace("T", " ") })
    ] })
  ] }, str(item["report_id"]))) });
}
function ReportDetailViewPane(props) {
  const { t, runtime, detail } = props;
  const content = str(detail["content"]);
  const openInNewWindow = () => {
    try {
      const url = URL.createObjectURL(new Blob([content], { type: "text/html" }));
      window.open(url, "_blank", "noopener");
    } catch {
    }
  };
  return /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("section", { className: "kss-card", children: [
    /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("div", { className: "kss-skill-head", children: [
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("button", { type: "button", className: "kss-btn", onClick: () => {
        runtime.closeReport();
      }, children: t("backToList") }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-skill-name", children: str(detail["title"]) }),
      str(detail["symbol"]) !== "" && /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-badge", children: str(detail["symbol"]) }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-field-hint", children: formatBytes(detail["size_bytes"]) }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("span", { className: "kss-tabs-spacer" }),
      /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("button", { type: "button", className: "kss-btn is-primary", onClick: openInNewWindow, children: t("reportOpenNew") })
    ] }),
    /* @__PURE__ */ (0, import_jsx_runtime3.jsxs)("p", { className: "kss-card-hint", children: [
      str(detail["report_type"]),
      " \xB7 ",
      str(detail["generated_at"]).slice(0, 16).replace("T", " "),
      str(detail["period_start"]) !== "" ? ` \xB7 ${str(detail["period_start"])} ~ ${str(detail["period_end"])}` : "",
      str(detail["risk_level"]) !== "" ? ` \xB7 ${t("reportRisk")} ${str(detail["risk_level"])}` : ""
    ] }),
    /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("h3", { className: "kss-group-title", children: t("reportPreview") }),
    content === "" ? /* @__PURE__ */ (0, import_jsx_runtime3.jsx)("p", { className: "kss-card-hint", children: t("reportNoContent") }) : /* @__PURE__ */ (0, import_jsx_runtime3.jsx)(
      "iframe",
      {
        className: "kss-report-frame",
        title: str(detail["title"]) || t("reportPreview"),
        srcDoc: content,
        sandbox: ""
      }
    )
  ] });
}

// src/client/bridge.ts
function createConversationBridge(ctx) {
  const backToChat = () => {
    try {
      ctx.layout?.selectPanel(null);
    } catch {
    }
  };
  const clipboardFallback = async (text) => {
    try {
      await navigator.clipboard?.writeText(text);
      return "copied";
    } catch {
      return "none";
    }
  };
  const send = (text, workspaceId) => {
    const sessions = ctx.sessions;
    let plan;
    try {
      if (sessions === void 0 || sessions.list === void 0 || typeof sessions.list.getSnapshot !== "function") {
        return clipboardFallback(text);
      }
      const current = sessions.list.getSnapshot().current;
      const wsList = ctx.workspaces?.list !== void 0 && typeof ctx.workspaces.list.getSnapshot === "function" ? ctx.workspaces.list.getSnapshot() : null;
      let wsOfCurrent;
      if (current !== void 0 && wsList?.items !== void 0) {
        for (const ws of wsList.items) {
          if ((ws.sessionIds ?? []).includes(current)) {
            wsOfCurrent = ws.workspaceId;
            break;
          }
        }
      }
      const wantsSwitch = workspaceId !== void 0 && wsOfCurrent !== workspaceId;
      if (current !== void 0 && !wantsSwitch) {
        plan = Promise.resolve(current);
      } else if (ctx.uiWorkspace?.openWorkspace !== void 0 && wsList?.items !== void 0 && wsList.items.length > 0) {
        const target = workspaceId ?? wsOfCurrent ?? wsList.items[0].workspaceId;
        plan = Promise.resolve(ctx.uiWorkspace.openWorkspace(target)).then(() => sessions.list.getSnapshot().current ?? null);
      } else if (typeof sessions.create === "function") {
        plan = Promise.resolve(sessions.create()).then((id) => {
          try {
            if (typeof sessions.open === "function") sessions.open(id);
          } catch {
          }
          backToChat();
          return id;
        });
      } else {
        plan = Promise.resolve(null);
      }
    } catch (bridgeError) {
      console.warn("[dsh-skills-stock] \u4F1A\u8BDD\u6865\u5B9A\u4F4D\u5F02\u5E38:", bridgeError instanceof Error ? bridgeError.message : bridgeError);
      return clipboardFallback(text);
    }
    return plan.then((sessionId) => {
      if (sessionId === null || sessionId === void 0) return clipboardFallback(text);
      try {
        backToChat();
        const shell = resolveInputShell(sessionId);
        if (shell !== null && typeof shell.setDraft === "function") {
          shell.setDraft(text);
          if (typeof shell.submit === "function") {
            shell.submit();
            return "submitted";
          }
          console.warn("[dsh-skills-stock] \u5BBF\u4E3B\u8F93\u5165\u9762\u65E0 submit\uFF0C\u964D\u7EA7\u526A\u8D34\u677F");
        }
      } catch {
      }
      return clipboardFallback(text);
    }, () => clipboardFallback(text));
  };
  const resolveInputShell = (sessionId) => {
    const sessions = ctx.sessions;
    if (sessions === void 0 || typeof sessions.scope !== "function") return null;
    try {
      const conversation = typeof ctx.get === "function" ? ctx.get("conversation") : ctx.conversation;
      const input = conversation?.input;
      if (input !== void 0) {
        if (typeof input.shell === "function") return input.shell(sessionId);
        if (typeof input.for === "function") {
          const actx = sessions.scope(sessionId);
          if (actx !== void 0) return input.for(actx);
        }
      }
    } catch {
    }
    try {
      const actx = sessions.scope(sessionId);
      const legacyInput = actx?.conversation?.input;
      if (legacyInput !== void 0 && typeof legacyInput.for === "function") return legacyInput.for(actx);
    } catch {
    }
    return null;
  };
  return { send, backToChat };
}

// src/client/locales.ts
var NS = "dsh-skills-stock";
var zh = {
  "nav": "\u6295\u7814\u5DE5\u4F5C\u53F0",
  "navDataSources": "\u6570\u636E\u6E90",
  "title": "A \u80A1\u91CF\u5316\u6295\u7814\u5DE5\u4F5C\u53F0",
  "subtitle": "KStock \u6280\u80FD\u5305 \xB7 41 \u4E2A\u6295\u7814\u6280\u80FD + \u7B56\u7565/\u56E0\u5B50/\u9009\u80A1/\u62A5\u544A\u56DB\u5E93\u5DE5\u4F5C\u533A",
  "refresh": "\u5237\u65B0",
  "refreshing": "\u52A0\u8F7D\u4E2D\u2026",
  "skillsCount": "{count} \u4E2A\u6280\u80FD",
  // 设置页 · 数据源
  "dataSourceHint": "\u5BC6\u94A5\u53EA\u5199\u5165\u672C\u673A\uFF08\u6743\u9650 0600\uFF09\uFF0C\u4E0D\u56DE\u663E\u3001\u4E0D\u4E0A\u4F20\uFF1BAgent \u8FD0\u884C\u6280\u80FD\u811A\u672C\u524D\u4F1A\u81EA\u52A8 source \u8BE5\u6587\u4EF6\u3002",
  "tushareLabel": "Tushare Pro Token",
  "tushareHint": "tushare.pro \u4E2A\u4EBA\u4E3B\u9875\u83B7\u53D6\uFF0C\u884C\u60C5/\u8D22\u52A1/\u5B8F\u89C2\u4E3B\u6570\u636E\u6E90",
  "iwencaiLabel": "\u540C\u82B1\u987A\u95EE\u8D22 API Key",
  "iwencaiHint": "\u95EE\u8D22\u5F00\u653E\u5E73\u53F0\u83B7\u53D6\uFF0C\u81EA\u7136\u8BED\u8A00\u6570\u636E\u67E5\u8BE2\u901A\u9053",
  "configured": "\u5DF2\u914D\u7F6E",
  "notConfigured": "\u672A\u914D\u7F6E",
  "keepBlank": "\u5DF2\u914D\u7F6E\u2014\u2014\u7559\u7A7A\u4FDD\u6301\u4E0D\u53D8",
  "save": "\u4FDD\u5B58\u51ED\u636E",
  "saving": "\u4FDD\u5B58\u4E2D\u2026",
  "saved": "\u5DF2\u4FDD\u5B58\uFF1A{keys}",
  "saveFailed": "\u4FDD\u5B58\u5931\u8D25",
  "secretsUnavailable": "\u6570\u636E\u76EE\u5F55\u4E0D\u53EF\u5199\uFF0C\u8BF7\u68C0\u67E5 {home} \u6743\u9650",
  "settingsIntro": "A \u80A1\u6295\u7814\u6570\u636E\u6E90\u51ED\u636E\uFF1A\u6280\u80FD\u811A\u672C\u7ECF\u51ED\u636E\u6587\u4EF6\u8BFB\u53D6 Tushare / \u95EE\u8D22\u5BC6\u94A5\uFF0C\u6B64\u5904\u6539\u52A8\u5373\u5199 ~/.dsh-stock/secrets.env\uFF080600\uFF09\u3002",
  // 工作台 · tab
  "tabStrategies": "\u7B56\u7565\u5E93",
  "tabFactors": "\u56E0\u5B50\u5E93",
  "tabSelections": "\u9009\u80A1\u5E93",
  "tabReports": "\u62A5\u544A\u5E93",
  "newResearch": "\u65B0\u5EFA\u7814\u7A76\u4EFB\u52A1",
  "emptyLibrary": "\u5E93\u8FD8\u662F\u7A7A\u7684\uFF1A\u5728\u5BF9\u8BDD\u91CC\u8BA9 Agent \u505A\u7B56\u7565\u56DE\u6D4B / \u56E0\u5B50\u68C0\u9A8C / \u6761\u4EF6\u9009\u80A1\uFF0C\u5B83\u4F1A\u7528 strategy_* / factor_* / selection_* \u5DE5\u5177\u628A\u7248\u672C\u4E0E\u8FD0\u884C\u767B\u8BB0\u8FDB\u6765\u3002",
  "openDetail": "\u67E5\u770B",
  "backToList": "\u8FD4\u56DE\u5217\u8868",
  "versions": "\u7248\u672C\u65F6\u95F4\u7EBF",
  "runs": "\u8FD0\u884C\u5F52\u6863",
  "latest": "\u6700\u65B0",
  "rerun": "\u91CD\u8DD1\u672C\u7248\u672C",
  "compare": "\u8FD0\u884C\u5BF9\u6BD4",
  "compareHint": "\u52FE\u9009 2-4 \u4E2A\u8FD0\u884C\u505A\u6307\u6807\u5E76\u6392\u5BF9\u6BD4\uFF1B\u7B56\u7565/\u56E0\u5B50\u53E6\u53E0\u52A0\u51C0\u503C / \u7D2F\u8BA1 IC \u66F2\u7EBF\uFF08\u53E3\u5F84\u4E00\u81F4\u624D\u53EF\u4E25\u683C\u5BF9\u6BD4\uFF09\u3002",
  "curveEquity": "\u51C0\u503C\u66F2\u7EBF\u53E0\u52A0\uFF08\u540C\u8D77\u70B9\u5F52\u4E00\uFF09",
  "curveCumIc": "\u7D2F\u8BA1 IC \u66F2\u7EBF\u53E0\u52A0",
  "curveLoading": "\u66F2\u7EBF\u6570\u636E\u52A0\u8F7D\u4E2D\u2026",
  "curveMissingEquity": "\u6240\u9009\u8FD0\u884C\u7F3A\u5C11\u51C0\u503C\u6570\u636E\uFF08*_record \u672A\u5B58 equity\uFF09\uFF0C\u65E0\u6CD5\u53E0\u52A0\u66F2\u7EBF\u3002",
  "curveMissingIc": "\u6240\u9009\u8FD0\u884C\u7F3A\u5C11 IC \u5E8F\u5217\u6570\u636E\uFF08*_record \u672A\u5B58 ic_series\uFF09\uFF0C\u65E0\u6CD5\u53E0\u52A0\u66F2\u7EBF\u3002",
  "noRuns": "\u8FD8\u6CA1\u6709\u8FD0\u884C\u5F52\u6863\uFF1AAgent \u5B8C\u6210{label}\u540E\u4F1A\u7528 *_record \u5DE5\u5177\u767B\u8BB0\u5230\u8FD9\u91CC\u3002",
  "emptyReports": "\u62A5\u544A\u5E93\u8FD8\u662F\u7A7A\u7684\uFF1A\u8BA9 Agent \u51FA\u7814\u7A76\u62A5\u544A\uFF08html-report \u6280\u80FD\u4EA4\u4ED8\u5355\u6587\u4EF6 HTML \u770B\u677F\uFF09\uFF0C\u5B83\u4F1A\u7528 report_archive \u5DE5\u5177\u5F52\u6863\u5230\u8FD9\u91CC\u3002",
  "reportRisk": "\u98CE\u9669",
  "reportOpenNew": "\u65B0\u7A97\u53E3\u6253\u5F00",
  "reportPreview": "\u62A5\u544A\u9884\u89C8",
  "reportNoContent": "\u62A5\u544A\u5168\u6587\u672A\u968F\u5F52\u6863\u4FDD\u5B58\uFF0C\u8BF7\u8BA9 Agent \u91CD\u65B0\u5F52\u6863\u3002",
  "hypothesis": "\u6295\u8D44\u5047\u8BBE",
  "criteria": "\u9009\u80A1\u53E3\u5F84",
  "category": "\u7C7B\u522B",
  "statusLabel": "\u72B6\u6001",
  "currentVersion": "\u5F53\u524D\u7248\u672C",
  "researchTaskPrompt": "\u8BF7\u57FA\u4E8E\u672C\u63D2\u4EF6\u6280\u80FD\u505A\u4E00\u6B21{label}\u7814\u7A76\u5E76\u628A\u6210\u679C\u767B\u8BB0\u8FDB\u5E93\uFF1A\u5148\u8BFB\u76F8\u5173\u6280\u80FD SKILL.md\uFF0C\u5B8C\u6210\u540E\u7528\u5BF9\u5E94 *_save_version / *_record \u5DE5\u5177\u5165\u5E93\uFF08\u53E3\u5F84\u539F\u6837\u6284\u5F55\uFF09\uFF0C\u8BA9\u6211\u80FD\u5728\u6295\u7814\u5DE5\u4F5C\u53F0\u67E5\u770B\u3002",
  "rerunPrompt": "\u8BF7\u91CD\u8DD1\u6295\u7814\u5DE5\u4F5C\u53F0{library}\u4E2D\u7684\u300C{name}\u300D\uFF1A\u5148\u7528 {toolPrefix}_list \u5B9A\u4F4D {object_id}\uFF0C\u518D\u7528 {toolPrefix}_get_latest \u8BFB\u53D6\u5F53\u524D\u7248\u672C\uFF08v{version}\uFF09\u5FEB\u7167\uFF0C\u6309\u5176\u53E3\u5F84\u590D\u73B0{label}\u6D41\u7A0B\uFF0C\u5B8C\u6210\u540E\u7528\u5BF9\u5E94 *_record \u5DE5\u5177\u767B\u8BB0\u65B0\u8FD0\u884C\uFF08\u53C2\u6570\u4E0E\u53E3\u5F84\u539F\u6837\u6284\u5F55\uFF09\uFF0C\u4E0D\u8981\u6539\u52A8\u7248\u672C\u5FEB\u7167\u5185\u5BB9\u3002",
  "sendFailed": "\u672A\u80FD\u81EA\u52A8\u6295\u9012\u5230\u4F1A\u8BDD\uFF0C\u5185\u5BB9\u5DF2\u590D\u5236\u5230\u526A\u8D34\u677F\uFF0C\u8BF7\u7C98\u8D34\u53D1\u9001\u3002",
  // 通用
  "requires": "\u9700\u8981 {names}",
  "sectionNotes": "\u4F7F\u7528\u7EA6\u5B9A",
  "note1": "\u6280\u80FD\u811A\u672C\u5728\u63D2\u4EF6\u5305\u6839\u5185\u8FD0\u884C\uFF0C\u4EA7\u7269\uFF08\u62A5\u544A HTML / \u56FE\u8868 / JSON / Excel\uFF09\u4E00\u5F8B\u5199\u5165\u5F53\u524D\u5DE5\u4F5C\u76EE\u5F55\u3002",
  "note2": "\u6570\u636E\u4F18\u5148\u7EA7\uFF1ATushare \u7ED3\u6784\u5316\u63A5\u53E3 > \u95EE\u8D22\u81EA\u7136\u8BED\u8A00\u67E5\u8BE2 > \u514D\u8D39\u6E90\uFF08akshare\uFF09/ \u7F51\u7EDC\u641C\u7D22\u515C\u5E95\u3002",
  "note3": "\u6570\u636E\u7F3A\u5931\u65F6\u5982\u5B9E\u6807\u6CE8\uFF0C\u7981\u6B62\u7F16\u9020\uFF1B\u91CD\u8981\u7ED3\u8BBA\u987B\u7ED9\u51FA\u6570\u636E\u6765\u6E90\u4E0E\u8BA1\u7B97\u53E3\u5F84\u3002",
  "note4": "\u7B56\u7565 / \u56E0\u5B50 / \u9009\u80A1\u662F\u7248\u672C\u5316\u8D44\u4EA7\uFF0C\u7814\u7A76\u62A5\u544A\u5F52\u6863\u8FDB\u62A5\u544A\u5E93\uFF1AAgent \u5165\u5E93\u540E\u5728\u5DE5\u4F5C\u53F0\u53EF\u67E5\u65F6\u95F4\u7EBF\u3001\u8FD0\u884C\u5BF9\u6BD4\u3001\u62A5\u544A\u770B\u677F\u5E76\u4E00\u952E\u91CD\u8DD1\u3002",
  "disclaimer": "\u5168\u90E8\u8F93\u51FA\u4EC5\u4F9B\u7814\u7A76\u53C2\u8003\uFF0C\u4E0D\u6784\u6210\u6295\u8D44\u5EFA\u8BAE\uFF1B\u6570\u636E\u7531\u7B2C\u4E09\u65B9\u63A5\u53E3\u63D0\u4F9B\uFF0C\u51C6\u786E\u6027\u4E0D\u4F5C\u4FDD\u8BC1\u3002",
  "errorLoad": "\u5DE5\u4F5C\u53F0\u52A0\u8F7D\u5931\u8D25",
  "retry": "\u91CD\u8BD5"
};
var dictionaries = {
  zh: { ...zh },
  en: {
    "nav": "Stock Workbench",
    "navDataSources": "Data Sources",
    "title": "A-share Quant Research Workbench",
    "subtitle": "KStock skill pack \xB7 41 research skills + strategy/factor/selection/report libraries",
    "refresh": "Refresh",
    "refreshing": "Loading\u2026",
    "skillsCount": "{count} skills",
    "dataSourceHint": "Keys are written only to this machine (mode 0600), never echoed or uploaded; the agent sources this file before running skill scripts.",
    "tushareLabel": "Tushare Pro Token",
    "tushareHint": "From tushare.pro profile; primary market/financial/macro source",
    "iwencaiLabel": "iWenCai API Key",
    "iwencaiHint": "From iWenCai open platform; natural-language data channel",
    "configured": "Configured",
    "notConfigured": "Not set",
    "keepBlank": "Configured \u2014 leave blank to keep",
    "save": "Save credentials",
    "saving": "Saving\u2026",
    "saved": "Saved: {keys}",
    "saveFailed": "Save failed",
    "secretsUnavailable": "Data directory is not writable; check permissions of {home}",
    "settingsIntro": "A-share research data-source credentials: skill scripts read Tushare / iWenCai keys from the secrets file; changes here write ~/.dsh-stock/secrets.env (0600).",
    "tabStrategies": "Strategies",
    "tabFactors": "Factors",
    "tabSelections": "Selections",
    "tabReports": "Reports",
    "newResearch": "New research task",
    "emptyLibrary": "The library is empty: ask the agent to backtest a strategy / test a factor / run a screening in chat \u2014 it registers versions and runs via strategy_* / factor_* / selection_* tools.",
    "openDetail": "Open",
    "backToList": "Back to list",
    "versions": "Version timeline",
    "runs": "Run archive",
    "latest": "Latest",
    "rerun": "Rerun this version",
    "compare": "Compare runs",
    "compareHint": "Check 2-4 runs to compare metrics side by side; strategies/factors also overlay equity / cumulative-IC curves (strictly comparable only when scopes match).",
    "curveEquity": "Equity curves overlaid (normalized to a common start)",
    "curveCumIc": "Cumulative IC curves overlaid",
    "curveLoading": "Loading curve data\u2026",
    "curveMissingEquity": "Selected runs have no equity data (not stored via *_record), so curves cannot be overlaid.",
    "curveMissingIc": "Selected runs have no IC series data (not stored via *_record), so curves cannot be overlaid.",
    "noRuns": "No runs archived yet: the agent registers here with the *_record tool after each {label}.",
    "emptyReports": "The report library is empty: ask the agent for an HTML dashboard (html-report skill) \u2014 it archives the self-contained file here via the report_archive tool.",
    "reportRisk": "Risk",
    "reportOpenNew": "Open in new window",
    "reportPreview": "Report preview",
    "reportNoContent": "Report content was not archived; ask the agent to archive it again.",
    "hypothesis": "Hypothesis",
    "criteria": "Criteria",
    "category": "Category",
    "statusLabel": "Status",
    "currentVersion": "Current version",
    "researchTaskPrompt": "Run a {label} research task using this plugin's skills and register the outcome: read the relevant SKILL.md first; when done, save via the matching *_save_version / *_record tools (copy scopes verbatim) so I can review it in the workbench.",
    "rerunPrompt": 'Rerun "{name}" from the workbench {library}: locate {object_id} via {toolPrefix}_list, read the current snapshot (v{version}) via {toolPrefix}_get_latest, reproduce the {label} flow per its scope, then register a new run with the matching *_record tool (copy parameters and scopes verbatim). Do not alter the version snapshot.',
    "sendFailed": "Could not deliver to a session automatically; content copied to clipboard \u2014 paste and send it.",
    "requires": "Requires {names}",
    "sectionNotes": "Conventions",
    "note1": "Skill scripts run inside the plugin root; artifacts (HTML reports / charts / JSON / Excel) go to the current working directory.",
    "note2": "Data priority: Tushare structured API > iWenCai natural language > free sources (akshare) / web search.",
    "note3": "Missing data is reported honestly and never fabricated; key conclusions must state source and method.",
    "note4": "Strategies / factors / selections are versioned assets and reports archive into the report library: the workbench shows timelines, run comparisons, report dashboards, and one-click reruns.",
    "disclaimer": "For research reference only, not investment advice; data comes from third-party APIs without accuracy warranty.",
    "errorLoad": "Failed to load workbench",
    "retry": "Retry"
  }
};

// src/client/styles.ts
var STYLE_ID = "kss-workbench-styles";
var CSS = `
.kss-panel, .kss-root {
  --kss-fg: var(--dsw-alias-label-primary, #ececf1);
  --kss-fg-secondary: var(--dsw-alias-label-secondary, #c0c5cd);
  --kss-fg-muted: var(--dsw-alias-label-tertiary, #9aa0aa);
  --kss-fill: var(--dsw-specific-sidebar-fill, rgba(127, 127, 127, 0.08));
  --kss-fill-hover: var(--dsw-alias-interactive-bg-hover, rgba(127, 127, 127, 0.1));
  --kss-border: var(--dsw-alias-border-l3, #2c2f36);
  --kss-border-hover: var(--dsw-alias-border-l2, #555);
  --kss-border-strong: var(--dsw-alias-border-l4, rgba(127, 127, 127, 0.48));
  --kss-btn-bg: var(--dsw-alias-button-primary-fill, #f5f5f5);
  --kss-btn-bg-hover: var(--dsw-alias-button-primary-hover, #e8e8e8);
  --kss-btn-fg: var(--dsw-alias-label-primary-foreground, #141518);
  --kss-focus: var(--dsw-alias-state-business-primary, #4c6ef5);
  --kss-error: var(--dsw-alias-state-error-primary, #d64545);
  --kss-success: var(--dsw-alias-state-success-primary, #2f9e6e);
  --kss-info: var(--dsw-alias-state-business-primary, #4c6ef5);
  --kss-warn: var(--dsw-alias-state-warn-primary, #d9a514);
}
.kss-panel{display:flex;flex-direction:column;height:100%;min-height:0;overflow:auto;gap:20px;padding:28px clamp(24px,4vw,48px) 48px;font-size:13px;line-height:1.6;color:var(--kss-fg);background:var(--dsw-alias-bg-base,#101114)}
.kss-panel > *{width:100%;max-width:960px;align-self:center}
.kss-root{display:flex;flex-direction:column;gap:16px;max-width:760px;color:var(--kss-fg);font-size:13px;line-height:1.6}
/* \u9875\u6807\u9898\u884C\uFF0820/28/500 \u6807\u9898 + \u4E09\u7EA7\u7070\u526F\u9898\uFF0C\u81EA\u52A8\u5316\u4EFB\u52A1\u9875\u540C\u89C4\u683C\uFF09 */
.kss-header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.kss-title{margin:0;font-size:20px;line-height:28px;font-weight:500}
.kss-subtitle{margin:2px 0 0;font-size:13px;line-height:21px;color:var(--kss-fg-muted)}
.kss-badges{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
/* \u80F6\u56CA tab\uFF1A\u53D1\u4E1D\u7EBF\u80F6\u56CA\uFF0C\u6FC0\u6D3B=\u4E2D\u6027\u4E3B\u80F6\u56CA\uFF08button-primary-fill\uFF09 */
.kss-tabs{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.kss-tab{appearance:none;height:28px;padding:0 14px;border:.5px solid var(--kss-border);border-radius:999px;background:transparent;color:var(--kss-fg-muted);font:inherit;font-size:13px;line-height:20px;cursor:pointer;transition:border-color .15s,background .15s,color .15s}
.kss-tab:hover{border-color:var(--kss-border-hover);background:var(--kss-fill-hover)}
.kss-tab.is-active{border-color:transparent;background:var(--kss-btn-bg);color:var(--kss-btn-fg);font-weight:500}
.kss-tabs-spacer{flex:1}
/* \u4E2D\u6027\u80F6\u56CA\u6309\u94AE\uFF08h32/r16\uFF0C\u4E3B\u6309\u94AE=button-primary-fill\uFF1B\u6B21\u6309\u94AE=\u53D1\u4E1D\u7EBF\uFF09 */
.kss-btn{appearance:none;display:inline-flex;align-items:center;justify-content:center;gap:4px;height:32px;padding:0 12px;border:.5px solid var(--kss-border);border-radius:16px;background:transparent;color:var(--kss-fg);font:inherit;font-size:13px;line-height:20px;cursor:pointer;transition:border-color .15s,background .15s}
.kss-btn:hover:not(:disabled){border-color:var(--kss-border-hover);background:var(--kss-fill-hover)}
.kss-btn:disabled{opacity:.4;cursor:not-allowed}
.kss-btn.is-primary{border-color:transparent;background:var(--kss-btn-bg);color:var(--kss-btn-fg)}
.kss-btn.is-primary:hover:not(:disabled){background:var(--kss-btn-bg-hover)}
/* \u5361\u7247\uFF08\u5BB6\u65CF\u540C\u6B3E\uFF1A\u900F\u660E\u5E95 + \u53D1\u4E1D\u7EBF + 12px \u5706\u89D2\uFF0Chover \u63D0\u4EAE\uFF09 */
.kss-card{border:.5px solid var(--kss-border);border-radius:12px;background:transparent;padding:16px;display:flex;flex-direction:column;gap:12px}
.kss-card-title{margin:0;font-size:14px;line-height:22px;font-weight:500}
.kss-card-hint{margin:0;font-size:13px;line-height:21px;color:var(--kss-fg-muted)}
.kss-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.kss-skill{display:flex;flex-direction:column;gap:6px;border:.5px solid var(--kss-border);border-radius:12px;padding:14px 16px;background:transparent;transition:border-color .15s,background .15s}
.kss-skill:hover{border-color:var(--kss-border-hover);background:var(--kss-fill-hover)}
.kss-skill-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
.kss-skill-name{overflow:hidden;font-size:14px;line-height:22px;font-weight:500;text-overflow:ellipsis;white-space:nowrap}
.kss-skill-copy{appearance:none;flex:none;height:24px;padding:0 10px;border:.5px solid var(--kss-border);border-radius:12px;background:transparent;color:var(--kss-fg-muted);font:inherit;font-size:12px;line-height:20px;cursor:pointer;transition:border-color .15s,background .15s,color .15s}
.kss-skill-copy:hover{border-color:var(--kss-border-hover);background:var(--kss-fill-hover);color:var(--kss-fg)}
.kss-skill-desc{margin:0;font-size:13px;line-height:21px;color:var(--kss-fg-muted);overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.kss-skill-keys{font-size:12px;color:var(--kss-warn)}
.kss-skill-meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px;color:var(--kss-fg-muted)}
/* \u72B6\u6001\u5FBD\u6807\uFF1A\u4F4E\u9971\u548C\u5E95 + \u72B6\u6001\u8272\u6587\u5B57\uFF08notice \u8272\u7CFB\uFF09 */
.kss-badge{display:inline-flex;align-items:center;gap:4px;padding:1px 8px;border-radius:999px;font-size:11px;line-height:18px;background:var(--kss-fill);color:var(--kss-fg-muted)}
.kss-badge.is-ok{color:var(--kss-success);background:color-mix(in srgb, var(--kss-success) 12%, transparent)}
.kss-badge.is-miss{color:var(--kss-warn);background:color-mix(in srgb, var(--kss-warn) 12%, transparent)}
/* \u7248\u672C\u65F6\u95F4\u7EBF\uFF1A\u53D1\u4E1D\u7EBF\u884C\uFF0Chover \u63D0\u4EAE */
.kss-versions{display:flex;flex-direction:column;gap:6px}
.kss-version-row{display:flex;align-items:center;gap:10px;padding:8px 12px;border:.5px solid var(--kss-border);border-radius:10px;background:transparent;transition:background .15s}
.kss-version-row:hover{background:var(--kss-fill-hover)}
.kss-version-tag{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;font-weight:600;color:var(--kss-fg-secondary)}
.kss-table{width:100%;border-collapse:collapse;font-size:12px}
.kss-table th,.kss-table td{border-bottom:.5px solid var(--kss-border);padding:6px 8px;text-align:left;white-space:nowrap}
.kss-table th{color:var(--kss-fg-muted);font-weight:500}
.kss-mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
/* \u5206\u7EC4\u6807\u9898\u4E0E\u53CD\u9988\uFF08notice \u8272\u7CFB\uFF09 */
.kss-group-title{margin:0 0 8px;font-size:13px;line-height:21px;font-weight:500;color:var(--kss-fg-secondary)}
.kss-feedback{font-size:12px;line-height:20px}
.kss-feedback.is-warn{color:var(--kss-warn)}
.kss-feedback.is-ok{color:var(--kss-success)}
.kss-feedback.is-err{color:var(--kss-error)}
/* \u8868\u5355\u5B57\u6BB5\uFF1A\u53D1\u4E1D\u7EBF\u63A7\u4EF6 + 12px \u5706\u89D2 + \u805A\u7126\u63CF\u8FB9\u4E0D\u6253\u73AF\uFF08searchField \u53E3\u5F84\uFF09 */
.kss-fields{display:flex;flex-direction:column;gap:18px;margin-top:4px}
.kss-field{display:flex;flex-direction:column;gap:6px}
.kss-field-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
.kss-label{font-size:13px;line-height:21px;font-weight:400;color:var(--kss-fg-muted)}
.kss-input{width:100%;box-sizing:border-box;height:36px;padding:0 12px;border:.5px solid var(--kss-border);border-radius:12px;background:transparent;color:var(--kss-fg);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px;letter-spacing:.3px;transition:border-color .15s}
.kss-input:hover{border-color:var(--kss-border-hover)}
.kss-input:focus{outline:none;border-color:var(--kss-focus)}
.kss-input::placeholder{color:var(--kss-fg-muted);letter-spacing:0}
.kss-path{display:inline-block;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;color:var(--kss-fg-secondary);background:var(--kss-fill);border-radius:6px;padding:2px 8px}
.kss-field-hint{font-size:12px;line-height:20px;color:var(--kss-fg-muted)}
.kss-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
/* \u7EA6\u5B9A/\u8BF4\u660E\uFF08notice \u5757\u53E3\u5F84\uFF09 */
.kss-notes{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:5px;font-size:12px;line-height:20px;color:var(--kss-fg-secondary)}
.kss-footer{font-size:12px;line-height:20px;color:var(--kss-fg-muted)}
/* \u8FD0\u884C\u5BF9\u6BD4\u66F2\u7EBF\uFF08SVG \u5750\u6807\u8272\u968F\u6587\u5B57\u5C42\u7EA7\uFF09 */
.kss-compare{overflow-x:auto}
.kss-curve-block{display:flex;flex-direction:column;gap:6px;margin-top:4px}
.kss-curve-svg{display:block;width:100%;max-width:640px;height:auto}
.kss-curve-grid{stroke:var(--kss-border-strong);stroke-width:1;stroke-dasharray:3 3;fill:none}
.kss-curve-axis{fill:var(--kss-fg-muted);font-size:10px}
.kss-curve-legend{fill:var(--kss-fg-secondary);font-size:11px}
.kss-curve-line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
/* \u62A5\u544A\u5185\u5D4C\u9884\u89C8\uFF1A\u53D1\u4E1D\u7EBF + 12px \u5706\u89D2 */
.kss-report-frame{width:100%;min-height:560px;height:64vh;border:.5px solid var(--kss-border);border-radius:12px;background:var(--kss-fill);display:block}
.kss-state{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:56px 0;color:var(--kss-fg-muted);font-size:13px;line-height:21px}
.kss-error{color:var(--kss-error);font-size:12px;line-height:20px;word-break:break-all}
`;
function installStyles() {
  let el = document.getElementById(STYLE_ID);
  if (el !== null) return () => {
  };
  el = document.createElement("style");
  el.id = STYLE_ID;
  el.textContent = CSS;
  document.head.append(el);
  return () => {
    el?.remove();
    el = null;
  };
}

// src/client/index.tsx
var import_jsx_runtime4 = require("react/jsx-runtime");
var name = "dsh-skills-stock";
var inject = [
  "slots",
  "locale",
  "layout",
  "connection",
  "sessions",
  "conversation",
  "uiWorkspace",
  "workspaces"
];
var PANEL_ID = "kss-workbench";
function bindTranslator(ctx) {
  const localeService = ctx.locale;
  if (localeService?.register !== void 0) {
    ctx.effect(() => localeService.register(NS, { zh: { ...zh }, en: { ...dictionaries.en } }), "kss: dictionaries");
  }
  return localeService?.bind !== void 0 ? localeService.bind(NS) : (key, params) => {
    const template = zh[key] ?? key;
    if (params === void 0) return template;
    return template.replace(/\{(\w+)\}/g, (_match, name2) => String(params[name2] ?? `{${name2}}`));
  };
}
function createRuntime(ctx) {
  return createWorkbenchRuntime({
    rpc: {
      call: (channel, endpoint, payload) => {
        if (ctx.connection?.rpc === void 0) {
          return Promise.reject(new Error("\u6295\u7814\u5DE5\u4F5C\u53F0\u901A\u9053\u4E0D\u53EF\u7528 (the workbench channel is unavailable)"));
        }
        return ctx.connection.rpc.call(channel, endpoint, payload);
      }
    }
  });
}
function apply(ctx) {
  const disposeStyles = installStyles();
  const t = bindTranslator(ctx);
  const runtime = createRuntime(ctx);
  const bridge = createConversationBridge(ctx);
  if (ctx.slots?.inject !== void 0) {
    try {
      ctx.slots.inject("sidebar.panellist", () => {
        const disposeIcon = ctx.slots.register({
          name: "sidebar.panellist",
          id: PANEL_ID,
          order: 125,
          label: () => t("nav"),
          locale: NS
        }, PanelIcon);
        const disposePanel = ctx.slots.register({
          name: "main",
          key: PANEL_ID,
          locale: NS
        }, function WorkbenchMount() {
          return /* @__PURE__ */ (0, import_jsx_runtime4.jsx)(WorkbenchView, { t, runtime, bridge });
        });
        return () => {
          disposePanel();
          disposeIcon();
        };
      });
    } catch (error) {
      console.warn("[dsh-skills-stock] sidebar/main slot registration skipped:", error);
    }
    try {
      ctx.slots.inject("settings.section", () => ctx.slots.register(
        { name: "settings.section", id: "kstock-data-sources", order: 20, label: () => t("navDataSources"), locale: NS },
        function DataSourcesMount() {
          return /* @__PURE__ */ (0, import_jsx_runtime4.jsx)(DataSourcesSettingsView, { t, runtime });
        }
      ));
    } catch (error) {
      console.warn("[dsh-skills-stock] settings.section slot registration skipped:", error);
    }
  }
  ctx.effect(() => disposeStyles, "kss: styles");
}
function PanelIcon(props) {
  const size = props.size ?? 18;
  return /* @__PURE__ */ (0, import_jsx_runtime4.jsxs)(
    "svg",
    {
      width: size,
      height: size,
      viewBox: "0 0 24 24",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: 1.9,
      strokeLinecap: "round",
      strokeLinejoin: "round",
      "aria-hidden": "true",
      children: [
        /* @__PURE__ */ (0, import_jsx_runtime4.jsx)("path", { d: "M4 4v16" }),
        /* @__PURE__ */ (0, import_jsx_runtime4.jsx)("path", { d: "M20 4v16" }),
        /* @__PURE__ */ (0, import_jsx_runtime4.jsx)("path", { d: "M8 8.5h3" }),
        /* @__PURE__ */ (0, import_jsx_runtime4.jsx)("path", { d: "M9.5 6.5v7" }),
        /* @__PURE__ */ (0, import_jsx_runtime4.jsx)("path", { d: "M13 11h3" }),
        /* @__PURE__ */ (0, import_jsx_runtime4.jsx)("path", { d: "M14.5 9v7" }),
        /* @__PURE__ */ (0, import_jsx_runtime4.jsx)("path", { d: "M3 20h18" })
      ]
    }
  );
}
return module.exports; } });
//# sourceMappingURL=client.js.map
