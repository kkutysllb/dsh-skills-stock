/** Build: Host ESM bundle + Web client bundle（对齐 dsh-kylin-automation）。
 *
 * - lib/index.js: Host bundle；`@deepseek-ai/*` / `cordis` 保持 external
 *   （由 harness 运行时提供），产物随仓提交（零构建链安装的前提）。
 * - lib/client.js: Web client bundle，client module-table 契约——
 *   window.__ModuleLoader__.load({ id, factory }) 包裹，react/react-dom
 *   走宿主 shell 的静态模块表（external）。
 */

import { readFile, rm, writeFile } from 'node:fs/promises'
import { build } from 'esbuild'

const PACKAGE_ID = 'dsh-skills-stock'

await rm('lib', { recursive: true, force: true })

// ── host bundle ───────────────────────────────────────────────────────────────
await build({
  entryPoints: ['src/index.ts'],
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'node20',
  outfile: 'lib/index.js',
  external: ['@deepseek-ai/*', 'cordis'],
})

// ── web client bundle ─────────────────────────────────────────────────────────
await build({
  entryPoints: ['src/client/index.tsx'],
  bundle: true,
  format: 'cjs',
  platform: 'browser',
  target: 'es2022',
  outfile: 'lib/client.js',
  sourcemap: true,
  external: ['react', 'react-dom', 'react/jsx-runtime'],
  define: {
    'process.env.NODE_ENV': '"production"',
  },
  banner: {
    js: [
      `window.__ModuleLoader__.load({ id: ${JSON.stringify(PACKAGE_ID)}, factory: (require) => {`,
      'var module = { exports: {} }; var exports = module.exports;',
    ].join('\n'),
  },
  footer: {
    js: 'return module.exports; } });',
  },
})

// Whitespace-only lines inside generated template literals keep committed
// artifacts diff-dirty; normalize them.
for (const file of ['lib/index.js', 'lib/client.js']) {
  const source = await readFile(file, 'utf8')
  await writeFile(file, source.replace(/[ \t]+$/gm, ''))
}

console.log('[dsh-skills-stock] built Host and Web client bundles')
