/** 设置页「数据源」区块：A 股投研凭据的受控配置（super-ppts settings.section
 * 同款挂载）。状态徽章 + 保存表单；凭据只在保存方向流动。 */

import { useEffect, useSyncExternalStore } from 'react'
import type { WorkbenchRuntime, Translate } from './runtime.ts'
import type { PanelState } from './runtime.ts'

export function usePanelState(runtime: WorkbenchRuntime): PanelState {
  return useSyncExternalStore(runtime.source.subscribe, runtime.source.getSnapshot, runtime.source.getSnapshot)
}

export function KeyBadge(props: { t: Translate; ok: boolean; label: string }): React.ReactElement {
  const { t, ok, label } = props
  return (
    <span className={`kss-badge ${ok ? 'is-ok' : 'is-miss'}`} title={label}>
      <span aria-hidden='true'>{ok ? '●' : '○'}</span>
      {label} · {ok ? t('configured') : t('notConfigured')}
    </span>
  )
}

/** 设置页主视图（settings.section slot 挂载）。 */
export function DataSourcesSettingsView(props: { t: Translate; runtime: WorkbenchRuntime }): React.ReactElement {
  const { t, runtime } = props
  const state = usePanelState(runtime)

  useEffectOnce(() => { void runtime.refresh() }, [runtime])

  if (state.phase === 'loading' || state.phase === 'idle') {
    return <div className='kss-root'><div className='kss-state'>{t('refreshing')}</div></div>
  }
  if (state.phase === 'error' && state.status === undefined) {
    return (
      <div className='kss-root'>
        <div className='kss-state'>
          <span>{t('errorLoad')}</span>
          <span className='kss-error'>{state.error}</span>
          <button type='button' className='kss-btn' onClick={() => { void runtime.refresh() }}>{t('retry')}</button>
        </div>
      </div>
    )
  }
  const status = state.status
  return (
    <div className='kss-root'>
      <section className='kss-card'>
        <h2 className='kss-card-title'>{t('navDataSources')}</h2>
        <p className='kss-card-hint'>{t('settingsIntro')}</p>
        <form
          id='kss-secrets-form'
          className='kss-fields'
          onSubmit={(event) => {
            event.preventDefault()
            const form = event.currentTarget
            const data = new FormData(form)
            void runtime.saveSecrets({
              tushareToken: String(data.get('tushare') ?? ''),
              iwencaiKey: String(data.get('iwencai') ?? ''),
            }).then(() => { form.reset() }).catch(() => undefined)
          }}
        >
          <label className='kss-field'>
            <span className='kss-field-head'>
              <span className='kss-label'>{t('tushareLabel')}</span>
              <KeyBadge t={t} ok={status?.keys.TUSHARE_TOKEN === true} label='Tushare' />
            </span>
            <input
              className='kss-input' name='tushare' type='password' autoComplete='off' spellCheck={false}
              placeholder={status?.keys.TUSHARE_TOKEN === true ? t('keepBlank') : ''}
            />
            <span className='kss-field-hint'>{t('tushareHint')}</span>
          </label>
          <label className='kss-field'>
            <span className='kss-field-head'>
              <span className='kss-label'>{t('iwencaiLabel')}</span>
              <KeyBadge t={t} ok={status?.keys.IWENCAI_API_KEY === true} label='iWenCai' />
            </span>
            <input
              className='kss-input' name='iwencai' type='password' autoComplete='off' spellCheck={false}
              placeholder={status?.keys.IWENCAI_API_KEY === true ? t('keepBlank') : ''}
            />
            <span className='kss-field-hint'>{t('iwencaiHint')}</span>
          </label>
        </form>
        <div className='kss-actions'>
          <button type='submit' form='kss-secrets-form' className='kss-btn is-primary' disabled={state.saving === true}>
            {state.saving === true ? t('saving') : t('save')}
          </button>
          {state.savedKeys !== undefined && state.savedKeys.length > 0 && (
            <span className='kss-feedback is-ok'>{t('saved', { keys: state.savedKeys.join(', ') })}</span>
          )}
          {state.saveError !== undefined && (
            <span className='kss-feedback is-err'>{t('saveFailed')}：{state.saveError}</span>
          )}
          {status?.secretsWritable === false && (
            <span className='kss-feedback is-err'>{t('secretsUnavailable', { home: status.stockHome })}</span>
          )}
        </div>
        <p className='kss-card-hint'>
          <code className='kss-path'>{status?.secretsPath ?? '~/.dsh-stock/secrets.env'}</code>
          {' '}{t('dataSourceHint')}
        </p>
      </section>
      <NotesCard t={t} />
    </div>
  )
}

/** 一次性 effect（挂载时拉数据）。 */
function useEffectOnce(fn: () => void, deps: unknown[]): void {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(fn, deps)
}

/** 使用约定卡（工作台与设置页共用）。 */
export function NotesCard(props: { t: Translate }): React.ReactElement {
  const { t } = props
  return (
    <section className='kss-card'>
      <h2 className='kss-card-title'>{t('sectionNotes')}</h2>
      <ol className='kss-notes'>
        <li>{t('note1')}</li>
        <li>{t('note2')}</li>
        <li>{t('note3')}</li>
        <li>{t('note4')}</li>
      </ol>
      <p className='kss-footer'>{t('disclaimer')}</p>
    </section>
  )
}
