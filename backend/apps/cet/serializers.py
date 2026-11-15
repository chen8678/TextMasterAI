from rest_framework import serializers

from .models import CETExam, CETQuestion, Vocabulary, VocabularyNotebook


class CETExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = CETExam
        fields = ["id", "exam_type", "exam_date", "year", "is_official", "title"]


class CETQuestionSerializer(serializers.ModelSerializer):
    knowledge_points = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = CETQuestion
        fields = [
            "id",
            "exam",
            "question_type",
            "question_number",
            "content",
            "options",
            "correct_answer",
            "explanation",
            "knowledge_points",
            "difficulty",
        ]


class VocabularySerializer(serializers.ModelSerializer):
    class Meta:
        model = Vocabulary
        fields = ["id", "word", "exam_type", "meaning", "example_sentence"]


class VocabularyNotebookSerializer(serializers.ModelSerializer):
    vocabularies = VocabularySerializer(many=True, read_only=True)

    class Meta:
        model = VocabularyNotebook
        fields = ["id", "name", "exam_type", "vocabularies"]

