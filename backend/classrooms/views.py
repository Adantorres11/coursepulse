from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from quizzes.models import QuizCompletion

from .models import Classroom
from .serializers import ClassroomSerializer


class StudentClassListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ClassroomSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)

        if profile is None or profile.role != "student":
            raise PermissionDenied(
                "Only students can access this class list."
            )

        completed_lectures = QuizCompletion.objects.filter(
            user=user,
        ).values_list("lecture_id", flat=True)

        available_quizzes = Q(
            lectures__published_at__lte=timezone.now(),
            lectures__questions__isnull=False,
        )

        return (
            Classroom.objects
            .filter(enrollments__user=user)
            .select_related("professor")
            .annotate(
                quiz_count=Count(
                    "lectures",
                    filter=available_quizzes,
                    distinct=True,
                ),
                new_quiz_count=Count(
                    "lectures",
                    filter=(
                        available_quizzes
                        & ~Q(lectures__id__in=completed_lectures)
                    ),
                    distinct=True,
                ),
            )
            .order_by("name", "id")
        )