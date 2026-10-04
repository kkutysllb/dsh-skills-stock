/** Plugin stylesheet: one injected <style> element, all classes prefixed
 * `kss-`. 视觉口径对齐家族插件面板（dsh-animations / 自动化任务
 * TaskManagerPage 同款）：bg-base 底 + 发丝线（.5px border-l3）12px 圆角
 * 透明卡片 + 中性胶囊按钮（button-primary-fill）+ 三级灰文字层级 +
 * 聚焦描边不打环。颜色 ride the host design-platform alias tokens
 * (`--dsw-alias-*`)，literal fallbacks 与家族插件保持同值。 */

const STYLE_ID = 'kss-workbench-styles'

const CSS = `
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
/* 页标题行（20/28/500 标题 + 三级灰副题，自动化任务页同规格） */
.kss-header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.kss-title{margin:0;font-size:20px;line-height:28px;font-weight:500}
.kss-subtitle{margin:2px 0 0;font-size:13px;line-height:21px;color:var(--kss-fg-muted)}
.kss-badges{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
/* 胶囊 tab：发丝线胶囊，激活=中性主胶囊（button-primary-fill） */
.kss-tabs{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.kss-tab{appearance:none;height:28px;padding:0 14px;border:.5px solid var(--kss-border);border-radius:999px;background:transparent;color:var(--kss-fg-muted);font:inherit;font-size:13px;line-height:20px;cursor:pointer;transition:border-color .15s,background .15s,color .15s}
.kss-tab:hover{border-color:var(--kss-border-hover);background:var(--kss-fill-hover)}
.kss-tab.is-active{border-color:transparent;background:var(--kss-btn-bg);color:var(--kss-btn-fg);font-weight:500}
.kss-tabs-spacer{flex:1}
/* 中性胶囊按钮（h32/r16，主按钮=button-primary-fill；次按钮=发丝线） */
.kss-btn{appearance:none;display:inline-flex;align-items:center;justify-content:center;gap:4px;height:32px;padding:0 12px;border:.5px solid var(--kss-border);border-radius:16px;background:transparent;color:var(--kss-fg);font:inherit;font-size:13px;line-height:20px;cursor:pointer;transition:border-color .15s,background .15s}
.kss-btn:hover:not(:disabled){border-color:var(--kss-border-hover);background:var(--kss-fill-hover)}
.kss-btn:disabled{opacity:.4;cursor:not-allowed}
.kss-btn.is-primary{border-color:transparent;background:var(--kss-btn-bg);color:var(--kss-btn-fg)}
.kss-btn.is-primary:hover:not(:disabled){background:var(--kss-btn-bg-hover)}
/* 卡片（家族同款：透明底 + 发丝线 + 12px 圆角，hover 提亮） */
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
/* 状态徽标：低饱和底 + 状态色文字（notice 色系） */
.kss-badge{display:inline-flex;align-items:center;gap:4px;padding:1px 8px;border-radius:999px;font-size:11px;line-height:18px;background:var(--kss-fill);color:var(--kss-fg-muted)}
.kss-badge.is-ok{color:var(--kss-success);background:color-mix(in srgb, var(--kss-success) 12%, transparent)}
.kss-badge.is-miss{color:var(--kss-warn);background:color-mix(in srgb, var(--kss-warn) 12%, transparent)}
/* 版本时间线：发丝线行，hover 提亮 */
.kss-versions{display:flex;flex-direction:column;gap:6px}
.kss-version-row{display:flex;align-items:center;gap:10px;padding:8px 12px;border:.5px solid var(--kss-border);border-radius:10px;background:transparent;transition:background .15s}
.kss-version-row:hover{background:var(--kss-fill-hover)}
.kss-version-tag{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;font-weight:600;color:var(--kss-fg-secondary)}
.kss-table{width:100%;border-collapse:collapse;font-size:12px}
.kss-table th,.kss-table td{border-bottom:.5px solid var(--kss-border);padding:6px 8px;text-align:left;white-space:nowrap}
.kss-table th{color:var(--kss-fg-muted);font-weight:500}
.kss-mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
/* 分组标题与反馈（notice 色系） */
.kss-group-title{margin:0 0 8px;font-size:13px;line-height:21px;font-weight:500;color:var(--kss-fg-secondary)}
.kss-feedback{font-size:12px;line-height:20px}
.kss-feedback.is-warn{color:var(--kss-warn)}
.kss-feedback.is-ok{color:var(--kss-success)}
.kss-feedback.is-err{color:var(--kss-error)}
/* 表单字段：发丝线控件 + 12px 圆角 + 聚焦描边不打环（searchField 口径） */
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
/* 约定/说明（notice 块口径） */
.kss-notes{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:5px;font-size:12px;line-height:20px;color:var(--kss-fg-secondary)}
.kss-footer{font-size:12px;line-height:20px;color:var(--kss-fg-muted)}
/* 运行对比曲线（SVG 坐标色随文字层级） */
.kss-compare{overflow-x:auto}
.kss-curve-block{display:flex;flex-direction:column;gap:6px;margin-top:4px}
.kss-curve-svg{display:block;width:100%;max-width:640px;height:auto}
.kss-curve-grid{stroke:var(--kss-border-strong);stroke-width:1;stroke-dasharray:3 3;fill:none}
.kss-curve-axis{fill:var(--kss-fg-muted);font-size:10px}
.kss-curve-legend{fill:var(--kss-fg-secondary);font-size:11px}
.kss-curve-line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
/* 报告内嵌预览：发丝线 + 12px 圆角 */
.kss-report-frame{width:100%;min-height:560px;height:64vh;border:.5px solid var(--kss-border);border-radius:12px;background:var(--kss-fill);display:block}
.kss-state{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:56px 0;color:var(--kss-fg-muted);font-size:13px;line-height:21px}
.kss-error{color:var(--kss-error);font-size:12px;line-height:20px;word-break:break-all}
`

/** Install once per document; idempotent across plugin re-activation. */
export function installStyles(): () => void {
  let el = document.getElementById(STYLE_ID) as HTMLStyleElement | null
  if (el !== null) return () => {}
  el = document.createElement('style')
  el.id = STYLE_ID
  el.textContent = CSS
  document.head.append(el)
  return () => {
    el?.remove()
    el = null
  }
}
