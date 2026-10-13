from rest_framework import serializers

from .models import Classroom


class ClassroomSerializer(serializers.ModelSerializer):
    professor = serializers.SerializerMethodField()
    quiz_count = serializers.IntegerField(read_only=True)
    new_quiz_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Classroom
        fields = [
            "id",
            "name",
            "course_code",
            "professor",
            "quiz_count",
            "new_quiz_count",
        ]

    def get_professor(self, classroom):
        if classroom.professor is None:
            return None

        professor = classroom.professor
        return {
            "id": professor.id,
            "name": professor.get_full_name() or professor.username,
        }