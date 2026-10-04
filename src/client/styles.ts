/** Plugin stylesheet: one injected <style> element, all classes prefixed
 * `kss-`. Colors ride the host design-platform alias tokens (`--dsw-alias-*`,
 * light on `:root`, dark on `body[data-ds-dark-theme]`) so both themes adapt;
 * literal fallbacks keep the panel readable on hosts without the token set. */

const STYLE_ID = 'kss-workbench-styles'

const CSS = `
.kss-panel, .kss-root {
  --kss-fg: var(--dsw-alias-label-primary, #1f2329);
  --kss-fg-secondary: var(--dsw-alias-label-secondary, #5a6472);
  --kss-fg-muted: var(--dsw-alias-label-tertiary, #8a94a3);
  --kss-layer: var(--dsw-alias-bg-layer-2, #ffffff);
  --kss-layer-3: var(--dsw-alias-bg-layer-3, #f5f6f7);
  --kss-fill: var(--dsw-alias-bg-skeleton, rgba(127, 127, 127, 0.14));
  --kss-fill-hover: var(--dsw-alias-interactive-bg-hover, rgba(127, 127, 127, 0.2));
  --kss-border: var(--dsw-alias-border-l3, rgba(127, 127, 127, 0.3));
  --kss-border-strong: var(--dsw-alias-border-l4, rgba(127, 127, 127, 0.48));
  --kss-primary: var(--dsw-alias-brand-primary-new-colorprimary-new-color, #c7222a);
  --kss-primary-fg: var(--dsw-alias-label-primary-foreground, #ffffff);
  --kss-error: var(--dsw-alias-state-error-primary, #d0403d);
  --kss-success: var(--dsw-alias-state-success-primary, #0f9d58);
  --kss-info: var(--dsw-alias-state-business-primary, #2e90fa);
  --kss-warn: var(--dsw-alias-state-warn-primary, #f5a209);
}
.kss-panel{display:flex;flex-direction:column;height:100%;min-height:0;overflow:auto;padding:20px 24px 32px;gap:16px;font-size:13px;line-height:1.5;color:var(--kss-fg);background:transparent}
.kss-root{display:flex;flex-direction:column;gap:16px;max-width:760px;color:var(--kss-fg);font-size:13px;line-height:1.5}
.kss-tabs{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.kss-tab{appearance:none;border:1px solid var(--kss-border);background:var(--kss-layer);color:var(--kss-fg-secondary);border-radius:999px;padding:4px 14px;font-size:12px;cursor:pointer}
.kss-tab:hover{background:var(--kss-fill-hover)}
.kss-tab.is-active{background:var(--kss-primary);border-color:var(--kss-primary);color:var(--kss-primary-fg);font-weight:600}
.kss-tabs-spacer{flex:1}
.kss-versions{display:flex;flex-direction:column;gap:6px}
.kss-version-row{display:flex;align-items:center;gap:10px;padding:6px 10px;border:1px solid var(--kss-border);border-radius:8px;background:var(--kss-layer-3)}
.kss-version-tag{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;font-weight:600;color:var(--kss-primary)}
.kss-table{width:100%;border-collapse:collapse;font-size:12px}
.kss-table th,.kss-table td{border-bottom:1px solid var(--kss-border);padding:5px 8px;text-align:left;white-space:nowrap}
.kss-table th{color:var(--kss-fg-muted);font-weight:500}
.kss-mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.kss-compare{overflow-x:auto}
.kss-curve-block{display:flex;flex-direction:column;gap:6px;margin-top:4px}
.kss-curve-svg{display:block;width:100%;max-width:640px;height:auto}
.kss-curve-grid{stroke:var(--kss-border-strong);stroke-width:1;stroke-dasharray:3 3;fill:none}
.kss-curve-axis{fill:var(--kss-fg-muted);font-size:10px}
.kss-curve-legend{fill:var(--kss-fg-secondary);font-size:11px}
.kss-curve-line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.kss-skill-meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.kss-feedback.is-warn{color:var(--kss-warn)}
.kss-header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.kss-title{margin:0;font-size:17px;font-weight:600;letter-spacing:.2px}
.kss-subtitle{margin:2px 0 0;font-size:12px;color:var(--kss-fg-muted)}
.kss-badges{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.kss-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:999px;font-size:11px;border:1px solid var(--kss-border);color:var(--kss-fg-secondary);background:var(--kss-layer)}
.kss-badge.is-ok{color:var(--kss-success);border-color:color-mix(in srgb, var(--kss-success) 45%, transparent)}
.kss-badge.is-miss{color:var(--kss-warn);border-color:color-mix(in srgb, var(--kss-warn) 45%, transparent)}
.kss-btn{appearance:none;border:1px solid var(--kss-border-strong);background:var(--kss-layer);color:var(--kss-fg);border-radius:8px;padding:5px 12px;font-size:12px;cursor:pointer;transition:background .15s ease,border-color .15s ease}
.kss-btn:hover{background:var(--kss-fill-hover)}
.kss-btn:disabled{opacity:.55;cursor:default}
.kss-btn.is-primary{background:var(--kss-primary);border-color:var(--kss-primary);color:var(--kss-primary-fg)}
.kss-btn.is-primary:hover{filter:brightness(1.06)}
.kss-card{border:1px solid var(--kss-border);border-radius:12px;background:var(--kss-layer);padding:16px;display:flex;flex-direction:column;gap:12px}
.kss-card-title{margin:0;font-size:13px;font-weight:600}
.kss-card-hint{margin:0;font-size:12px;color:var(--kss-fg-muted)}
.kss-fields{display:flex;flex-direction:column;gap:18px;margin-top:4px}
.kss-field{display:flex;flex-direction:column;gap:6px}
.kss-field-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
.kss-label{font-size:12.5px;font-weight:600;color:var(--kss-fg-secondary)}
.kss-input{width:100%;box-sizing:border-box;border:1px solid var(--kss-border-strong);border-radius:8px;background:var(--kss-fill);color:var(--kss-fg);padding:9px 12px;font-size:13px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:.3px}
.kss-input:hover{border-color:var(--kss-primary)}
.kss-input:focus{outline:none;border-color:var(--kss-primary);background:var(--kss-layer);box-shadow:0 0 0 2px color-mix(in srgb, var(--kss-primary) 18%, transparent)}
.kss-input::placeholder{color:var(--kss-fg-muted);letter-spacing:0}
.kss-path{display:inline-block;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;color:var(--kss-fg-secondary);background:var(--kss-fill);border:1px solid var(--kss-border);border-radius:6px;padding:2px 8px}
.kss-field-hint{font-size:11px;color:var(--kss-fg-muted)}
.kss-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.kss-feedback{font-size:12px}
.kss-feedback.is-ok{color:var(--kss-success)}
.kss-feedback.is-err{color:var(--kss-error)}
.kss-groups{display:flex;flex-direction:column;gap:14px}
.kss-group-title{margin:0 0 8px;font-size:12px;font-weight:600;color:var(--kss-fg-secondary);letter-spacing:.3px}
.kss-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.kss-skill{display:flex;flex-direction:column;gap:6px;border:1px solid var(--kss-border);border-radius:10px;padding:10px 12px;background:var(--kss-layer-3);transition:border-color .15s ease}
.kss-skill:hover{border-color:var(--kss-border-strong)}
.kss-skill-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
.kss-skill-name{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;font-weight:600;color:var(--kss-primary)}
.kss-skill-copy{appearance:none;border:none;background:transparent;color:var(--kss-fg-muted);font-size:11px;cursor:pointer;padding:2px 4px;border-radius:6px}
.kss-skill-copy:hover{background:var(--kss-fill);color:var(--kss-fg)}
.kss-skill-desc{margin:0;font-size:11.5px;color:var(--kss-fg-secondary);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.kss-skill-keys{font-size:10.5px;color:var(--kss-warn)}
.kss-notes{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:5px;font-size:12px;color:var(--kss-fg-secondary)}
.kss-footer{font-size:11px;color:var(--kss-fg-muted)}
.kss-state{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:48px 0;color:var(--kss-fg-muted);font-size:13px}
.kss-error{color:var(--kss-error);font-size:12px;word-break:break-all}
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
