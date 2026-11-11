from rest_framework import serializers

from .grading import get_open_attempt
from .models import Lecture, Question


class LectureSerializer(serializers.ModelSerializer):
    classroom = serializers.CharField(source="classroom.name", read_only=True)
    question_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Lecture
        fields = [
            "id",
            "title",
            "classroom_id",
            "classroom",
            "published_at",
            "question_count",
        ]


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["id", "prompt", "choices", "correct_index", "difficulty"]


class QuizSerializer(serializers.ModelSerializer):
    lecture_id = serializers.IntegerField(source="id", read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)
    answered_question_ids = serializers.SerializerMethodField()
    total_points = serializers.SerializerMethodField()

    class Meta:
        model = Lecture
        fields = [
            "lecture_id",
            "title",
            "questions",
            "answered_question_ids",
            "total_points",
        ]

    def _open_attempt(self, lecture):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return None
        return get_open_attempt(request.user, lecture)

    def get_answered_question_ids(self, lecture):
        attempt = self._open_attempt(lecture)
        if attempt is None:
            return []
        return list(attempt.answers.values_list("question_id", flat=True))

    def get_total_points(self, lecture):
        attempt = self._open_attempt(lecture)
        return attempt.total_points if attempt else 0


class AnswerRequestSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    chosen_index = serializers.IntegerField(min_value=0, max_value=3)
    time_taken_ms = serializers.IntegerField(min_value=0)
