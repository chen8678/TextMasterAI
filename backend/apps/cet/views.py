from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import CETQuestion, VocabularyNotebook, MockExam
from .serializers import CETQuestionSerializer, VocabularyNotebookSerializer
from .services import (
    CETPracticeService,
    CETVocabularyService,
    CETAnalysisService,
    CETWritingService,
    CETListeningService,
    CETExamService,
    CETTutorService,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def question_list(request):
    """按条件筛选题目列表（默认仅四级）"""
    from django.db.models import Q

    qs = CETQuestion.objects.filter(Q(exam__exam_type="cet4") | Q(exam__isnull=True))
    question_type = request.query_params.get("question_type")
    if question_type:
        qs = qs.filter(question_type=question_type)
    difficulty = request.query_params.get("difficulty")
    if difficulty is not None:
        try:
            qs = qs.filter(difficulty=int(difficulty))
        except (TypeError, ValueError):
            pass
    exam_id = request.query_params.get("exam_id")
    if exam_id:
        qs = qs.filter(exam_id=exam_id)
    limit = request.query_params.get("limit")
    try:
        limit_int = min(100, max(1, int(limit))) if limit is not None else 50
    except (TypeError, ValueError):
        limit_int = 50
    qs = qs[:limit_int]
    serializer = CETQuestionSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_practice(request):
    """生成专项练习题列表（默认四级）"""
    question_type = request.data.get("question_type")
    if not question_type:
        return Response({"error": "缺少 question_type"}, status=status.HTTP_400_BAD_REQUEST)
    difficulty = request.data.get("difficulty")
    try:
        difficulty_int = int(difficulty) if difficulty is not None else None
    except (TypeError, ValueError):
        difficulty_int = None
    count = request.data.get("count", 10)
    try:
        count_int = min(50, max(1, int(count)))
    except (TypeError, ValueError):
        count_int = 10

    service = CETPracticeService()
    questions = service.generate_practice(
        user=request.user,
        question_type=question_type,
        difficulty=difficulty_int,
        count=count_int,
        exam_type="cet4",
    )
    # 练习作答前不暴露正确答案与解析
    serializer = CETQuestionSerializer(questions, many=True)
    safe_questions = []
    for item in serializer.data:
        row = dict(item)
        row.pop("correct_answer", None)
        row.pop("explanation", None)
        safe_questions.append(row)
    weak_points = service.analyze_weak_points(request.user)
    return Response(
        {
            "questions": safe_questions,
            "weak_points": weak_points,
            "exam_type": "cet4",
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_practice(request):
    """提交专项练习答案"""
    answers = request.data.get("answers") or {}
    if not isinstance(answers, dict) or not answers:
        return Response(
            {"error": "answers 必须为非空 {question_id: answer}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    service = CETPracticeService()
    result = service.submit_practice(request.user, answers)
    return Response(result)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def weak_points(request):
    """返回当前用户的弱项分析结果"""
    service = CETPracticeService()
    data = service.analyze_weak_points(request.user)
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_vocabulary_notebook(request):
    """根据单词列表创建词汇本（固定四级）"""
    word_list = request.data.get("words") or []
    if not isinstance(word_list, list) or not word_list:
        return Response({"error": "请提供非空的 words 列表"}, status=status.HTTP_400_BAD_REQUEST)
    service = CETVocabularyService()
    notebook = service.create_vocabulary_notebook(
        user=request.user,
        word_list=word_list,
        exam_type="cet4",
    )
    serializer = VocabularyNotebookSerializer(notebook)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_core_vocabulary_notebook(request):
    """一键导入四级核心词本"""
    limit = request.data.get("limit", 100)
    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        limit_int = 100
    service = CETVocabularyService()
    try:
        notebook = service.import_core_notebook(request.user, limit=limit_int)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    serializer = VocabularyNotebookSerializer(notebook)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def record_vocabulary_review(request):
    """词汇复习打卡：remembered=true/false"""
    vocabulary_id = request.data.get("vocabulary_id")
    remembered = bool(request.data.get("remembered"))
    if not vocabulary_id:
        return Response({"error": "缺少 vocabulary_id"}, status=status.HTTP_400_BAD_REQUEST)
    service = CETVocabularyService()
    try:
        data = service.record_review(
            user=request.user,
            vocabulary_id=int(vocabulary_id),
            remembered=remembered,
        )
    except Exception:
        return Response({"error": "词汇不存在或记录失败"}, status=status.HTTP_400_BAD_REQUEST)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vocabulary_notebook_list(request):
    """获取当前用户的词汇本列表"""
    notebooks = VocabularyNotebook.objects.filter(user=request.user).prefetch_related("vocabularies")
    serializer = VocabularyNotebookSerializer(notebooks, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vocabulary_review_plan(request, notebook_id: int):
    """获取指定词汇本的复习计划"""
    notebook = get_object_or_404(
        VocabularyNotebook, id=notebook_id, user=request.user
    )
    service = CETVocabularyService()
    plan = service.generate_review_plan(request.user, notebook)
    return Response(plan)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ability_radar(request):
    """获取当前用户的能力雷达图数据（简版）"""
    service = CETAnalysisService()
    data = service.generate_ability_radar(request.user)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def learner_snapshot(request):
    """只读学习者状态汇总：今日任务 / 诊断依据 / 到期复习 / 雷达弱项。"""
    service = CETAnalysisService()
    data = service.build_learner_snapshot(request.user)
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def tutor_ask(request):
    """四级答疑：有限轮次，达上限后强制收束到弱项练习。"""
    message = request.data.get("message") or ""
    prior = request.data.get("prior_user_turns", 0)
    max_turns = request.data.get("max_turns")
    try:
        max_turns_int = int(max_turns) if max_turns is not None else CETTutorService.MAX_TURNS
    except (TypeError, ValueError):
        max_turns_int = CETTutorService.MAX_TURNS
    service = CETTutorService(max_turns=max_turns_int)
    result = service.respond(
        user=request.user,
        message=str(message),
        prior_user_turns=prior,
    )
    if result.get("error"):
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grade_writing(request):
    """写作/翻译批改接口"""
    question_id = request.data.get("question_id")
    content = (request.data.get("content") or "").strip()
    if not question_id or not content:
        return Response(
            {"error": "缺少 question_id 或 content"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    question = get_object_or_404(CETQuestion, id=question_id)
    model_name = request.data.get("model", "deepseek-chat")
    service = CETWritingService(model=model_name)
    result = service.grade_writing(question=question, content=content)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def process_listening_transcript(request):
    """听力文本处理：生成摘要、关键词和练习题草案"""
    transcript = (request.data.get("transcript") or "").strip()
    if not transcript:
        return Response(
            {"error": "缺少 transcript"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    model_name = request.data.get("model", "deepseek-chat")
    service = CETListeningService(model=model_name)
    result = service.process_transcript(transcript)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_mock_exam(request):
    """创建四级模拟考试"""
    service = CETExamService()
    mock_exam = service.create_mock_exam(user=request.user, exam_type="cet4")
    questions = mock_exam.questions.all()
    serializer = CETQuestionSerializer(questions, many=True)
    safe_questions = []
    for item in serializer.data:
        row = dict(item)
        row.pop("correct_answer", None)
        row.pop("explanation", None)
        safe_questions.append(row)
    if not safe_questions:
        return Response(
            {"error": "四级题库为空，请先执行 python manage.py seed_cet4"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {
            "mock_exam_id": mock_exam.id,
            "exam_type": "cet4",
            "questions": safe_questions,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_mock_exam(request, mock_exam_id: int):
    """提交模拟考试答案"""
    mock_exam = get_object_or_404(MockExam, id=mock_exam_id, user=request.user)
    answers = request.data.get("answers") or {}
    if not isinstance(answers, dict):
        return Response(
            {"error": "answers 必须为 {question_id: answer} 的对象"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    service = CETExamService()
    result = service.submit_exam(mock_exam, answers)
    return Response(result)

