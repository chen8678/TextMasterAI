from django.conf import settings
from django.db import models


class CETExam(models.Model):
    """四六级考试/试卷定义"""

    EXAM_TYPE_CHOICES = (
        ("cet4", "四级"),
        ("cet6", "六级"),
    )

    exam_type = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES)
    exam_date = models.DateField(null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    is_official = models.BooleanField(default=True)
    title = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "四六级试卷"
        verbose_name_plural = "四六级试卷"

    def __str__(self) -> str:
        return self.title or f"{self.get_exam_type_display()} - {self.year or ''}"


class KnowledgePoint(models.Model):
    """知识点：词汇/语法/技能等"""

    CATEGORY_CHOICES = (
        ("vocabulary", "词汇"),
        ("grammar", "语法"),
        ("listening", "听力"),
        ("reading", "阅读"),
        ("translation", "翻译"),
        ("writing", "写作"),
        ("strategy", "应试技巧"),
    )

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "知识点"
        verbose_name_plural = "知识点"

    def __str__(self) -> str:
        return self.name


class CETQuestion(models.Model):
    """题目：与试卷和知识点关联"""

    QUESTION_TYPE_CHOICES = (
        ("listening", "听力"),
        ("reading", "阅读"),
        ("translation", "翻译"),
        ("writing", "写作"),
        ("vocabulary", "词汇"),
        ("grammar", "语法"),
    )

    exam = models.ForeignKey(
        CETExam, on_delete=models.CASCADE, related_name="questions", null=True, blank=True
    )
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    question_number = models.IntegerField(default=1)
    content = models.TextField()
    options = models.JSONField(default=list, blank=True)
    correct_answer = models.TextField(blank=True, default="")
    explanation = models.TextField(blank=True, default="")
    knowledge_points = models.ManyToManyField(
        KnowledgePoint, related_name="questions", blank=True
    )
    difficulty = models.IntegerField(default=3)

    class Meta:
        verbose_name = "四六级题目"
        verbose_name_plural = "四六级题目"
        ordering = ["exam_id", "question_number"]

    def __str__(self) -> str:
        return f"{self.get_question_type_display()} Q{self.question_number}"


class UserAnswer(models.Model):
    """用户做题记录，用于错题本和学习分析"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey(CETQuestion, on_delete=models.CASCADE)
    user_answer = models.TextField(blank=True, default="")
    is_correct = models.BooleanField(default=False)
    score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "用户做题记录"
        verbose_name_plural = "用户做题记录"


class Vocabulary(models.Model):
    """词汇表条目"""

    EXAM_TYPE_CHOICES = (
        ("cet4", "四级"),
        ("cet6", "六级"),
        ("general", "通用"),
    )

    word = models.CharField(max_length=100)
    exam_type = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES, default="cet4")
    meaning = models.TextField(blank=True, default="")
    example_sentence = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "词汇"
        verbose_name_plural = "词汇"
        unique_together = ("word", "exam_type")

    def __str__(self) -> str:
        return self.word


class VocabularyNotebook(models.Model):
    """用户词汇本"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    exam_type = models.CharField(max_length=10, default="cet4")
    vocabularies = models.ManyToManyField(Vocabulary, related_name="notebooks", blank=True)

    class Meta:
        verbose_name = "词汇笔记本"
        verbose_name_plural = "词汇笔记本"

    def __str__(self) -> str:
        return self.name


class VocabularyLearningRecord(models.Model):
    """用户词汇学习记录，支持记忆曲线"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    vocabulary = models.ForeignKey(Vocabulary, on_delete=models.CASCADE)
    last_review_time = models.DateTimeField(auto_now=True)
    review_count = models.IntegerField(default=0)
    correct_count = models.IntegerField(default=0)

    class Meta:
        verbose_name = "词汇学习记录"
        verbose_name_plural = "词汇学习记录"
        unique_together = ("user", "vocabulary")


class MockExam(models.Model):
    """模拟考试记录"""

    EXAM_TYPE_CHOICES = (
        ("cet4", "四级"),
        ("cet6", "六级"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exam_type = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES, default="cet4")
    created_at = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField(auto_now_add=True)
    duration_minutes = models.IntegerField(default=120)
    questions = models.ManyToManyField(CETQuestion, related_name="mock_exams", blank=True)
    is_submitted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "模拟考试"
        verbose_name_plural = "模拟考试"


