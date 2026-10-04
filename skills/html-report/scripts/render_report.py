#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_report.py — 把报告 JSON 渲染为自包含 HTML 看板（2.0 重写版）。

设计原则（对照 1.x render_html_report 的教训）：
- 单文件交付：CSS/图表全部内联，零外部资源、零 JS 依赖，邮件/离线/归档皆可打开；
- 图表由本脚本直接绘制内联 SVG（line/area/bar/pie/radar/scatter），
  不再依赖外部图表工具的 URL 契约——数据即图，杜绝两层契约漂移；
- 单主题输出：KStock 深色基调，不再生成 dark/light 双文件；
- 安全默认：所有插值经 HTML 转义，外链仅放行 http(s)，无任何脚本注入面。

用法：
    python render_report.py report.json -o report.html

报告 JSON 契约见 references/report-schema.md；字段容错从宽——缺省字段
优雅降级为隐藏，非法图表配置跳过该图并在页面顶部给出告警条。
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

# 外链仅放行 http(s)：转义拦不住 scheme 型 href（javascript:/data:）。
_SAFE_HREF_RE = re.compile(r"^https?://", re.IGNORECASE)

# KStock 品牌色板（与引擎客户端插件 token 同源）
C_BG = "#030d0b"
C_PANEL = "#101b18"
C_PANEL_2 = "#0c1412"
C_BORDER = "#1d2b27"
C_TEXT = "#d7e2de"
C_MUTED = "#7d8f89"
C_ACCENT = "#31c7a2"
C_UP = "#2fc197"
C_DOWN = "#e0564f"
C_WARN = "#e8a33d"
C_BLUE = "#5ab0ff"
C_PURPLE = "#c792ea"
PALETTE = [C_ACCENT, C_BLUE, C_WARN, C_PURPLE, C_UP, "#8ee6c8", "#f2a65a", "#7f9ff8"]


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def num(value: Any) -> str:
    """数字排版：千分位 + 去尾零；非数字原样返回。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return esc(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return "—"
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer() and abs(value) < 1e15):
        return f"{int(value):,}"
    return f"{value:,.4f}".rstrip("0").rstrip(".")


def warn_list() -> list[str]:
    return WARNINGS


def warn(message: str) -> None:
    WARNINGS.append(message)


WARNINGS: list[str] = []


# ── 图表绘制（内联 SVG）─────────────────────────────────────────────

def _nice_ticks(lo: float, hi: float, count: int = 4) -> list[float]:
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    span = hi - lo
    step = span / count
    mag = 10 ** math.floor(math.log10(step)) if step > 0 else 1
    for mult in (1, 2, 2.5, 5, 10):
        candidate = mult * mag
        if candidate >= step:
            step = candidate
            break
    first = math.ceil(lo / step) * step
    ticks = []
    value = first
    while value <= hi + 1e-9:
        ticks.append(round(value, 10))
        value += step
    return ticks


def _fmt_tick(value: float) -> str:
    if abs(value) >= 1e8:
        return f"{value / 1e8:.1f}亿"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.1f}万"
    return num(value)


def _legend(entries: list[tuple[str, str]]) -> str:
    if len(entries) <= 1:
        return ""
    items = "".join(
        f'<span class="lg"><i style="background:{color}"></i>{esc(name)}</span>'
        for name, color in entries
    )
    return f'<div class="legend">{items}</div>'


def _svg_open(w: int, h: int, title: str) -> str:
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}" '
            f'font-family="inherit" preserveAspectRatio="xMidYMid meet">')


def draw_xy(kind: str, title: str, chart: dict[str, Any]) -> str:
    """line / area / bar / scatter 共用的直角坐标系绘制。"""
    w, h, pad = 640, 300, 46
    x_labels = [str(label) for label in chart.get("x") or []]
    series = [s for s in chart.get("series") or [] if isinstance(s, dict)]
    series = [s for s in series if isinstance(s.get("values"), list)]
    if not x_labels or not series:
        warn(f"图表「{title}」缺少 x 轴或 series，已跳过")
        return ""
    counts = {len(s["values"]) for s in series}
    if len(counts) != 1:
        # 容许长度不齐：按最长对齐，短序列尾部留空
        pass
    max_len = max(counts)

    plotted: list[list[float | None]] = []
    for s in series:
        row: list[float | None] = []
        for v in s["values"][:max_len]:
            row.append(float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None)
        plotted.append(row)
    flat = [v for row in plotted for v in row if v is not None]
    if not flat:
        warn(f"图表「{title}」无有效数值，已跳过")
        return ""

    lo, hi = min(flat), max(flat)
    if chart.get("baseline") is not None and isinstance(chart["baseline"], (int, float)):
        lo, hi = min(lo, float(chart["baseline"])), max(hi, float(chart["baseline"]))
    pad_y = (hi - lo) * 0.08 or abs(hi) * 0.1 or 1
    lo, hi = lo - pad_y, hi + pad_y
    ticks = _nice_ticks(lo, hi)

    inner_w, inner_h = w - pad - 16, h - pad - 20
    def px(i: int) -> float:
        return pad + (i / max(1, max_len - 1)) * inner_w
    def py(v: float) -> float:
        return 20 + (1 - (v - ticks[0]) / (ticks[-1] - ticks[0] or 1)) * inner_h

    parts = [_svg_open(w, h, title)]
    for t in ticks:
        y = py(t)
        parts.append(f'<line x1="{pad}" y1="{y:.1f}" x2="{w - 16}" y2="{y:.1f}" stroke="{C_BORDER}" stroke-width="1"/>')
        parts.append(f'<text x="{pad - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="{C_MUTED}">{esc(_fmt_tick(t))}</text>')
    step = max(1, math.ceil(max_len / 12))
    for i in range(0, max_len, step):
        x = px(i) if max_len > 1 else pad
        parts.append(f'<text x="{x:.1f}" y="{h - 8}" text-anchor="middle" font-size="11" fill="{C_MUTED}">{esc(x_labels[i][:12])}</text>')

    def color(idx: int) -> str:
        return PALETTE[idx % len(PALETTE)]

    if kind == "bar":
        group_w = inner_w / max(1, max_len)
        bar_w = group_w * 0.72 / len(plotted)
        for si, row in enumerate(plotted):
            for i, v in enumerate(row):
                if v is None:
                    continue
                x = pad + i * group_w + group_w * 0.14 + si * bar_w
                y0, y1 = py(v), py(max(ticks[0], 0) if ticks[0] < 0 < ticks[-1] else ticks[0])
                top, bottom = min(y0, y1), max(y0, y1)
                parts.append(
                    f'<rect x="{x:.1f}" y="{top:.1f}" width="{bar_w * 0.86:.1f}" height="{max(1, bottom - top):.1f}" '
                    f'rx="2" fill="{color(si)}" opacity="0.92"><title>{esc(x_labels[i])} · {esc(str(series[si].get("name", "")))}: {num(v)}</title></rect>'
                )
    elif kind == "scatter":
        for si, row in enumerate(plotted):
            for i, v in enumerate(row):
                if v is None:
                    continue
                parts.append(
                    f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="4" fill="{color(si)}" opacity="0.85">'
                    f'<title>{esc(x_labels[i])} · {esc(str(series[si].get("name", "")))}: {num(v)}</title></circle>'
                )
    else:  # line / area
        for si, row in enumerate(plotted):
            pts = [(px(i), py(v)) for i, v in enumerate(row) if v is not None]
            if len(pts) < 2:
                if pts:
                    parts.append(f'<circle cx="{pts[0][0]:.1f}" cy="{pts[0][1]:.1f}" r="3.5" fill="{color(si)}"/>')
                continue
            polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            if kind == "area":
                area = polyline + f" {pts[-1][0]:.1f},{py(ticks[0]):.1f} {pts[0][0]:.1f},{py(ticks[0]):.1f}"
                parts.append(f'<polygon points="{area}" fill="{color(si)}" opacity="0.14"/>')
            parts.append(
                f'<polyline points="{polyline}" fill="none" stroke="{color(si)}" stroke-width="2.2" '
                f'stroke-linejoin="round" stroke-linecap="round"/>'
            )
            for x, y in pts:
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{color(si)}"/>')
        if chart.get("baseline") is not None and isinstance(chart["baseline"], (int, float)):
            by = py(float(chart["baseline"]))
            parts.append(f'<line x1="{pad}" y1="{by:.1f}" x2="{w - 16}" y2="{by:.1f}" stroke="{C_MUTED}" stroke-dasharray="4,4" stroke-width="1"/>')

    parts.append("</svg>")
    legend = _legend([(str(s.get("name", f"系列{i + 1}")), color(i)) for i, s in enumerate(series)])
    y_label = f'<span class="axis-label">{esc(str(chart.get("yLabel", "")))}</span>' if chart.get("yLabel") else ""
    return f'{legend}{y_label}{"".join(parts)}'


def draw_pie(title: str, chart: dict[str, Any]) -> str:
    data = [d for d in chart.get("data") or [] if isinstance(d, dict)]
    data = [d for d in data if isinstance(d.get("value"), (int, float)) and not isinstance(d["value"], bool)]
    if not data:
        warn(f"图表「{title}」缺少可绘数据，已跳过")
        return ""
    total = sum(float(d["value"]) for d in data) or 1.0
    w, h, cx, cy, r, inner = 640, 300, 200, 150, 108, 58
    parts = [_svg_open(w, h, title)]
    angle = -math.pi / 2
    for i, d in enumerate(data):
        sweep = float(d["value"]) / total * 2 * math.pi
        x0, y0 = cx + r * math.cos(angle), cy + r * math.sin(angle)
        x1, y1 = cx + r * math.cos(angle + sweep), cy + r * math.sin(angle + sweep)
        xi, yi = cx + inner * math.cos(angle + sweep), cy + inner * math.sin(angle + sweep)
        xo, yo = cx + inner * math.cos(angle), cy + inner * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        color = PALETTE[i % len(PALETTE)]
        if sweep >= 2 * math.pi - 1e-9:
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{(r + inner) / 2:.1f}" fill="none" stroke="{color}" stroke-width="{r - inner}"/>')
        else:
            parts.append(
                f'<path d="M{x0:.1f},{y0:.1f} A{r},{r} 0 {large} 1 {x1:.1f},{y1:.1f} '
                f'L{xi:.1f},{yi:.1f} A{inner},{inner} 0 {large} 0 {xo:.1f},{yo:.1f} Z" '
                f'fill="{color}" opacity="0.92"><title>{esc(d.get("name", ""))}: {num(d["value"])}'
                f'（{float(d["value"]) / total * 100:.1f}%）</title></path>'
            )
        label_x = cx + (r + 26) * math.cos(angle + sweep / 2)
        label_y = cy + (r + 26) * math.sin(angle + sweep / 2)
        parts.append(
            f'<text x="{label_x:.1f}" y="{label_y + 4:.1f}" text-anchor="middle" font-size="11.5" fill="{C_TEXT}">'
            f'{esc(str(d.get("name", "")))} {float(d["value"]) / total * 100:.0f}%</text>'
        )
        angle += sweep
    parts.append("</svg>")
    entries = [(f'{d.get("name", "")} {num(d["value"])}', PALETTE[i % len(PALETTE)]) for i, d in enumerate(data)]
    return _legend(entries) + "".join(parts)


def draw_radar(title: str, chart: dict[str, Any]) -> str:
    indicators = [str(i.get("name", "") if isinstance(i, dict) else i) for i in chart.get("indicators") or []]
    series = [s for s in chart.get("series") or [] if isinstance(s, dict) and isinstance(s.get("values"), list)]
    if len(indicators) < 3 or not series:
        warn(f"图表「{title}」至少需要 3 个维度与一组 series，已跳过")
        return ""
    w, h, cx, cy, radius = 640, 320, 320, 165, 118
    n = len(indicators)
    all_values = [float(v) for s in series for v in s["values"][:n]
                  if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not all_values:
        warn(f"图表「{title}」无数值，已跳过")
        return ""
    lo, hi = min(all_values), max(all_values)
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    parts = [_svg_open(w, h, title)]
    for ring in (1.0, 0.75, 0.5, 0.25):
        pts = []
        for i in range(n):
            a = -math.pi / 2 + i * 2 * math.pi / n
            pts.append(f"{cx + radius * ring * math.cos(a):.1f},{cy + radius * ring * math.sin(a):.1f}")
        parts.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="{C_BORDER}"/>')
    for i, name in enumerate(indicators):
        a = -math.pi / 2 + i * 2 * math.pi / n
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{cx + radius * math.cos(a):.1f}" y2="{cy + radius * math.sin(a):.1f}" stroke="{C_BORDER}"/>')
        lx, ly = cx + (radius + 18) * math.cos(a), cy + (radius + 18) * math.sin(a)
        anchor = "middle" if abs(math.cos(a)) < 0.3 else ("start" if math.cos(a) > 0 else "end")
        parts.append(f'<text x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}" font-size="12" fill="{C_TEXT}">{esc(name[:10])}</text>')
    for si, s in enumerate(series):
        color = PALETTE[si % len(PALETTE)]
        pts = []
        for i in range(n):
            raw = s["values"][i] if i < len(s["values"]) else lo
            v = float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else lo
            a = -math.pi / 2 + i * 2 * math.pi / n
            scaled = (v - lo) / (hi - lo)
            pts.append((cx + radius * scaled * math.cos(a), cy + radius * scaled * math.sin(a), v))
        polygon = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)
        parts.append(f'<polygon points="{polygon}" fill="{color}" opacity="0.16" stroke="{color}" stroke-width="2"/>')
        for x, y, v in pts:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"><title>{num(v)}</title></circle>')
    parts.append("</svg>")
    return _legend([(str(s.get("name", f"系列{i + 1}")), PALETTE[i % len(PALETTE)]) for i, s in enumerate(series)]) + "".join(parts)


CHART_KINDS = {"line", "area", "bar", "scatter", "pie", "radar"}


def draw_chart(chart: dict[str, Any]) -> str:
    kind = str(chart.get("type", "line")).lower()
    title = str(chart.get("title", ""))
    if kind not in CHART_KINDS:
        warn(f"图表「{title}」类型 {kind!r} 不支持（支持 {'/'.join(sorted(CHART_KINDS))}），已跳过")
        return ""
    if kind == "pie":
        body = draw_pie(title, chart)
    elif kind == "radar":
        body = draw_radar(title, chart)
    else:
        body = draw_xy(kind, title, chart)
    if not body:
        return ""
    return f'<figure class="chart"><figcaption>{esc(title)}</figcaption>{body}</figure>'


# ── 区块与页面 ──────────────────────────────────────────────────────

INLINE_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def inline_text(text: str) -> str:
    """有限的行内标记：**粗体** 与 `代码`；其余字符经转义。"""
    result_parts: list[str] = []
    position = 0
    pattern = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`")
    for match in pattern.finditer(str(text)):
        result_parts.append(esc(str(text)[position:match.start()]))
        if match.group(1) is not None:
            result_parts.append(f"<strong>{esc(match.group(1))}</strong>")
        else:
            result_parts.append(f"<code>{esc(match.group(2))}</code>")
        position = match.end()
    result_parts.append(esc(str(text)[position:]))
    return "".join(result_parts)


def draw_table(block: dict[str, Any]) -> str:
    columns = [str(c) for c in block.get("columns") or []]
    rows = [r for r in block.get("rows") or [] if isinstance(r, list)]
    if not columns or not rows:
        warn("表格缺少 columns 或 rows，已跳过")
        return ""
    head = "".join(f"<th>{esc(c)}</th>" for c in columns)
    body_rows = []
    for row in rows[:200]:
        cells = "".join(f"<td>{inline_text(cell)}</td>" for cell in row[:len(columns)])
        body_rows.append(f"<tr>{cells}</tr>")
    note = f'<p class="tbl-note">仅展示前 {len(rows[:200])} 行（共 {len(rows)} 行）</p>' if len(rows) > 200 else ""
    return f'<div class="tbl-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>{note}'


def draw_block(block: dict[str, Any]) -> str:
    kind = str(block.get("type", "text"))
    if kind == "text":
        body = str(block.get("body", "")).strip()
        if not body:
            return ""
        paragraphs = "".join(f"<p>{inline_text(p)}</p>" for p in body.split("\n") if p.strip())
        return f'<div class="prose">{paragraphs}</div>'
    if kind == "list":
        items = "".join(f"<li>{inline_text(item)}</li>" for item in block.get("items") or [])
        return f'<ul class="dot-list">{items}</ul>' if items else ""
    if kind == "table":
        return draw_table(block)
    if kind == "chart":
        chart = block.get("chart")
        return draw_chart(chart) if isinstance(chart, dict) else ""
    if kind == "callout":
        tone = str(block.get("tone", "info"))
        return f'<div class="callout tone-{esc(tone)}">{inline_text(block.get("body", ""))}</div>'
    warn(f"未知区块类型 {kind!r}，已跳过")
    return ""


def _tone_class(value: Any) -> str:
    tone = str(value or "").lower()
    return f" tone-{esc(tone)}" if tone in {"up", "down", "warn", "neutral"} else ""


def build_html(payload: dict[str, Any]) -> str:
    title = str(payload.get("title") or "KStock 研究报告")
    generated_at = str(payload.get("generated_at") or "")
    symbol = str(payload.get("symbol") or "")
    risk_level = str(payload.get("risk_level") or "")
    report_type = str(payload.get("report_type") or "")

    meta_bits = [bit for bit in (
        f'<span>{esc(symbol)}</span>' if symbol else "",
        f'<span>{esc(report_type)}</span>' if report_type else "",
        f'<span>{esc(generated_at[:19].replace("T", " "))}</span>' if generated_at else "",
    ) if bit]

    metrics = [m for m in payload.get("metrics") or [] if isinstance(m, dict) and m.get("label")]
    metric_cards = "".join(
        f'<div class="metric{ _tone_class(m.get("tone")) }">'
        f'<span class="metric-label">{esc(m["label"])}</span>'
        f'<strong class="metric-value">{esc(m.get("value", "—"))}</strong>'
        + (f'<span class="metric-hint">{esc(m["hint"])}</span>' if m.get("hint") else "")
        + "</div>"
        for m in metrics
    )
    metrics_html = f'<div class="metrics">{metric_cards}</div>' if metric_cards else ""

    summary = str(payload.get("summary") or "").strip()
    summary_html = f'<section class="card summary"><h2>摘要</h2><div class="prose">{inline_text(summary)}</div></section>' if summary else ""

    sections_html = []
    for section in payload.get("sections") or []:
        if not isinstance(section, dict) or not section.get("heading"):
            continue
        blocks = "".join(filter(None, (draw_block(b) for b in section.get("blocks") or [] if isinstance(b, dict))))
        sections_html.append(f'<section class="card"><h2>{esc(section["heading"])}</h2>{blocks}</section>')
    body_sections = "".join(sections_html)

    risks = [str(r) for r in payload.get("risks") or [] if str(r).strip()]
    risks_html = (
        f'<section class="card risks"><h2>风险提示</h2><ul class="dot-list">'
        + "".join(f'<li>{inline_text(r)}</li>' for r in risks) + "</ul></section>"
    ) if risks else ""

    references = [r for r in payload.get("references") or [] if isinstance(r, dict) and r.get("title")]
    ref_items = []
    for r in references:
        url = str(r.get("url") or "")
        link = (f'<a href="{esc(url)}" rel="noreferrer noopener">{esc(r["title"])}</a>'
                if url and _SAFE_HREF_RE.match(url) else f"<span>{esc(r['title'])}</span>")
        date = f'<span class="ref-date">{esc(str(r["date"])[:10])}</span>' if r.get("date") else ""
        ref_items.append(f"<li>{link}{date}</li>")
    references_html = (
        f'<section class="card refs"><h2>参考来源</h2><ol class="ref-list">{"".join(ref_items)}</ol></section>'
    ) if ref_items else ""

    disclaimer = str(payload.get("disclaimer") or "本报告由 KStock 智能体基于公开信息自动生成，仅供研究参考，不构成任何投资建议。")

    warnings_html = ""
    if WARNINGS:
        items = "".join(f"<li>{esc(w)}</li>" for w in WARNINGS)
        warnings_html = f'<div class="callout tone-warn render-notes"><strong>渲染说明</strong><ul>{items}</ul></div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
  :root {{ color-scheme: dark; --bg:{C_BG}; --panel:{C_PANEL}; --panel2:{C_PANEL_2}; --border:{C_BORDER};
          --text:{C_TEXT}; --muted:{C_MUTED}; --accent:{C_ACCENT}; --up:{C_UP}; --down:{C_DOWN}; --warn:{C_WARN}; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: radial-gradient(1200px 500px at 70% -10%, rgba(49,199,162,.07), transparent 60%), var(--bg);
         color: var(--text); font: 15px/1.75 -apple-system, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif; }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 34px 22px 60px; }}
  header.hero {{ border: 1px solid var(--border); border-radius: 16px; padding: 26px 28px;
                 background: linear-gradient(160deg, rgba(49,199,162,.09), transparent 55%), var(--panel); }}
  .brand {{ display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--accent); letter-spacing: .12em; }}
  .brand::before {{ content: ""; width: 18px; height: 12px; border-radius: 2px;
                    background: linear-gradient(180deg, var(--accent), #1d8a6e); }}
  h1 {{ margin: 10px 0 6px; font-size: 27px; letter-spacing: .3px; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 6px 14px; color: var(--muted); font-size: 12.5px; }}
  .risk {{ margin-left: auto; border: 1px solid rgba(232,163,61,.45); color: var(--warn);
           border-radius: 999px; padding: 0 10px; font-size: 12px; line-height: 22px; }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-top: 14px; }}
  .metric {{ background: var(--panel2); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px;
             display: flex; flex-direction: column; gap: 2px; }}
  .metric-label {{ font-size: 12px; color: var(--muted); }}
  .metric-value {{ font-size: 20px; font-variant-numeric: tabular-nums; }}
  .metric-hint {{ font-size: 11.5px; color: var(--muted); }}
  .tone-up .metric-value {{ color: var(--up); }} .tone-down .metric-value {{ color: var(--down); }}
  .tone-warn .metric-value {{ color: var(--warn); }}
  main {{ display: flex; flex-direction: column; gap: 14px; margin-top: 14px; }}
  .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 20px 24px; }}
  .card h2 {{ margin: 0 0 10px; font-size: 17px; border-left: 3px solid var(--accent); padding-left: 10px; }}
  .prose p {{ margin: 8px 0; }} .prose strong {{ color: #fff; }}
  code {{ background: var(--panel2); border: 1px solid var(--border); border-radius: 5px; padding: 0 5px; font-size: .9em; }}
  .dot-list {{ margin: 8px 0; padding-left: 20px; }} .dot-list li {{ margin: 5px 0; }}
  .callout {{ border-radius: 10px; padding: 12px 16px; font-size: 14px; margin: 8px 0;
              border: 1px solid rgba(49,199,162,.35); background: rgba(49,199,162,.07); }}
  .callout.tone-warn {{ border-color: rgba(232,163,61,.4); background: rgba(232,163,61,.08); }}
  .callout.tone-down {{ border-color: rgba(224,86,79,.4); background: rgba(224,86,79,.08); }}
  .render-notes ul {{ margin: 6px 0 0; padding-left: 18px; }}
  .tbl-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
  th, td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; white-space: nowrap; }}
  th {{ color: var(--muted); font-weight: 500; }}
  .tbl-note {{ color: var(--muted); font-size: 12px; }}
  figure.chart {{ margin: 14px 0 4px; }}
  figure.chart figcaption {{ font-size: 13.5px; color: var(--muted); margin-bottom: 6px; }}
  figure.chart svg {{ width: 100%; height: auto; display: block; background: var(--panel2);
                      border: 1px solid var(--border); border-radius: 10px; padding: 8px; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; color: var(--muted); margin: 2px 0 4px; }}
  .legend .lg {{ display: inline-flex; align-items: center; gap: 5px; }}
  .legend i {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
  .axis-label {{ font-size: 11.5px; color: var(--muted); }}
  .ref-list {{ padding-left: 20px; margin: 6px 0; }}
  .ref-list li {{ margin: 5px 0; }}
  .ref-list a {{ color: var(--accent); text-decoration: none; }} .ref-list a:hover {{ text-decoration: underline; }}
  .ref-date {{ color: var(--muted); font-size: 12px; margin-left: 8px; }}
  footer {{ margin-top: 18px; color: var(--muted); font-size: 12px; border-top: 1px solid var(--border); padding-top: 14px; }}
  @media print {{
    body {{ background: #fff; color: #111; }}
    .card, header.hero {{ border-color: #ddd; background: #fff; }}
    figure.chart svg, .metric, code {{ background: #f6f8f7; }}
    h1, .prose strong, .metric-value {{ color: #000; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <div class="brand">KSTOCK RESEARCH</div>
    <h1>{esc(title)}</h1>
    <div class="meta">{''.join(meta_bits)}{f'<span class="risk">风险 {esc(risk_level)}</span>' if risk_level else ''}</div>
    {metrics_html}
  </header>
  <main>
    {warnings_html}
    {summary_html}
    {body_sections}
    {risks_html}
    {references_html}
  </main>
  <footer>{esc(disclaimer)}</footer>
</div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    global WARNINGS
    WARNINGS = []
    parser = argparse.ArgumentParser(description="报告 JSON → 自包含 HTML 看板")
    parser.add_argument("payload", type=Path, help="报告 JSON 路径")
    parser.add_argument("-o", "--output", type=Path, default=None, help="输出 HTML 路径（缺省与输入同名 .html）")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.payload.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读取失败：{exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, dict) or not payload.get("title"):
        print("报告 JSON 必须是对象且含 title 字段", file=sys.stderr)
        return 2

    document = build_html(payload)
    output = args.output or args.payload.with_suffix(".html")
    output.write_text(document, encoding="utf-8")
    size_kb = output.stat().st_size / 1024
    print(f"已生成 {output}（{size_kb:.0f} KB）")
    for warning in WARNINGS:
        print(f"  ⚠ {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
