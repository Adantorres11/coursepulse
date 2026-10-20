from django.contrib import admin

from .models import Answer, Attempt


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "lecture",
        "started_at",
        "completed_at",
        "total_points",
    )
    list_filter = ("lecture",)
    list_select_related = ("user", "lecture")


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "attempt",
        "question",
        "chosen_index",
        "is_correct",
        "time_taken_ms",
        "points_awarded",
    )
    list_filter = ("is_correct",)
    list_select_related = ("attempt", "question")