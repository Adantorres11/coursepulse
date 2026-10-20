from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quizzes.models import QuizCompletion

from .models import Classroom, Enrollment
from .serializers import ClassCodeSerializer, ClassroomSerializer


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


class ClassCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def get_classroom(self, request, data):
        profile = getattr(request.user, "profile", None)

        if profile is None or profile.role != "student":
            raise PermissionDenied(
                "Only students can look up or join classes."
            )

        serializer = ClassCodeSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        classroom = (
            Classroom.objects
            .select_related("professor")
            .filter(
                access_code__iexact=serializer.validated_data["code"]
            )
            .first()
        )

        if classroom is None:
            raise NotFound(
                "We couldn't find a class with that code"
            )

        return classroom

    def class_data(self, classroom, user):
        available = classroom.lectures.filter(
            published_at__lte=timezone.now(),
            questions__isnull=False,
        ).distinct()

        completed = QuizCompletion.objects.filter(
            user=user,
        ).values_list("lecture_id", flat=True)

        classroom.quiz_count = available.count()
        classroom.new_quiz_count = available.exclude(
            id__in=completed,
        ).count()

        return ClassroomSerializer(classroom).data


class ClassLookupView(ClassCodeView):
    def get(self, request):
        classroom = self.get_classroom(
            request,
            request.query_params,
        )

        return Response(
            self.class_data(classroom, request.user)
        )


class ClassJoinView(ClassCodeView):
    def post(self, request):
        classroom = self.get_classroom(
            request,
            request.data,
        )

        enrollment, created = Enrollment.objects.get_or_create(
            user=request.user,
            classroom=classroom,
        )

        return Response(
            self.class_data(classroom, request.user),
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )