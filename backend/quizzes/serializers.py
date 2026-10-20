from rest_framework import serializers

from .models import Lecture


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
