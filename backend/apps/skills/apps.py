from django.apps import AppConfig


class SkillsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.skills'
    verbose_name = '技能管理'

    def ready(self):
        # 加载并注册内置 Skill
        from apps.skills import builtin  # noqa: F401
