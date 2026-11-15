/**
 * 侧栏菜单扩展 —— 临时加入口不必改 MainShell 结构，往 menuExtras 塞一项即可。
 * 注意：path 对应路由须已存在，或同步在 router/index.ts 增加路由。
 */
export interface MenuExtraItem {
  path: string
  label: string
  /** 需要登录 */
  requiresAuth?: boolean
  /** 仅管理员 */
  adminOnly?: boolean
  /** 仅 PRO（且受 VITE_ENABLE_PRO_STUDIO 等业务约束时由页面自行判断） */
  proOnly?: boolean
}

/**
 * 赛场临时菜单：默认空。
 * 示例：
 *   menuExtras.push({ path: '/chat', label: '智能问答（演示）', requiresAuth: true })
 */
export const menuExtras: MenuExtraItem[] = []

export function addMenuExtra(item: MenuExtraItem): void {
  const exists = menuExtras.some((x) => x.path === item.path && x.label === item.label)
  if (!exists) menuExtras.push(item)
}

export function clearMenuExtras(): void {
  menuExtras.length = 0
}
