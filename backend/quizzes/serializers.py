from rest_framework import serializers

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

    class Meta:
        model = Lecture
        fields = ["lecture_id", "title", "questions"]
