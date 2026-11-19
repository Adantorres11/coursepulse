from rest_framework import serializers

from .grading import get_open_attempt
from .models import Lecture, Question
from .parts import part_sizes

class LectureSerializer(serializers.ModelSerializer):
    classroom = serializers.CharField(
        source="classroom.name",
        read_only=True,
    )
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
        fields = ["id", "prompt", "choices", "difficulty"]


def normalize_choices(value):
    if (
        not isinstance(value, list)
        or len(value) != 4
        or not all(isinstance(choice, str) for choice in value)
    ):
        raise serializers.ValidationError(
            "Provide exactly four choices, all strings."
        )

    stripped = [choice.strip() for choice in value]
    if any(choice == "" for choice in stripped):
        raise serializers.ValidationError("Choices cannot be blank.")

    folded = [choice.casefold() for choice in stripped]
    if len(set(folded)) != 4:
        raise serializers.ValidationError("Choices must be unique.")

    return stripped


def question_is_publishable(question):
    if question.correct_index not in (0, 1, 2, 3):
        return False
    if question.difficulty not in ("easy", "medium", "hard"):
        return False
    try:
        normalize_choices(question.choices)
    except serializers.ValidationError:
        return False
    return True


class ProfessorQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "id",
            "prompt",
            "choices",
            "correct_index",
            "difficulty",
            "position",
        ]
        read_only_fields = ["id", "position"]

    def validate_choices(self, value):
        return normalize_choices(value)

    def validate_correct_index(self, value):
        if value not in (0, 1, 2, 3):
            raise serializers.ValidationError(
                "Correct answer index must be between 0 and 3."
            )
        return value

    def create(self, validated_data):
        lecture = validated_data["lecture"]
        last_position = (
            Question.objects.filter(lecture=lecture)
            .order_by("-position")
            .values_list("position", flat=True)
            .first()
        )
        # Question generation numbers from 0. A hand-written question continues that.
        validated_data["position"] = 0 if last_position is None else last_position + 1
        # Null generation marks a professor-written question. Regeneration keeps it.
        validated_data["generation"] = None
        return super().create(validated_data)


class QuizSerializer(serializers.ModelSerializer):
    lecture_id = serializers.IntegerField(source="id", read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)
    answered_question_ids = serializers.SerializerMethodField()
    total_points = serializers.SerializerMethodField()
    part = serializers.SerializerMethodField()
    part_count = serializers.SerializerMethodField()

    class Meta:
        model = Lecture
        fields = [
            "lecture_id",
            "title",
            "questions",
            "answered_question_ids",
            "total_points",
            "part",
            "part_count",
        ]

    def get_part(self, lecture):
        return None

    def get_part_count(self, lecture):
        return len(part_sizes(len(lecture.questions.all())))

    def _open_attempt(self, lecture):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return None
        return get_open_attempt(request.user, lecture)

    def to_representation(self, lecture):
        self._attempt = self._open_attempt(lecture)
        return super().to_representation(lecture)

    def get_answered_question_ids(self, lecture):
        if self._attempt is None:
            return []
        return list(self._attempt.answers.values_list("question_id", flat=True))

    def get_total_points(self, lecture):
        return self._attempt.total_points if self._attempt else 0

class AnswerRequestSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    chosen_index = serializers.IntegerField(
        min_value=0,
        max_value=3,
        allow_null=True,
    )
    # 1-based part. Omit it to play a one-part lecture in the original order.
    part = serializers.IntegerField(required=False, min_value=1)
