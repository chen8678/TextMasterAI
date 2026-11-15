"""
Skill 自进化（MVP）：信号检测 → 异步任务 → 草案入库存储 → 人工审批后合并至 Skill.metadata。

设计参考：OpenSpace skill_engine（逻辑自研实现，非拷贝）；见项目根文档
《开源参考核心代码提取步骤与框架对照（2026-04-11）》。
"""
from .manager import schedule_evolution_after_user_turn

__all__ = ["schedule_evolution_after_user_turn"]
