/** 会话桥（super-ppts sendToChatV3 同款链路的 TS 移植）：
 * 1) 定位会话——当前会话即目标；带 workspaceId 且当前会话不在该工作区时
 *    uiWorkspace.openWorkspace 切换；无会话时 sessions.create + open；
 * 2) sessions.scope(id).conversation.input.for(actx) 取输入 shell，
 *    先 setDraft(text) 再 submit()（顺序不可颠倒）；
 * 3) submit 不存在或任一步抛错 → 不得假装提交成功，降级剪贴板。
 * 返回 'submitted'（已写入并提交）/ 'copied'（降级剪贴板）/ 'none'（全失败）。
 */

import type { ClientContext, ConversationService, InputShell } from './contracts.ts'

export interface ConversationBridge {
  send(text: string, workspaceId?: string): Promise<'submitted' | 'copied' | 'none'>
  backToChat(): void
}

export function createConversationBridge(ctx: ClientContext): ConversationBridge {
  const backToChat = (): void => {
    try { ctx.layout?.selectPanel(null) } catch { /* layout service absent */ }
  }

  const clipboardFallback = async (text: string): Promise<'copied' | 'none'> => {
    try {
      await navigator.clipboard?.writeText(text)
      return 'copied'
    } catch {
      return 'none'
    }
  }

  const send = (text: string, workspaceId?: string): Promise<'submitted' | 'copied' | 'none'> => {
    const sessions = ctx.sessions
    let plan: Promise<string | null>
    try {
      if (sessions === undefined || sessions.list === undefined || typeof sessions.list.getSnapshot !== 'function') {
        return clipboardFallback(text)
      }
      const current = sessions.list.getSnapshot().current
      const wsList = ctx.workspaces?.list !== undefined && typeof ctx.workspaces.list.getSnapshot === 'function'
        ? ctx.workspaces.list.getSnapshot() as { items?: Array<{ workspaceId?: string; sessionIds?: string[] }> }
        : null
      let wsOfCurrent: string | undefined
      if (current !== undefined && wsList?.items !== undefined) {
        for (const ws of wsList.items) {
          if ((ws.sessionIds ?? []).includes(current)) {
            wsOfCurrent = ws.workspaceId
            break
          }
        }
      }
      const wantsSwitch = workspaceId !== undefined && wsOfCurrent !== workspaceId
      if (current !== undefined && !wantsSwitch) {
        plan = Promise.resolve(current)
      } else if (ctx.uiWorkspace?.openWorkspace !== undefined && wsList?.items !== undefined && wsList.items.length > 0) {
        const target = workspaceId ?? wsOfCurrent ?? wsList.items[0]!.workspaceId
        plan = Promise.resolve(ctx.uiWorkspace.openWorkspace(target as string)).then(() =>
          sessions.list!.getSnapshot().current ?? null)
      } else if (typeof sessions.create === 'function') {
        plan = Promise.resolve(sessions.create()).then((id) => {
          try {
            if (typeof sessions.open === 'function') sessions.open(id)
          } catch {
            // 已选中
          }
          backToChat()
          return id
        })
      } else {
        plan = Promise.resolve(null)
      }
    } catch (bridgeError) {
      console.warn('[dsh-skills-stock] 会话桥定位异常:', bridgeError instanceof Error ? bridgeError.message : bridgeError)
      return clipboardFallback(text)
    }
    return plan.then((sessionId) => {
      if (sessionId === null || sessionId === undefined) return clipboardFallback(text)
      try {
        backToChat()
        const shell = resolveInputShell(sessionId)
        if (shell !== null && typeof shell.setDraft === 'function') {
          shell.setDraft(text)
          if (typeof shell.submit === 'function') {
            shell.submit()
            return 'submitted'
          }
          console.warn('[dsh-skills-stock] 宿主输入面无 submit，降级剪贴板')
        }
      } catch {
        // 服务不可达：降级剪贴板
      }
      return clipboardFallback(text)
    }, () => clipboardFallback(text))
  }

  /** 解析会话的输入 shell：根 conversation 服务优先（宿主 ≥0.1.6 的
   * input registry），旧 scope(id).conversation.input.for(actx) 路径兜底。
   * dsh-animations / super-ppts 同款双路径。 */
  const resolveInputShell = (sessionId: string): InputShell | null => {
    const sessions = ctx.sessions
    if (sessions === undefined || typeof sessions.scope !== 'function') return null
    // ① 根 ctx 的 conversation 服务（0.1.6+ 公开面）
    try {
      const conversation = typeof ctx.get === 'function'
        ? ctx.get('conversation') as ConversationService | undefined
        : ctx.conversation
      const input = conversation?.input
      if (input !== undefined) {
        if (typeof input.shell === 'function') return input.shell(sessionId)
        if (typeof input.for === 'function') {
          const actx = sessions.scope(sessionId)
          if (actx !== undefined) return input.for(actx)
        }
      }
    } catch { /* 根服务不可达：试旧路径 */ }
    // ② 旧路径：会话作用域上的 conversation（<0.1.6 宿主）
    try {
      const actx = sessions.scope(sessionId)
      const legacyInput = actx?.conversation?.input
      if (legacyInput !== undefined && typeof legacyInput.for === 'function') return legacyInput.for(actx)
    } catch { /* 作用域路径不可达 */ }
    return null
  }

  return { send, backToChat }
}
