/**
 * 问答输入区（Composer）适配层 —— 赛场/演示临时改动优先改本文件，少动 AgentChat.vue。
 *
 * 用法示例（赛前 5 分钟改文案）：
 *   applyComposerPatch({ placeholder: '请输入与课程相关的问题…' })
 *
 * 若需整块替换输入框架，见 registerCustomComposer / resolveCustomComposer。
 */
import type { Component } from 'vue'

export interface ChatComposerConfig {
  /** 输入框占位符 */
  placeholder: string
  /** textarea 最小行数 */
  minRows: number
  /** textarea 最大行数 */
  maxRows: number
  /** 是否 Enter 发送（Shift+Enter 换行由页面自行处理时可关闭） */
  sendOnEnter: boolean
  /** 发送按钮文案 */
  sendButtonLabel: string
  /** 生成中暂停按钮文案 */
  stopButtonLabel: string
}

/** 默认配置：与产品口径一致，可被 patch / 环境覆盖 */
export const chatComposerConfig: ChatComposerConfig = {
  placeholder: '在这里输入你的问题...',
  minRows: 1,
  maxRows: 4,
  sendOnEnter: true,
  sendButtonLabel: '发送',
  stopButtonLabel: '暂停生成',
}

/** 浅合并覆盖；返回合并后的完整配置（便于调试打印） */
export function applyComposerPatch(patch: Partial<ChatComposerConfig>): ChatComposerConfig {
  Object.assign(chatComposerConfig, patch)
  return chatComposerConfig
}

type ComposerFactory = () => Component

const customComposers = new Map<string, ComposerFactory>()

/**
 * 注册自定义输入框架组件。
 * 页面侧：若 customComposerId 有值且已注册，则渲染该组件，否则用默认 el-input。
 */
export function registerCustomComposer(id: string, factory: ComposerFactory): void {
  customComposers.set(id, factory)
}

export function resolveCustomComposer(id: string | null | undefined): Component | null {
  if (!id) return null
  const factory = customComposers.get(id)
  return factory ? factory() : null
}

/** 当前启用的自定义 Composer id；null 表示用默认输入框 */
export let activeCustomComposerId: string | null = null

export function setActiveCustomComposer(id: string | null): void {
  activeCustomComposerId = id
}
