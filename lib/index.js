// src/index.ts
import { readFileSync as readFileSync3, rmSync as rmSync3 } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join as join4 } from "node:path";

// src/guidance.ts
var SECTION_ORDER = 209;
var KSTOCK_GUIDANCE = `\u672C\u673A\u5DF2\u5B89\u88C5 dsh-skills-stock \u63D2\u4EF6\uFF08A \u80A1\u91CF\u5316\u6295\u7814\u6280\u80FD\u5305\uFF1A30 \u4E2A runtime skill + \u7B56\u7565/\u56E0\u5B50/\u9009\u80A1\u4E09\u5E93\u5DE5\u4F5C\u533A + \u6295\u7814\u5DE5\u4F5C\u53F0\u9762\u677F\uFF09\u3002\u6D89\u53CA A \u80A1/\u57FA\u91D1/\u671F\u8D27/\u671F\u6743/\u5B8F\u89C2\u7684\u91CF\u5316\u7814\u7A76\u9700\u6C42\u65F6\uFF0C\u5148\u6309\u4E0B\u9762\u8DEF\u7531\u4ECE available_skills \u9009\u7528\u6280\u80FD\u3001\u8BFB\u5176 SKILL.md \u540E\u52A8\u624B\uFF0C\u4E0D\u8981\u5F92\u624B\u91CD\u5199\u5DF2\u6709\u811A\u672C\u80FD\u529B\u3002\u9700\u6C42\u8DEF\u7531\uFF1A1) \u5355\u53EA A \u80A1\u6DF1\u5EA6\u5206\u6790\uFF08\u6280\u672F/\u8D22\u52A1/\u7B79\u7801/\u4F30\u503C/\u7F20\u8BBA/\u6CE2\u6D6A/\u8C10\u6CE2/\u8206\u60C5/\u80A1\u4E1C\u4EFB\u4E00\u7EF4\u5EA6\uFF09\u2192 stock-analysis\uFF1B2) \u4E09\u5927\u62A5\u8868\u89E3\u8BFB \u2192 financial-statement\uFF0C\u5238\u5546\u76C8\u5229\u9884\u6D4B \u2192 earnings-forecast\uFF0C\u76C8\u5229\u4FEE\u6B63 \u2192 earnings-revision\uFF1B3) \u76F8\u5BF9\u4F30\u503C\uFF08PE-Band/PB-ROE/\u5206\u4F4D/\u4F30\u503C\u9677\u9631\uFF09\u2192 valuation-model\uFF0CDCF \u7EDD\u5BF9\u4F30\u503C\u5EFA\u6A21 \u2192 dcf\uFF1B4) \u81EA\u7136\u8BED\u8A00\u6761\u4EF6\u9009\u80A1 \u2192 a-stock-screener\uFF0C\u5341\u5927\u65E2\u5B9A\u7B56\u7565\u8DD1\u6279 \u2192 selection-strategies\uFF1B5) \u56E0\u5B50\u7814\u7A76 \u2192 factor-research\uFF0C\u7B56\u7565\u8BBE\u8BA1\u4E0E\u56DE\u6D4B \u2192 strategy-research\uFF08backtrader-strategies \u662F\u88AB\u5F15\u7528\u7684\u7B56\u7565\u9002\u914D\u5668\u5E93\uFF09\uFF1B6) \u53EF\u8F6C\u503A \u2192 cb-analysis\uFF0CETF \u2192 etf-analysis\uFF0C\u80A1\u6307\u671F\u8D27 \u2192 futures-analysis\uFF0C\u671F\u6307\u671F\u6743\u8054\u52A8 \u2192 option-futures-linkage\uFF0C\u671F\u6743\u5B9A\u4EF7/\u591A\u817F\u76C8\u4E8F \u2192 options-payoff\uFF0C\u6CE2\u52A8\u7387\u66F2\u9762 \u2192 options-volatility\uFF1B7) \u80A1\u503A\u6C47\u5546 8 \u7EF4\u5E02\u573A\u8054\u52A8\u4F53\u68C0 \u2192 market-linkage-engine\uFF0C\u884C\u4E1A\u753B\u50CF/\u4EA7\u4E1A\u94FE \u2192 industry-analysis\uFF1B8) \u6570\u636E\u67E5\u8BE2\uFF1A\u5DF2\u77E5 Tushare \u63A5\u53E3 \u2192 tushare-data\uFF1B\u81EA\u7136\u8BED\u8A00\u67E5\u6570\u636E\u8D70\u95EE\u8D22\u516B\u4EF6\u5957\uFF08zhishu-query \u6307\u6570 / announcement-search \u516C\u544A / news-search \u65B0\u95FB / report-search \u7814\u62A5 / business-query \u7ECF\u8425 / macro-query \u5B8F\u89C2 / event-query \u4E8B\u4EF6 / hithink-futures \u671F\u8D27\u671F\u6743\uFF09\uFF1B9) 26 \u79CD\u4E13\u4E1A\u56FE\u8868 \u2192 chart-visualization\uFF1B10) common \u662F\u516C\u5171\u6570\u636E\u7F51\u5173\u5E93\uFF08kk_common\uFF09\uFF0C\u7531\u5176\u4ED6\u6280\u80FD\u811A\u672C\u81EA\u52A8\u5F15\u7528\uFF0C\u4E0D\u8981\u5355\u72EC\u6FC0\u6D3B\u3002\u4E09\u5E93\u5DE5\u4F5C\u533A\uFF08\u6D3B\u8D44\u4EA7\u7BA1\u7406\uFF0C\u5BBF\u4E3B\u5DF2\u6CE8\u518C strategy_* / factor_* / selection_* \u5404 5 \u4E2A\u5DE5\u5177\uFF09\uFF1A\u7B56\u7565\u5E93 strategy_list/create/get_latest/save_version/record_backtest\uFF0C\u56E0\u5B50\u5E93 factor_* \u540C\u6784\uFF08record_run\uFF09\uFF0C\u9009\u80A1\u5E93 selection_*\uFF08criteria_json.summary \u5FC5\u586B\uFF0Crecord_run \u5F52\u6863\u62A5\u544A\u4E0E\u547D\u4E2D\u6E05\u5355\uFF09\u3002\u7EAA\u5F8B\uFF1A\u7B56\u7565/\u56E0\u5B50\u4EE3\u7801\u4E0E\u9009\u80A1\u53E3\u5F84\u5FC5\u987B\u7ECF save_version \u5165\u5E93\uFF08\u7981\u6B62\u53EA\u7559\u5728\u4F1A\u8BDD\u5DE5\u4F5C\u533A\uFF09\uFF0C\u56DE\u6D4B/\u68C0\u9A8C\u540E\u5FC5\u987B record \u5F52\u6863\u8FD0\u884C\uFF08rules/config \u539F\u6837\u6284\u5F55\uFF0C\u5426\u5219\u8DE8\u7248\u672C\u5BF9\u6BD4\u53E3\u5F84\u5931\u6548\uFF09\uFF1B\u65B0\u7248\u672C\u52A3\u4E8E\u65E7\u7248\u672C\u8981\u5982\u5B9E\u5448\u73B0\u5E76\u5728 change_note \u5199\u300C\u8BC1\u4F2A\u300D\uFF1B\u7528\u6237\u8BF4\u300C\u7EE7\u7EED/\u6539\u8FDB/\u5BF9\u6BD4\u4E4B\u524D\u7684\u7B56\u7565\uFF08\u6216\u56E0\u5B50/\u9009\u80A1\uFF09\u300D\u65F6\u5148 *_list \u5B9A\u4F4D\u518D *_get_latest \u8FED\u4EE3\uFF1B\u7ED3\u679C\u544A\u77E5\u7528\u6237\u53EF\u5728\u4FA7\u8FB9\u680F\u300C\u6295\u7814\u5DE5\u4F5C\u53F0\u300D\u5BF9\u5E94\u5E93\u67E5\u770B\u7248\u672C\u65F6\u95F4\u7EBF\u3001\u8FD0\u884C\u5BF9\u6BD4\u4E0E\u91CD\u8DD1\u3002\u8DE8\u6280\u80FD\u7EA6\u5B9A\uFF1A\u6280\u80FD\u811A\u672C\u5728\u63D2\u4EF6\u5305\u6839\u5185\uFF08\u5305\u6839\u4EE5\u6FC0\u6D3B\u63D0\u793A skill_resources \u7ED9\u51FA\u7684\u7EDD\u5BF9\u8DEF\u5F84\u4E3A\u51C6\uFF0C\u4E0D\u8981\u731C\u6D4B\uFF09\uFF0C\u4EA7\u7269\uFF08\u62A5\u544A HTML\u3001\u56FE\u8868\u3001JSON\u3001Excel\uFF09\u4E00\u5F8B\u5199\u5165\u5F53\u524D\u5DE5\u4F5C\u76EE\u5F55\uFF1B\u6570\u636E\u5BC6\u94A5\uFF08TUSHARE_TOKEN / IWENCAI_API_KEY\uFF09\u8D70\u51ED\u636E\u6587\u4EF6 <\u6570\u636E\u6839>/secrets.env\u2014\u2014\u6570\u636E\u6839\u662F\u5BBF\u4E3B home \u4E0B\u7684 dsh-skills-stock/ \u76EE\u5F55\uFF08\u5BBF\u4E3B home \u6309 $QILIN_HOME \u2192 $DSH_HOME \u2192 ~/.dsh \u89E3\u6790\uFF0C\u672A\u8BBE\u73AF\u5883\u53D8\u91CF\u65F6\u5373 ~/.dsh/dsh-skills-stock\uFF1B\u4EE5\u5DE5\u4F5C\u53F0\u8BBE\u7F6E\u9875\u300C\u6570\u636E\u6E90\u300D\u663E\u793A\u7684\u7EDD\u5BF9\u8DEF\u5F84\u4E3A\u51C6\uFF09\u2014\u2014dsh \u4F1A\u628A\u540D\u5B57\u542B TOKEN/KEY/SECRET/PASSWORD \u7684\u8FDB\u7A0B\u73AF\u5883\u53D8\u91CF\u4ECE bash \u5B50\u8FDB\u7A0B\u5265\u79BB\uFF0C\u8FD0\u884C\u811A\u672C\u524D\u5728\u540C\u4E00\u6761 bash \u547D\u4EE4\u91CC set -a; source <\u6570\u636E\u6839>/secrets.env; set +a \u540E\u518D\u6267\u884C\uFF0C\u7528\u6237\u672A\u914D\u7F6E\u65F6\u5F15\u5BFC\u5176\u5230\u8BBE\u7F6E\u9875\u300C\u6570\u636E\u6E90\u300D\u586B\u5199\uFF1B\u6570\u636E\u8BBF\u95EE\u4F18\u5148\u7EA7 Tushare \u7ED3\u6784\u5316\u63A5\u53E3 > \u540C\u82B1\u987A\u95EE\u8D22\u81EA\u7136\u8BED\u8A00\u67E5\u8BE2 > \u514D\u8D39\u6E90\uFF08akshare\uFF09/\u7F51\u7EDC\u641C\u7D22\u515C\u5E95\uFF0C\u6570\u636E\u7F3A\u5931\u65F6\u5982\u5B9E\u6807\u6CE8\uFF0C\u7981\u6B62\u7F16\u9020\u6570\u636E\uFF1B\u7814\u7A76\u62A5\u544A\u9ED8\u8BA4\u4EA4\u4ED8\u5355\u6587\u4EF6\u79BB\u7EBF HTML\uFF08\u5185\u5D4C\u56FE\u8868\uFF0C\u53CC\u51FB\u53EF\u6253\u5F00\uFF09\uFF0C\u843D\u76D8\u540E\u544A\u77E5\u8DEF\u5F84\uFF0C\u4E0D\u6574\u4EFD\u8D34\u8FDB\u5BF9\u8BDD\uFF1B\u5168\u90E8\u8F93\u51FA\u4EC5\u4F9B\u7814\u7A76\u53C2\u8003\uFF0C\u4E0D\u6784\u6210\u6295\u8D44\u5EFA\u8BAE\u3002`;

// src/library.ts
import { existsSync as existsSync2, mkdirSync as mkdirSync2, readFileSync, readdirSync as readdirSync2, renameSync as renameSync2, rmSync as rmSync2, writeFileSync } from "node:fs";
import { createHash, randomBytes } from "node:crypto";
import { join as join2 } from "node:path";

// src/stock-home.ts
import { existsSync, mkdirSync, readdirSync, renameSync, rmSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
function userHome() {
  const fromEnv = process.env.HOME;
  return fromEnv !== void 0 && fromEnv.trim() !== "" ? fromEnv : homedir();
}
function harnessHome() {
  const fromEnv = process.env.QILIN_HOME ?? process.env.DSH_HOME;
  return fromEnv !== void 0 && fromEnv.trim() !== "" ? fromEnv : join(userHome(), ".dsh");
}
function stockHome() {
  return join(harnessHome(), "dsh-skills-stock");
}
function secretsPath() {
  return join(stockHome(), "secrets.env");
}
function legacyStockHomes() {
  return [.../* @__PURE__ */ new Set([join(userHome(), ".dsh-stock"), join(homedir(), ".dsh-stock")])];
}
function migrateLegacyStockHome() {
  try {
    const root = stockHome();
    for (const legacy of legacyStockHomes()) {
      if (legacy === root || !existsSync(legacy)) continue;
      mkdirSync(root, { recursive: true });
      for (const entry of readdirSync(legacy)) {
        const target = join(root, entry);
        if (existsSync(target)) continue;
        renameSync(join(legacy, entry), target);
      }
      if (readdirSync(legacy).length === 0) rmSync(legacy, { recursive: true, force: true });
    }
  } catch {
  }
}
function legacyPresetDirs() {
  const dirs = /* @__PURE__ */ new Set([
    join(harnessHome(), ".agent-presets", "dsh-skills-stock"),
    join(userHome(), ".dsh", ".agent-presets", "dsh-skills-stock")
  ]);
  return [...dirs];
}

// src/library.ts
var LIBRARY_KINDS = ["strategies", "factors", "selections"];
var CAPS = {
  code: 512 * 1024,
  params: 64 * 1024,
  metrics: 64 * 1024,
  rules: 16 * 1024,
  curve: 2 * 1024 * 1024,
  // equity / ic_series / report
  detail: 4 * 1024 * 1024
  // trades / layers / picks
};
var KIND_CONFIG = {
  strategies: { idPrefix: "stg_", runPrefix: "srun_", statuses: ["researching", "paused", "rejected"], autoVersionOnCreate: false },
  factors: { idPrefix: "fac_", runPrefix: "frun_", statuses: ["researching", "adopted", "paused", "rejected"], autoVersionOnCreate: false },
  selections: { idPrefix: "sel_", runPrefix: "xrun_", statuses: ["watching", "archived", "closed"], autoVersionOnCreate: true }
};
var RUN_PAYLOAD_KEYS = ["equity", "ic_series", "report", "trades", "layers", "picks"];
function lightRun(run) {
  const out = { ...run };
  for (const key of RUN_PAYLOAD_KEYS) delete out[key];
  return out;
}
var LibraryError = class extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
    this.name = "LibraryError";
  }
};
function isLibraryKind(value) {
  return typeof value === "string" && LIBRARY_KINDS.includes(value);
}
function kindConfig(kind) {
  return KIND_CONFIG[kind];
}
var LibraryStore = class _LibraryStore {
  root;
  constructor(root = join2(stockHome(), "product")) {
    this.root = root;
  }
  dir(kind, objectId) {
    return objectId === void 0 ? join2(this.root, kind) : join2(this.root, kind, objectId);
  }
  objectPath(kind, objectId) {
    return join2(this.dir(kind, objectId), "object.json");
  }
  versionPath(kind, objectId, version) {
    return join2(this.dir(kind, objectId), "versions", `v${String(version).padStart(3, "0")}.json`);
  }
  runPath(kind, objectId, runId) {
    return join2(this.dir(kind, objectId), "runs", `${runId}.json`);
  }
  readJson(path) {
    try {
      return JSON.parse(readFileSync(path, "utf8"));
    } catch {
      return void 0;
    }
  }
  writeJson(path, value) {
    mkdirSync2(_LibraryStore.dirname(path), { recursive: true });
    const tmp = `${path}.tmp-${process.pid}-${Date.now()}`;
    writeFileSync(tmp, JSON.stringify(value, null, 2), { mode: 384 });
    renameSync2(tmp, path);
  }
  static dirname(path) {
    const at = path.lastIndexOf("/");
    return at > 0 ? path.slice(0, at) : ".";
  }
  static now() {
    return (/* @__PURE__ */ new Date()).toISOString();
  }
  newId(kind) {
    return kindConfig(kind).idPrefix + randomBytes(6).toString("hex");
  }
  requireObject(kind, objectId) {
    const object = this.readJson(this.objectPath(kind, objectId));
    if (object === void 0) {
      throw new LibraryError("not-found", `${kind}/${objectId} \u4E0D\u5B58\u5728\uFF08\u5148\u7528 list \u5B9A\u4F4D\uFF0C\u6216 create \u521B\u5EFA\uFF09`);
    }
    return object;
  }
  assertSize(label, value, cap) {
    if (value === void 0 || value === null) return;
    const bytes = typeof value === "string" ? Buffer.byteLength(value) : Buffer.byteLength(JSON.stringify(value));
    if (bytes > cap) {
      throw new LibraryError("too-large", `${label} \u8D85\u51FA\u5BB9\u91CF\u4E0A\u9650\uFF08${bytes} > ${cap} \u5B57\u8282\uFF09`);
    }
  }
  assertVersionPayload(kind, payload) {
    if (kind === "selections") {
      const criteria = payload["criteria_json"];
      if (typeof criteria !== "object" || criteria === null || Array.isArray(criteria)) {
        throw new LibraryError("invalid", "selection_save_version \u9700\u8981 criteria_json \u5BF9\u8C61\uFF08\u9009\u80A1\u8981\u6C42\u7ED3\u6784\u5316\u53E3\u5F84\uFF09");
      }
      const summary = criteria["summary"];
      if (typeof summary !== "string" || summary.trim() === "") {
        throw new LibraryError("invalid", "criteria_json.summary \u5FC5\u586B\uFF08\u4E00\u53E5\u8BDD\u9009\u80A1\u53E3\u5F84\uFF0C\u7528\u4E8E\u5E93\u5185\u5B9A\u4F4D\u4E0E\u590D\u7528\uFF09");
      }
      this.assertSize("criteria_json", criteria, CAPS.params);
    } else {
      if (typeof payload["code"] !== "string" || payload["code"].trim() === "") {
        throw new LibraryError("invalid", "save_version \u9700\u8981 code \u5B57\u7B26\u4E32\uFF08\u5B8C\u6574\u53EF\u6267\u884C\u7248\u672C\u5FEB\u7167\uFF0C\u7981\u6B62\u53EA\u7559\u5728\u4F1A\u8BDD\u5DE5\u4F5C\u533A\uFF09");
      }
      this.assertSize("code", payload["code"], CAPS.code);
    }
    if (payload["params"] !== void 0) this.assertSize("params", payload["params"], CAPS.params);
    if (typeof payload["change_note"] !== "string" || payload["change_note"].trim() === "") {
      throw new LibraryError("invalid", "change_note \u5FC5\u586B\uFF08\u672C\u7248\u672C\u76F8\u5BF9\u4E0A\u4E00\u7248\u6539\u4E86\u4EC0\u4E48\u3001\u4E3A\u4EC0\u4E48\uFF09");
    }
  }
  /* ── 查询 ── */
  listObjects(kind) {
    const dir = this.dir(kind);
    if (!existsSync2(dir)) return [];
    const out = [];
    for (const entry of readdirSync2(dir)) {
      const object = this.readJson(this.objectPath(kind, entry));
      if (object === void 0) continue;
      const runs = this.listRuns(kind, entry);
      const latest = runs.length > 0 ? runs[runs.length - 1] : void 0;
      out.push({
        ...object,
        object_id: entry,
        library: kind,
        latest_run: latest === void 0 ? void 0 : lightRun(latest),
        run_count: runs.length
      });
    }
    out.sort((a, b) => String(b["updated_at"]).localeCompare(String(a["updated_at"])));
    return out;
  }
  detail(kind, objectId) {
    const object = this.requireObject(kind, objectId);
    return {
      ...object,
      object_id: objectId,
      library: kind,
      versions: this.listVersions(kind, objectId),
      runs: this.listRuns(kind, objectId).map(lightRun)
    };
  }
  /** 运行对比取数：按 run_ids 返回完整归档（含 equity / ic_series 曲线负载）。
   * 任一 run 缺失即整体报 not-found——宁可让 UI 重开详情，也不给静默空曲线。 */
  runsByIds(kind, objectId, runIds) {
    this.requireObject(kind, objectId);
    const out = [];
    for (const runId of runIds) {
      const run = this.readJson(this.runPath(kind, objectId, runId));
      if (run === void 0) throw new LibraryError("not-found", `\u8FD0\u884C ${runId} \u4E0D\u5B58\u5728\uFF08\u5217\u8868\u53EF\u80FD\u5DF2\u8FC7\u671F\uFF0C\u8BF7\u91CD\u5F00\u8BE6\u60C5\u5237\u65B0\uFF09`);
      out.push(run);
    }
    return out;
  }
  listVersions(kind, objectId) {
    const dir = join2(this.dir(kind, objectId), "versions");
    if (!existsSync2(dir)) return [];
    const out = [];
    for (const entry of readdirSync2(dir)) {
      if (!entry.endsWith(".json")) continue;
      const version = this.readJson(join2(dir, entry));
      if (version !== void 0) out.push(version);
    }
    out.sort((a, b) => a.version - b.version);
    return out;
  }
  listRuns(kind, objectId) {
    const dir = join2(this.dir(kind, objectId), "runs");
    if (!existsSync2(dir)) return [];
    const out = [];
    for (const entry of readdirSync2(dir)) {
      if (!entry.endsWith(".json")) continue;
      const run = this.readJson(join2(dir, entry));
      if (run !== void 0) out.push(run);
    }
    out.sort((a, b) => String(a["created_at"]).localeCompare(String(b["created_at"])));
    return out;
  }
  /* ── 写入（agent 工具专用语义） ── */
  createObject(kind, input) {
    const name2 = typeof input.name === "string" ? input.name.trim() : "";
    if (name2 === "") throw new LibraryError("invalid", "name \u5FC5\u586B");
    if (name2.length > 120) throw new LibraryError("invalid", "name \u8FC7\u957F\uFF08\u2264120 \u5B57\uFF09");
    const now = _LibraryStore.now();
    const objectId = this.newId(kind);
    const object = {
      name: name2,
      status: kindConfig(kind).statuses[0],
      current_version: 0,
      created_at: now,
      updated_at: now
    };
    if (kind === "strategies" || kind === "factors") {
      object["hypothesis"] = typeof input.hypothesis === "string" ? input.hypothesis.slice(0, 2e3) : "";
    }
    if (kind === "factors") {
      const categories = ["value", "momentum", "quality", "low_vol", "size", "growth", "custom"];
      const category = typeof input.category === "string" && categories.includes(input.category) ? input.category : "custom";
      object["category"] = category;
    }
    if (kind === "selections") {
      if (typeof input.criteria !== "string" || input.criteria.trim() === "") {
        throw new LibraryError("invalid", "selection_create \u9700\u8981 criteria\uFF08\u4E00\u53E5\u8BDD\u9009\u80A1\u53E3\u5F84\uFF09");
      }
      object["criteria"] = input.criteria.trim().slice(0, 2e3);
    }
    this.writeJson(this.objectPath(kind, objectId), object);
    if (kindConfig(kind).autoVersionOnCreate) {
      const criteriaJson = typeof input.criteria_json === "object" && input.criteria_json !== null ? input.criteria_json : { summary: object["criteria"] };
      this.writeVersion(kind, objectId, { criteria_json: criteriaJson, params: input.params, change_note: "\u521D\u59CB\u9009\u80A1\u8981\u6C42", parent_version: 0 });
    }
    return { object_id: objectId, ...this.readJson(this.objectPath(kind, objectId)), library: kind };
  }
  updateObject(kind, objectId, patch) {
    const object = this.requireObject(kind, objectId);
    if (patch.name !== void 0) {
      const name2 = patch.name.trim();
      if (name2 === "") throw new LibraryError("invalid", "name \u4E0D\u80FD\u4E3A\u7A7A");
      object["name"] = name2;
    }
    if (patch.hypothesis !== void 0) object["hypothesis"] = patch.hypothesis.slice(0, 2e3);
    if (patch.criteria !== void 0) object["criteria"] = patch.criteria.trim().slice(0, 2e3);
    if (patch.category !== void 0) {
      const categories = ["value", "momentum", "quality", "low_vol", "size", "growth", "custom"];
      if (!categories.includes(patch.category)) throw new LibraryError("invalid", `category \u5FC5\u987B\u662F ${categories.join("/")}`);
      object["category"] = patch.category;
    }
    if (patch.status !== void 0) {
      if (!kindConfig(kind).statuses.includes(patch.status)) {
        throw new LibraryError("invalid", `status \u5FC5\u987B\u662F ${kindConfig(kind).statuses.join("/")}`);
      }
      object["status"] = patch.status;
    }
    object["updated_at"] = _LibraryStore.now();
    this.writeJson(this.objectPath(kind, objectId), object);
    return { ...object, object_id: objectId, library: kind };
  }
  writeVersion(kind, objectId, payload) {
    const object = this.requireObject(kind, objectId);
    const parentVersion = typeof payload["parent_version"] === "number" ? payload["parent_version"] : void 0;
    if (parentVersion !== object["current_version"]) {
      throw new LibraryError(
        "version-conflict",
        `\u7248\u672C\u51B2\u7A81\uFF1Aparent_version=${parentVersion} \u4F46\u5F53\u524D\u662F v${object["current_version"]}\uFF08\u5148 get_latest \u8BFB\u53D6\u6700\u65B0\u7248\uFF0C\u5728\u5176\u4E4B\u4E0A\u8FED\u4EE3\uFF09`
      );
    }
    this.assertVersionPayload(kind, payload);
    const version = object["current_version"] + 1;
    const record2 = {
      version,
      parent_version: parentVersion,
      code_sha256: kind === "selections" ? void 0 : createSha256(String(payload["code"])),
      ...payload,
      created_at: _LibraryStore.now()
    };
    if (record2["code_sha256"] === void 0) delete record2["code_sha256"];
    this.writeJson(this.versionPath(kind, objectId, version), record2);
    object["current_version"] = version;
    object["updated_at"] = _LibraryStore.now();
    if (kind === "selections") {
      const criteria = payload["criteria_json"];
      const summary = criteria?.["summary"];
      if (typeof summary === "string" && summary.trim() !== "") object["criteria"] = summary.trim().slice(0, 2e3);
    }
    this.writeJson(this.objectPath(kind, objectId), object);
    return record2;
  }
  saveVersion(kind, objectId, payload) {
    return this.writeVersion(kind, objectId, payload);
  }
  recordRun(kind, objectId, input) {
    const object = this.requireObject(kind, objectId);
    const version = input["version"];
    if (typeof version !== "number" || version < 1 || version > object["current_version"]) {
      throw new LibraryError("invalid", `version \u5FC5\u987B\u662F 1..${object["current_version"]}\uFF08\u5148 save_version \u843D\u7248\u672C\uFF0C\u518D\u767B\u8BB0\u8FD0\u884C\uFF09`);
    }
    this.assertSize("metrics", input["metrics"], CAPS.metrics);
    this.assertSize("rules/config", input["rules"] ?? input["config"], CAPS.rules);
    for (const key of ["equity", "ic_series", "report"]) {
      if (input[key] !== void 0) this.assertSize(key, input[key], CAPS.curve);
    }
    for (const key of ["trades", "layers", "picks"]) {
      if (input[key] !== void 0) this.assertSize(key, input[key], CAPS.detail);
    }
    const runId = kindConfig(kind).runPrefix + randomBytes(6).toString("hex");
    const run = {
      run_id: runId,
      version,
      ...input,
      created_at: _LibraryStore.now()
    };
    this.writeJson(this.runPath(kind, objectId, runId), run);
    return run;
  }
  deleteObject(kind, objectId) {
    const dir = this.dir(kind, objectId);
    if (!existsSync2(dir)) throw new LibraryError("not-found", `${kind}/${objectId} \u4E0D\u5B58\u5728`);
    rmSync2(dir, { recursive: true, force: true });
  }
};
function createSha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

// src/service.ts
import { chmodSync, mkdirSync as mkdirSync3, readFileSync as readFileSync2, renameSync as renameSync3, unlinkSync, writeFileSync as writeFileSync2 } from "node:fs";
import { join as join3 } from "node:path";
var SECRET_KEYS = ["TUSHARE_TOKEN", "IWENCAI_API_KEY"];
var ServiceError = class extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
    this.name = "ServiceError";
  }
};
function parseSecretKeySet(text) {
  const found = /* @__PURE__ */ new Set();
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (line === "" || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    if (SECRET_KEYS.includes(key)) found.add(key);
  }
  return found;
}
function loadSkillsCatalog(packageRoot2) {
  try {
    const parsed = JSON.parse(readFileSync2(join3(packageRoot2, "skills", "manifest.json"), "utf8"));
    return Array.isArray(parsed.skills) ? { skills: parsed.skills } : { skills: [] };
  } catch {
    return { skills: [] };
  }
}
var WorkbenchService = class {
  constructor(root) {
    this.root = root;
  }
  status() {
    const path = secretsPath();
    let keys = /* @__PURE__ */ new Set();
    let exists = false;
    try {
      const text = readFileSync2(path, "utf8");
      exists = true;
      keys = parseSecretKeySet(text);
    } catch {
    }
    let writable = false;
    try {
      mkdirSync3(stockHome(), { recursive: true });
      const probe = join3(stockHome(), ".write-probe");
      writeFileSync2(probe, "");
      unlinkSync(probe);
      writable = true;
    } catch {
      writable = false;
    }
    const keyMap = Object.fromEntries(SECRET_KEYS.map((key) => [key, keys.has(key)]));
    return {
      stockHome: stockHome(),
      secretsPath: path,
      secretsExists: exists,
      secretsWritable: writable,
      keys: keyMap,
      skillCount: loadSkillsCatalog(this.root).skills.length
    };
  }
  skills() {
    return loadSkillsCatalog(this.root);
  }
  /** 合并写入凭据：只更新 payload 里出现且非空的键；返回落盘的键名。 */
  saveSecrets(updates) {
    const path = secretsPath();
    const applied = [];
    for (const key of SECRET_KEYS) {
      const value = updates[key];
      if (typeof value !== "string" || value.trim() === "") continue;
      applied.push(key);
    }
    if (applied.length === 0) throw new ServiceError("empty", "\u6CA1\u6709\u9700\u8981\u4FDD\u5B58\u7684\u51ED\u636E\uFF08\u63D0\u4F9B TUSHARE_TOKEN / IWENCAI_API_KEY \u81F3\u5C11\u4E00\u9879\uFF09");
    let existing = "";
    try {
      existing = readFileSync2(path, "utf8");
    } catch {
      existing = "";
    }
    const lines = existing.length > 0 ? existing.replace(/\n+$/, "").split(/\r?\n/) : [];
    for (const key of applied) {
      const rendered = `${key}=${updates[key].trim()}`;
      const at = lines.findIndex((line) => {
        const trimmed = line.trim();
        return !trimmed.startsWith("#") && trimmed.startsWith(`${key}=`);
      });
      if (at >= 0) lines[at] = rendered;
      else lines.push(rendered);
    }
    mkdirSync3(stockHome(), { recursive: true });
    const tmp = `${path}.tmp-${process.pid}-${Date.now()}`;
    writeFileSync2(tmp, `${lines.join("\n")}
`, { mode: 384 });
    chmodSync(tmp, 384);
    renameSync3(tmp, path);
    try {
      chmodSync(path, 384);
    } catch {
    }
    return { saved: applied };
  }
};

// src/rpc.ts
var RPC_CHANNEL = "/dsh-skills-stock";
var MAX_TOKEN_CHARS = 200;
function ok(value) {
  return { ok: true, value };
}
function fail(code, message) {
  return { ok: false, error: { code, message, details: {} } };
}
function toErrorResult(error) {
  if (error instanceof ServiceError) return fail(error.code, error.message);
  return fail("internal", error instanceof Error ? error.message : String(error));
}
var RPC_BODY_LIMIT_BYTES = 256 * 1024;
function registerWorkbenchRpc(ctx, service, library) {
  return ctx.effect(() => {
    const registered = ctx.webServer.register({
      kind: "prefix",
      path: RPC_CHANNEL,
      handler: (req, res) => {
        void serveRpcRequest(ctx, service, library, req, res);
      }
    });
    return () => {
      if (typeof registered === "function") registered();
    };
  }, "dsh-skills-stock: rpc channel");
}
async function serveRpcRequest(ctx, service, library, req, res) {
  const reply = (status, payload) => {
    res.writeHead(status, { "content-type": "application/json", connection: "close" });
    res.end(JSON.stringify(payload));
  };
  const rejection = ctx.connection.requestRejection(req);
  if (rejection !== void 0) {
    res.writeHead(rejection);
    res.end(rejection === 401 ? "unauthorized" : "forbidden");
    return;
  }
  if (req.method !== "POST") {
    res.writeHead(405, { "content-type": "text/plain" });
    res.end("method not allowed");
    return;
  }
  const url = new URL(req.url ?? "/", "http://dsh.internal");
  const endpoint = url.pathname === RPC_CHANNEL ? "" : url.pathname.startsWith(`${RPC_CHANNEL}/`) ? url.pathname.slice(RPC_CHANNEL.length + 1) : void 0;
  if (endpoint === void 0 || !/^[A-Za-z0-9_$.:-]+$/.test(endpoint)) {
    reply(404, { type: "server-response", rpcId: "invalid-request", result: fail("not-found", "unknown endpoint") });
    return;
  }
  const contentType = String(req.headers["content-type"] ?? "").split(";")[0]?.trim().toLowerCase();
  if (contentType !== "application/json") {
    reply(415, { type: "server-response", rpcId: "invalid-request", result: fail("invalid", "content type must be application/json") });
    return;
  }
  const declared = req.headers["content-length"];
  if (declared !== void 0 && Number(declared) > RPC_BODY_LIMIT_BYTES) {
    res.writeHead(413, { connection: "close" });
    res.end();
    return;
  }
  let raw = "";
  const abort = new AbortController();
  res.on("close", () => {
    if (!res.writableEnded) abort.abort();
  });
  try {
    let received = 0;
    for await (const chunk of req) {
      received += chunk.byteLength;
      if (received > RPC_BODY_LIMIT_BYTES) throw new Error("body too large");
      raw += String(chunk);
    }
  } catch {
    res.writeHead(400, { connection: "close" });
    res.end("body read failure");
    req.destroy();
    return;
  }
  let envelope;
  try {
    envelope = JSON.parse(raw);
  } catch {
    reply(400, { type: "server-response", rpcId: "invalid-request", result: fail("invalid", "body is not JSON") });
    return;
  }
  if (envelope?.type !== "client-request" || typeof envelope.rpcId !== "string" || typeof envelope.method !== "string") {
    reply(200, {
      type: "server-response",
      rpcId: typeof envelope?.rpcId === "string" ? envelope.rpcId : "invalid-request",
      result: fail("invalid", "invalid client-request message")
    });
    return;
  }
  if (envelope.method !== endpoint) {
    reply(200, {
      type: "server-response",
      rpcId: envelope.rpcId,
      result: fail("invalid", `method ${JSON.stringify(envelope.method)} does not match endpoint ${JSON.stringify(endpoint)}`)
    });
    return;
  }
  const result = await handleWorkbenchRpc(service, library, envelope.method, envelope.payload, abort.signal);
  reply(200, { type: "server-response", rpcId: envelope.rpcId, result });
}
async function handleWorkbenchRpc(service, library, endpoint, payload, signal) {
  try {
    signal.throwIfAborted();
    if (endpoint === "status") {
      return ok(service.status());
    }
    if (endpoint === "skills") {
      return ok(service.skills());
    }
    if (endpoint === "library_list") {
      const kind = libraryKindOf(payload);
      return ok({ library: kind, items: library.listObjects(kind) });
    }
    if (endpoint === "library_detail") {
      const kind = libraryKindOf(payload);
      const body = payload;
      const objectId = typeof body["object_id"] === "string" ? body["object_id"] : "";
      if (!/^[a-z]+_[a-z0-9]+$/i.test(objectId)) return fail("invalid", "object_id \u5F62\u5982 stg_/fac_/sel_ + \u6807\u8BC6\u540E\u7F00");
      return ok(library.detail(kind, objectId));
    }
    if (endpoint === "library_runs") {
      const kind = libraryKindOf(payload);
      const body = payload;
      const objectId = typeof body["object_id"] === "string" ? body["object_id"] : "";
      if (!/^[a-z]+_[a-z0-9]+$/i.test(objectId)) return fail("invalid", "object_id \u5F62\u5982 stg_/fac_/sel_ + \u6807\u8BC6\u540E\u7F00");
      const rawIds = body["run_ids"];
      if (!Array.isArray(rawIds) || rawIds.length < 2 || rawIds.length > 4) {
        return fail("invalid", "run_ids \u5FC5\u987B\u662F 2-4 \u4E2A run_id \u7684\u6570\u7EC4\uFF08\u4E0E\u5DE5\u4F5C\u53F0\u5BF9\u6BD4\u52FE\u9009\u4E0A\u9650\u4E00\u81F4\uFF09");
      }
      const runIds = [];
      for (const id of rawIds) {
        if (typeof id !== "string" || !/^[a-z]+_[a-z0-9]+$/i.test(id)) {
          return fail("invalid", "run_id \u5F62\u5982 srun_/frun_/xrun_ + \u6807\u8BC6\u540E\u7F00");
        }
        if (!runIds.includes(id)) runIds.push(id);
      }
      return ok({ library: kind, object_id: objectId, runs: library.runsByIds(kind, objectId, runIds) });
    }
    if (endpoint === "save_secrets") {
      if (typeof payload !== "object" || payload === null) return fail("invalid", "payload must be an object");
      const body = payload;
      const updates = {};
      for (const key of SECRET_KEYS) {
        const value = body[key];
        if (value === void 0 || value === null) continue;
        if (typeof value !== "string") return fail("invalid", `${key} must be a string`);
        if (value.trim() !== value) return fail("invalid", `${key} must not have surrounding whitespace`);
        if (value.length > MAX_TOKEN_CHARS) return fail("invalid", `${key} exceeds ${MAX_TOKEN_CHARS} chars`);
        if (/[\r\n#]/.test(value)) return fail("invalid", `${key} contains forbidden characters`);
        if (value.trim() === "") return fail("invalid", `${key} must not be empty\uFF08\u7559\u7A7A\u8868\u793A\u4FDD\u6301\u4E0D\u53D8\uFF0C\u8BF7\u76F4\u63A5\u7701\u7565\u8BE5\u5B57\u6BB5\uFF09`);
        updates[key] = value;
      }
      return ok(service.saveSecrets(updates));
    }
    return fail("not-found", `unknown endpoint ${JSON.stringify(endpoint)}`);
  } catch (error) {
    if (error instanceof LibraryError) return fail(error.code, error.message);
    return toErrorResult(error);
  }
}
function libraryKindOf(payload) {
  const body = typeof payload === "object" && payload !== null ? payload : {};
  const kind = body["kind"];
  if (!isLibraryKind(kind)) throw new LibraryError("invalid", "kind \u5FC5\u987B\u662F strategies / factors / selections \u4E4B\u4E00");
  return kind;
}

// src/tools.ts
var ToolRejection = class extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
    this.name = "ToolRejection";
  }
};
function callerFrom(exec) {
  const agent = exec.agent;
  return {
    sessionId: typeof agent?.session?.id === "string" ? agent.session.id : void 0,
    cwd: typeof agent?.session?.header?.cwd === "string" ? agent.session.header.cwd : void 0
  };
}
var jsonRender = (_args, value) => [
  typeof value === "string" ? value : JSON.stringify(value, null, 2)
];
function toolEnvelope(error) {
  if (error instanceof LibraryError) return { ok: false, error: { code: error.code, message: error.message } };
  return { ok: false, error: { code: "internal", message: error instanceof Error ? error.message : String(error) } };
}
function record(value, label) {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ToolRejection("invalid", `${label} \u5FC5\u987B\u662F\u5BF9\u8C61`);
  }
  return value;
}
function string(value, label) {
  if (typeof value !== "string") throw new ToolRejection("invalid", `${label} \u5FC5\u987B\u662F\u5B57\u7B26\u4E32`);
  return value;
}
function boundedLine(summary) {
  return Object.fromEntries(Object.entries(summary).map(([k, v]) => [k, typeof v === "string" && v.length > 200 ? v.slice(0, 200) + "\u2026" : v]));
}
function libraryToolSet(kind, store) {
  const zh = kind === "strategies" ? { noun: "\u7B56\u7565", record: "strategy_record_backtest", recordLabel: "\u56DE\u6D4B", runPayload: ["data_start", "data_end", "rules", "metrics", "equity?", "trades?"] } : kind === "factors" ? { noun: "\u56E0\u5B50", record: "factor_record_run", recordLabel: "\u68C0\u9A8C", runPayload: ["universe", "data_start", "data_end", "config", "metrics", "ic_series?", "layers?"] } : { noun: "\u9009\u80A1", record: "selection_record_run", recordLabel: "\u6267\u884C", runPayload: ["trade_date", "universe", "rules", "metrics", "report?", "picks?"] };
  const idKey = kind === "strategies" ? "strategy_id" : kind === "factors" ? "factor_id" : "selection_id";
  return [
    {
      name: `${kind === "strategies" ? "strategy" : kind === "factors" ? "factor" : "selection"}_list`,
      description: `\u5217\u51FA${zh.noun}\u5E93\u5168\u90E8${zh.noun}\uFF08id/\u540D\u79F0/\u72B6\u6001/\u5F53\u524D\u7248\u672C/\u6700\u8FD1${zh.recordLabel}\u6838\u5FC3\u6307\u6807\uFF09\u3002\u7528\u6237\u8BF4\u300C\u7EE7\u7EED/\u6539\u8FDB/\u5BF9\u6BD4\u4E4B\u524D\u7684${zh.noun}\u300D\u65F6\uFF0C\u4ECE\u8FD9\u91CC\u5B9A\u4F4D\u8D77\u70B9\u3002`,
      parameters: { type: "object", properties: {} },
      output: { schema: { type: "object" }, render: jsonRender },
      timeoutMs: 15e3,
      execute: async () => {
        try {
          const views = store.listObjects(kind).map((view) => boundedLine(view));
          return { ok: true, value: { library: kind, count: views.length, items: views } };
        } catch (error) {
          return toolEnvelope(error);
        }
      }
    },
    {
      name: `${kind === "strategies" ? "strategy" : kind === "factors" ? "factor" : "selection"}_create`,
      description: kind === "selections" ? `\u521B\u5EFA\u9009\u80A1\u65B9\u6848\uFF08{name, criteria, params?}\uFF09\uFF1Acriteria \u662F\u4E00\u53E5\u8BDD\u9009\u80A1\u53E3\u5F84\uFF0C\u521B\u5EFA\u5373\u843D v1\u300C\u521D\u59CB\u9009\u80A1\u8981\u6C42\u300D\u3002\u540E\u7EED\u6267\u884C\u7ED3\u679C\u7528 selection_record_run \u5F52\u6863\u3002` : `\u521B\u5EFA${zh.noun}\uFF08{name, hypothesis${kind === "factors" ? ", category" : ""}}\uFF09\uFF1Ahypothesis \u5199\u6E05\u7ECF\u6D4E\u5B66/\u6295\u8D44\u5047\u8BBE\u3002\u8FD4\u56DE ${idKey}\uFF0C\u540E\u7EED\u7528 get_latest / save_version \u8FED\u4EE3\u3002`,
      parameters: {
        type: "object",
        properties: {
          name: { type: "string", description: "\u540D\u79F0\uFF08\u2264120 \u5B57\uFF09" },
          hypothesis: { type: "string", description: "\u6295\u8D44/\u7ECF\u6D4E\u5B66\u5047\u8BBE\uFF08\u7B56\u7565\u4E0E\u56E0\u5B50\uFF09" },
          category: { type: "string", enum: ["value", "momentum", "quality", "low_vol", "size", "growth", "custom"], description: "\u56E0\u5B50\u7C7B\u522B\uFF08\u4EC5\u56E0\u5B50\u5E93\uFF09" },
          criteria: { type: "string", description: "\u4E00\u53E5\u8BDD\u9009\u80A1\u53E3\u5F84\uFF08\u4EC5\u9009\u80A1\u5E93\uFF09" },
          params: { type: "object", description: "\u521D\u59CB\u53C2\u6570\uFF08\u53EF\u9009\uFF09" }
        }
      },
      output: { schema: { type: "object" }, render: jsonRender },
      timeoutMs: 15e3,
      execute: async (args) => {
        try {
          const body = record(args, "args");
          const created = store.createObject(kind, {
            name: string(body["name"], "name"),
            hypothesis: typeof body["hypothesis"] === "string" ? body["hypothesis"] : void 0,
            category: typeof body["category"] === "string" ? body["category"] : void 0,
            criteria: typeof body["criteria"] === "string" ? body["criteria"] : void 0,
            criteria_json: body["criteria_json"] === void 0 ? void 0 : record(body["criteria_json"], "criteria_json"),
            params: body["params"]
          });
          return { ok: true, value: created };
        } catch (error) {
          return toolEnvelope(error);
        }
      }
    },
    {
      name: `${kind === "strategies" ? "strategy" : kind === "factors" ? "factor" : "selection"}_get_latest`,
      description: `\u8BFB\u53D6${zh.noun}\u5F53\u524D\u7248\u672C\u7684\u5B8C\u6574\u5FEB\u7167\uFF08${kind === "selections" ? "criteria_json \u7ED3\u6784\u5316\u53E3\u5F84" : "\u4EE3\u7801 code"} + params + change_note\uFF09\u3002\u8FED\u4EE3/\u590D\u7528\u7684\u8D77\u70B9\uFF1B\u5E93\u5185\u65E0\u7248\u672C\u65F6\u5148 save_version \u843D v1\u3002`,
      parameters: {
        type: "object",
        properties: { [idKey]: { type: "string", description: `${zh.noun} id\uFF08${idKey} \u524D\u7F00\uFF09` } },
        required: [idKey]
      },
      output: { schema: { type: "object" }, render: jsonRender },
      timeoutMs: 15e3,
      execute: async (args) => {
        try {
          const body = record(args, "args");
          const objectId = string(body[idKey], idKey);
          const detail = store.detail(kind, objectId);
          const versions = detail["versions"] ?? [];
          const latest = versions.length > 0 ? versions[versions.length - 1] : void 0;
          if (latest === void 0) {
            throw new ToolRejection("empty", `${objectId} \u5C1A\u65E0\u7248\u672C\uFF1A\u5148 save_version \u843D v1\uFF08${kind === "selections" ? "criteria_json.summary \u5FC5\u586B" : "\u5B8C\u6574\u4EE3\u7801 + params + change_note"}\uFF09`);
          }
          return { ok: true, value: { object: boundedLine(detail), latest_version: latest } };
        } catch (error) {
          return toolEnvelope(error);
        }
      }
    },
    {
      name: `${kind === "strategies" ? "strategy" : kind === "factors" ? "factor" : "selection"}_save_version`,
      description: kind === "selections" ? `\u4FDD\u5B58\u9009\u80A1\u65B9\u6848\u65B0\u7248\u672C\uFF08{${idKey}, criteria_json, change_note, parent_version}\uFF09\uFF1Acriteria_json.summary \u5FC5\u586B\uFF1Bparent_version \u5FC5\u987B\u7B49\u4E8E\u5F53\u524D\u7248\u672C\uFF08\u4E50\u89C2\u9501\uFF09\u3002\u4E34\u65F6\u65B0\u53E3\u5F84\u5148\u5B58\u7248\u672C\u518D\u6267\u884C\u3002` : `\u4FDD\u5B58${zh.noun}\u65B0\u7248\u672C\uFF08{${idKey}, code, params, change_note, parent_version}\uFF09\uFF1Acode \u662F\u5B8C\u6574\u53EF\u6267\u884C\u5FEB\u7167\u2014\u2014${zh.noun}\u4EE3\u7801\u5FC5\u987B\u5165\u5E93\uFF0C\u7981\u6B62\u53EA\u7559\u5728\u4F1A\u8BDD\u5DE5\u4F5C\u533A\uFF1Bparent_version \u5FC5\u987B\u7B49\u4E8E\u5F53\u524D\u7248\u672C\uFF08\u4E50\u89C2\u9501\uFF09\uFF0Cconflict \u65F6\u5148 get_latest\u3002`,
      parameters: {
        type: "object",
        properties: {
          [idKey]: { type: "string", description: `${zh.noun} id` },
          code: { type: "string", description: "\u5B8C\u6574\u4EE3\u7801\u5FEB\u7167\uFF08\u7B56\u7565/\u56E0\u5B50\uFF09" },
          criteria_json: { type: "object", description: "\u7ED3\u6784\u5316\u9009\u80A1\u8981\u6C42\uFF08\u9009\u80A1\u5E93\uFF0Csummary \u5FC5\u586B\uFF09" },
          params: { type: "object", description: "\u53C2\u6570\u5B57\u5178" },
          change_note: { type: "string", description: "\u672C\u7248\u672C\u6539\u52A8\u4E0E\u539F\u56E0\uFF08\u8BC1\u4F2A\u4E5F\u8981\u5982\u5B9E\u5199\uFF09" },
          parent_version: { type: "number", description: "\u57FA\u4E8E\u7684\u5F53\u524D\u7248\u672C\u53F7\uFF08\u4E50\u89C2\u9501\uFF09" }
        },
        required: [idKey, "change_note", "parent_version"]
      },
      output: { schema: { type: "object" }, render: jsonRender },
      timeoutMs: 15e3,
      execute: async (args) => {
        try {
          const body = record(args, "args");
          const objectId = string(body[idKey], idKey);
          const saved = store.saveVersion(kind, objectId, body);
          return { ok: true, value: { [idKey]: objectId, version: saved["version"], change_note: saved["change_note"] } };
        } catch (error) {
          return toolEnvelope(error);
        }
      }
    },
    {
      name: zh.record,
      description: `${zh.noun}${zh.recordLabel}\u540E\u767B\u8BB0\u8FD0\u884C\u5F52\u6863\uFF08{${idKey}, version, ${zh.runPayload.join(", ")}, thread_id?}\uFF09\uFF1A${kind === "strategies" ? "rules \u5FC5\u987B\u539F\u6837\u6284\u5F55\u56DE\u6D4B\u7684 A \u80A1\u4EA4\u6613\u89C4\u5219\u56DE\u663E" : kind === "factors" ? "config \u539F\u6837\u6284\u5F55\u68C0\u9A8C\u914D\u7F6E" : "picks=[{code,name,score,strategies,rank}]\uFF0Creport \u4E3A\u5B8C\u6574 markdown \u62A5\u544A"}\uFF1B\u767B\u8BB0\u540E\u53EF\u5728\u6295\u7814\u5DE5\u4F5C\u53F0\u5BF9\u5E94\u5E93\u67E5\u770B\u4E0E\u8DE8${kind === "selections" ? "\u57FA\u51C6\u65E5" : "\u7248\u672C"}\u5BF9\u6BD4\u3002`,
      parameters: {
        type: "object",
        properties: {
          [idKey]: { type: "string", description: `${zh.noun} id` },
          version: { type: "number", description: "\u672C\u6B21\u8FD0\u884C\u57FA\u4E8E\u7684\u7248\u672C\u53F7" },
          data_start: { type: "string", description: "\u6570\u636E\u533A\u95F4\u8D77\uFF08YYYYMMDD\uFF09" },
          data_end: { type: "string", description: "\u6570\u636E\u533A\u95F4\u6B62\uFF08YYYYMMDD\uFF09" },
          trade_date: { type: "string", description: "\u57FA\u51C6\u65E5\uFF08\u9009\u80A1\u5E93\uFF0CYYYYMMDD\uFF09" },
          universe: { type: "string", description: "\u80A1\u7968\u6C60\u8BF4\u660E\uFF08\u56E0\u5B50/\u9009\u80A1\uFF09" },
          rules: { type: "object", description: "\u4EA4\u6613/\u6267\u884C\u89C4\u5219\uFF08\u539F\u6837\u6284\u5F55\uFF09" },
          config: { type: "object", description: "\u68C0\u9A8C\u914D\u7F6E\uFF08\u56E0\u5B50\uFF0C\u539F\u6837\u6284\u5F55\uFF09" },
          metrics: { type: "object", description: "\u6838\u5FC3\u6307\u6807\u5B57\u5178" },
          equity: { type: "object", description: "\u51C0\u503C\u66F2\u7EBF\uFF08\u7B56\u7565\uFF0C\u53EF\u9009\uFF0C\u22642MB\uFF09" },
          trades: { type: "object", description: "\u6210\u4EA4\u660E\u7EC6\uFF08\u53EF\u9009\uFF0C\u22644MB\uFF09" },
          ic_series: { type: "object", description: "IC \u5E8F\u5217\uFF08\u56E0\u5B50\uFF0C\u53EF\u9009\uFF09" },
          layers: { type: "object", description: "\u5206\u5C42\u56DE\u6D4B\u7ED3\u679C\uFF08\u56E0\u5B50\uFF0C\u53EF\u9009\uFF09" },
          report: { type: "string", description: "\u5B8C\u6574 markdown \u62A5\u544A\uFF08\u9009\u80A1\uFF0C\u53EF\u9009\uFF09" },
          picks: { type: "object", description: "\u547D\u4E2D\u6E05\u5355\uFF08\u9009\u80A1\uFF0C\u53EF\u9009\uFF09" },
          thread_id: { type: "string", description: "\u6765\u6E90\u4F1A\u8BDD id\uFF08\u53EF\u9009\uFF09" }
        },
        required: [idKey, "version", "metrics"]
      },
      output: { schema: { type: "object" }, render: jsonRender },
      timeoutMs: 3e4,
      execute: async (args, exec) => {
        try {
          const body = record(args, "args");
          const objectId = string(body[idKey], idKey);
          const caller = callerFrom(exec);
          const run = store.recordRun(kind, objectId, {
            ...body,
            ...caller.sessionId !== void 0 && body["thread_id"] === void 0 ? { thread_id: caller.sessionId } : {}
          });
          return { ok: true, value: { [idKey]: objectId, run_id: run["run_id"], version: run["version"], created_at: run["created_at"] } };
        } catch (error) {
          return toolEnvelope(error);
        }
      }
    }
  ];
}
function libraryToolDefs(store) {
  return ["strategies", "factors", "selections"].flatMap((kind) => libraryToolSet(kind, store));
}

// src/index.ts
var name = "dsh-skills-stock";
var inject = ["skills", "systemPrompt", "webServer", "connection", "tools"];
var packageRoot = dirname(fileURLToPath(new URL(".", import.meta.url)));
function stripFrontmatter(raw) {
  if (!raw.startsWith("---\n")) return raw;
  const end = raw.indexOf("\n---\n", 4);
  if (end === -1) return raw;
  return raw.slice(end + 5).replace(/^\n+/, "");
}
function cleanupLegacyPresets() {
  for (const dir of legacyPresetDirs()) {
    try {
      rmSync3(dir, { recursive: true, force: true });
    } catch {
    }
  }
}
function registerSkills(skills, root) {
  const manifest = JSON.parse(readFileSync3(join4(root, "skills", "manifest.json"), "utf8"));
  const disposers = [];
  for (const item of manifest.skills) {
    const dir = join4(root, "skills", item.dir);
    const content = stripFrontmatter(readFileSync3(join4(dir, "SKILL.md"), "utf8"));
    disposers.push(skills.register({
      name: item.name,
      description: item.description,
      ...item.whenToUse === void 0 ? {} : { whenToUse: item.whenToUse },
      source: "runtime",
      content,
      // 正文引用的相对资源（scripts/、references/、assets/）按此基目录解析
      resourceBase: { kind: "directory", path: dir },
      // 自由元数据：凭据需求随注册透传（宿主不消费，便于诊断与下游集成）
      ...item.requiredSecrets?.length ? { metadata: { requiredSecrets: [...item.requiredSecrets] } } : {}
    }));
  }
  console.log(`dsh-skills-stock: ${disposers.length} runtime skills registered (${manifest.skills.map((s) => s.name).join(", ")})`);
  return () => {
    for (const dispose of disposers) {
      try {
        dispose();
      } catch {
      }
    }
  };
}
function apply(ctx, config = {}) {
  if (config.enabled === false) return () => {
  };
  migrateLegacyStockHome();
  cleanupLegacyPresets();
  const disposers = [];
  disposers.push(registerSkills(ctx.skills, packageRoot));
  if (config.announceToAgent !== false) {
    disposers.push(ctx.systemPrompt.section({
      name: `plugin:${name}`,
      order: SECTION_ORDER,
      text: KSTOCK_GUIDANCE
    }));
  }
  const library = new LibraryStore();
  if (config.registerTools !== false && ctx.tools !== void 0) {
    for (const def of libraryToolDefs(library)) {
      disposers.push(ctx.tools.register(def));
    }
  }
  disposers.push(registerWorkbenchRpc(ctx, new WorkbenchService(packageRoot), library));
  return () => {
    for (const dispose of disposers) {
      try {
        dispose();
      } catch {
      }
    }
  };
}
export {
  KSTOCK_GUIDANCE,
  LibraryError,
  LibraryStore,
  RPC_CHANNEL,
  SECRET_KEYS,
  SECTION_ORDER,
  ToolRejection,
  WorkbenchService,
  apply,
  cleanupLegacyPresets,
  handleWorkbenchRpc,
  inject,
  libraryToolDefs,
  migrateLegacyStockHome,
  name,
  packageRoot,
  registerSkills,
  secretsPath,
  stockHome,
  stripFrontmatter
};
