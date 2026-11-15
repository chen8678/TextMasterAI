function envFlag(name: string, fallback = 'false'): boolean {
  const raw = String(import.meta.env[name] ?? fallback).trim().toLowerCase()
  return raw === '1' || raw === 'true' || raw === 'yes'
}

/**
 * 首发 SKU（P0-06 修正）：CET 四级备考 + 知识库 + AI 问答默认开启。
 * 其余能力默认关闭，仅保留代码与显式 VITE_* 打开入口。
 */

/** CET 四级/六级学习中心（词汇/听力/阅读练习/写作/模考/分析） */
export const ENABLE_CET = envFlag('VITE_ENABLE_CET', 'true')

/** 英语学习向导（english_learning）。CET 链路未依赖本模块，默认关闭。 */
export const ENABLE_ENGLISH_LEARNING = envFlag('VITE_ENABLE_ENGLISH_LEARNING', 'false')

/**
 * PRO Studio 前端特性开关：
 * - true: 显示入口并允许路由访问（仍受 requiresPro 约束）
 * - false: 隐藏入口并在路由守卫中拦截
 */
export const ENABLE_PRO_STUDIO = envFlag('VITE_ENABLE_PRO_STUDIO', 'false')

/**
 * BIM / 工地知识库入口。默认关闭。
 */
export const ENABLE_BIM = envFlag('VITE_ENABLE_BIM', 'false')

/** 自进化管理 / 进化历史（公网默认关闭） */
export const ENABLE_SELF_EVOLUTION = envFlag('VITE_ENABLE_SELF_EVOLUTION', 'false')

/** 工作流公网入口（若有独立页；API 另由后端开关） */
export const ENABLE_WORKFLOWS = envFlag('VITE_ENABLE_WORKFLOWS', 'false')

/** Agents 公网入口 */
export const ENABLE_AGENTS = envFlag('VITE_ENABLE_AGENTS', 'false')

/** SCAR UI / 实验入口 */
export const ENABLE_SCAR_UI = envFlag('VITE_ENABLE_SCAR_UI', 'false')
