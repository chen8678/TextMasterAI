/** 默认目标：大学英语四级（产品主路径锁定 CET-4） */
export const DEFAULT_LEVEL_TAG = 'stage:cet4'

/** 默认考试/阶段目标文案 */
export const DEFAULT_EXAM_GOAL = '大学英语四级'

/** 提交 API 时仍为 level_tags 数组（仅含一项） */
export function levelTagsPayload(tag: string): string[] {
  const t = String(tag || '').trim()
  return t ? [t] : [DEFAULT_LEVEL_TAG]
}

/** 从档案多条标签中取主学段（兼容旧数据） */
export function pickPrimaryLevelTag(tags: string[]): string {
  const normalized = normalizeLevelTagsForDisplay(tags)
  return normalized[0] || DEFAULT_LEVEL_TAG
}

export type LevelTagOption = { label: string; value: string }

export type LevelTagOptionGroup = { label: string; options: LevelTagOption[] }

export const LEVEL_TAG_OPTION_GROUPS: LevelTagOptionGroup[] = [
  {
    label: '小学阶段',
    options: [
      { label: '小学 · 3–4 年级', value: 'stage:primary:34' },
      { label: '小学 · 5–6 年级', value: 'stage:primary:56' }
    ]
  },
  {
    label: '初中阶段',
    options: [
      { label: '初中 · 七年级（初一）', value: 'stage:junior:7' },
      { label: '初中 · 八年级（初二）', value: 'stage:junior:8' },
      { label: '初中 · 九年级（初三）', value: 'stage:junior:9' }
    ]
  },
  {
    label: '高中阶段',
    options: [
      { label: '高中 · 高一', value: 'stage:senior:10' },
      { label: '高中 · 高二', value: 'stage:senior:11' },
      { label: '高中 · 高三', value: 'stage:senior:12' }
    ]
  },
  {
    label: '大学考试',
    options: [
      { label: '大学英语 · 四级（CET-4）', value: 'stage:cet4' },
      { label: '大学英语 · 六级（CET-6）', value: 'stage:cet6' }
    ]
  },
  {
    label: '其他目标（可选）',
    options: [
      { label: '雅思 · 目标 6 分', value: 'goal:IELTS6' },
      { label: '雅思 · 目标 7 分', value: 'goal:IELTS7' }
    ]
  }
]

const LEGACY_CEFR_MAP: Record<string, string> = {
  'CEFR:A1': 'stage:primary:56',
  'CEFR:A2': 'stage:junior:7',
  'CEFR:B1': 'stage:junior:8',
  'CEFR:B2': 'stage:senior:11',
  'CEFR:C1': 'stage:cet6',
  'goal:CET': 'stage:cet4'
}

/** 将旧档案中的 CEFR 标签转为学段标签，便于下拉展示 */
export function normalizeLevelTagsForDisplay(tags: string[]): string[] {
  const out: string[] = []
  for (const raw of tags) {
    const t = String(raw || '').trim()
    if (!t) continue
    if (LEGACY_CEFR_MAP[t.toUpperCase()] || LEGACY_CEFR_MAP[t]) {
      out.push(LEGACY_CEFR_MAP[t.toUpperCase()] || LEGACY_CEFR_MAP[t])
      continue
    }
    if (/^CEFR:[ABC][12]$/i.test(t)) {
      out.push(LEGACY_CEFR_MAP[t.toUpperCase()] || t)
      continue
    }
    out.push(t)
  }
  return [...new Set(out)]
}

/** 测评组卷用的内部难度（对接 sample_questions.json 的 level 字段） */
export function inferAssessmentLevelFromTags(tags: string[]): string {
  const joined = tags.join(' ').toLowerCase()
  if (/cet6|六级|stage:cet6/.test(joined)) return 'B2'
  if (/cet4|四级|goal:cet|stage:cet4/.test(joined)) return 'B2'
  if (/senior|高中|stage:senior|高一|高二|高三/.test(joined)) return 'B2'
  if (/junior|初中|stage:junior|初一|初二|初三/.test(joined)) return 'B1'
  if (/primary|小学|stage:primary/.test(joined)) return 'A2'
  for (const t of tags) {
    const u = String(t).toUpperCase().replace(/^CEFR:/, '')
    if (/^[ABC][12]$/.test(u)) return u
  }
  return 'B1'
}
