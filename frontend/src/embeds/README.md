# 赛场 / 演示临时嵌入目录（可选）

把临时输入框组件、演示页放在这里，例如：

- `ContestChatInput.vue` — 自定义问答输入框架

注册方式见：`比赛材料/文档/07-临时改动与嵌入对接文档.md` §3.2

```ts
import { defineAsyncComponent } from 'vue'
import { registerCustomComposer, setActiveCustomComposer } from '@/adapters/chatComposer'

registerCustomComposer('contest-input', () =>
  defineAsyncComponent(() => import('@/embeds/ContestChatInput.vue'))
)
setActiveCustomComposer('contest-input')
```
