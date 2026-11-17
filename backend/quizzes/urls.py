from classrooms.views import LectureUnpublishView
from django.urls import path

from . import views

urlpatterns = [
    path(
        "lectures/",
        views.LectureListView.as_view(),
        name="lecture-list",
    ),
    path(
        "lectures/<int:pk>/quiz/",
        views.LectureQuizView.as_view(),
        name="lecture-quiz",
    ),
    path(
        "lectures/<int:pk>/questions/<int:question_id>/start/",
        views.LectureQuestionStartView.as_view(),
        name="lecture-question-start",
    ),
    path(
        "lectures/<int:pk>/answers/",
        views.LectureAnswerView.as_view(),
        name="lecture-answers",
    ),
    path(
        "lectures/<int:pk>/status/",
        views.LectureStatusView.as_view(),
        name="lecture-status",
    ),
    path(
        "lectures/<int:pk>/retry/",
        views.LectureRetryView.as_view(),
        name="lecture-retry",
    ),
    path(
        "lectures/<int:pk>/unpublish/",
        LectureUnpublishView.as_view(),
        name="lecture-unpublish",
    ),
    path(
        "lectures/<int:pk>/questions/",
        views.ProfessorLectureQuestionsView.as_view(),
        name="professor-lecture-questions",
    ),
    path(
        "lectures/<int:pk>/questions/<int:question_id>/",
        views.ProfessorQuestionDetailView.as_view(),
        name="professor-question-detail",
    ),
    path(
        "lectures/<int:pk>/publish/",
        views.LecturePublishView.as_view(),
        name="lecture-publish",
    ),
]
