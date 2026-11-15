# 英语预置知识库 · 数据来源

> 由 `scripts/download_english_curriculum_data.sh` 下载到 `raw/`。大文件默认不提交 Git（见根 `.gitignore`）。

## 阶段与文件

| 阶段 | slug | 本地文件 | 开源来源 | 许可 |
|------|------|----------|----------|------|
| 小学 | `primary` | `primary_merged.jsonl` | [kajweb/dict](https://github.com/kajweb/dict) 人教版 PEP 3–6 年级（NetEase CDN zip） | 社区词库，仅供学习 |
| 初中 | `junior` | `1-初中-顺序.json` | [KyleBing/english-vocabulary](https://github.com/KyleBing/english-vocabulary) | MIT |
| 高中 | `senior` | `2-高中-顺序.json` | 同上 | MIT |
| 四级 | `cet4` | `3-CET4-顺序.json` | 同上 | MIT |
| 六级 | `cet6` | `4-CET6-顺序.json` | 同上 | MIT |

## 词量（约）

| 阶段 | 词条数 |
|------|--------|
| 小学（合并 8 册） | ~800 |
| 初中 | ~3223 |
| 高中 | ~6008 |
| CET-4 | ~7508 |
| CET-6 | ~5651 |

## 可选扩展（需你后续准备）

| 内容 | 建议来源 | 格式 |
|------|----------|------|
| 四六级**真题** Markdown | [wamich/english-exem-md](https://github.com/wamich/english-exem-md) | `.md` 按年份 |
| 带词根/助记 | [vxiaozhi/vocabulary-book-by-deepseek](https://github.com/vxiaozhi/vocabulary-book-by-deepseek) | `data/cet4/` |
| 教材同步分册 | [lilinji/English](https://github.com/lilinji/English) | `.xlsx`（需转 Markdown） |

## 初始化

```bash
chmod +x scripts/download_english_curriculum_data.sh
./scripts/download_english_curriculum_data.sh

cd backend
python manage.py init_english_curriculum          # 导入 + 向量化（较慢）
python manage.py init_english_curriculum --skip-vectorize  # 仅入库
python manage.py init_english_curriculum --backfill-users  # 给已有用户挂只读库
```

## 版权说明

- KyleBing 词库为开源 MIT，请在产品关于页保留出处。
- kajweb/有道词库为第三方整理，**商用前请自行合规审查**；校内演示/研究通常可接受。
