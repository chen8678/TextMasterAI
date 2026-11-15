from django.apps import AppConfig


class EnglishLearningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.english_learning"
    verbose_name = "英语学习定制"

    def ready(self):
        # 注册 Skill（依赖 apps.skills 已加载 SkillRegistry）
        from apps.english_learning.skill_handlers import register_english_skills  # noqa: F401

        register_english_skills()
