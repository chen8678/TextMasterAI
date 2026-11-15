/**
 * 运行时嵌入注册表：把「临时要换的文案 / 外链 / 演示开关」集中在一处。
 * 也可在浏览器控制台（开发态）挂到 window.__TM_EMBED__ 便于现场调试。
 */
import { applyComposerPatch, type ChatComposerConfig } from './chatComposer'
import { addMenuExtra, type MenuExtraItem } from './menuExtras'

export interface EmbedRuntimeConfig {
  /** 首页副标题等轻量文案覆盖（Home 等页面可读） */
  homeTagline?: string
  /** @deprecated P0-07 首发免费，不再使用升级外链 */
  proUpgradeUrl?: string
  /** 演示模式：可隐藏部分非竞赛入口（由页面自行读取） */
  demoMode?: boolean
  /** 额外问答示例气泡文案 */
  chatExamplePrompts?: string[]
}

export const embedRuntime: EmbedRuntimeConfig = {
  demoMode: false,
  chatExamplePrompts: undefined,
}

export function applyEmbedRuntime(patch: Partial<EmbedRuntimeConfig>): EmbedRuntimeConfig {
  Object.assign(embedRuntime, patch)
  return embedRuntime
}

/** 一站式赛场补丁入口 */
export function applyContestPatch(options: {
  composer?: Partial<ChatComposerConfig>
  menuExtra?: MenuExtraItem
  runtime?: Partial<EmbedRuntimeConfig>
}): void {
  if (options.composer) applyComposerPatch(options.composer)
  if (options.menuExtra) addMenuExtra(options.menuExtra)
  if (options.runtime) applyEmbedRuntime(options.runtime)
}

declare global {
  interface Window {
    __TM_EMBED__?: {
      applyContestPatch: typeof applyContestPatch
      applyComposerPatch: typeof applyComposerPatch
      embedRuntime: typeof embedRuntime
    }
  }
}

/** 开发/演示构建下挂到 window，方便控制台热改（生产也可按需打开） */
export function exposeEmbedDebug(): void {
  if (typeof window === 'undefined') return
  window.__TM_EMBED__ = {
    applyContestPatch,
    applyComposerPatch,
    embedRuntime,
  }
}
