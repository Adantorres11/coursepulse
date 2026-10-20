from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Lecture(models.Model):
    classroom = models.ForeignKey(
        "classrooms.Classroom",
        on_delete=models.CASCADE,
        related_name="lectures",
    )
    title = models.CharField(max_length=255)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-id"]

    def __str__(self):
        return self.title


class Question(models.Model):
    lecture = models.ForeignKey(
        Lecture,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    prompt = models.TextField()
    choices = models.JSONField()
    correct_index = models.PositiveSmallIntegerField()
    difficulty = models.CharField(
        max_length=6,
        choices=[
            ("easy", "Easy"),
            ("medium", "Medium"),
            ("hard", "Hard"),
        ],
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def clean(self):
        super().clean()

        if (
            not isinstance(self.choices, list)
            or len(self.choices) != 4
            or not all(isinstance(choice, str) for choice in self.choices)
        ):
            raise ValidationError({
                "choices": "Provide exactly four choices, all strings."
            })

        if self.correct_index not in (0, 1, 2, 3):
            raise ValidationError({
                "correct_index": "Choose an index from 0 to 3."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.prompt

class QuizCompletion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_completions",
    )
    lecture = models.ForeignKey(
        Lecture,
        on_delete=models.CASCADE,
        related_name="completions",
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lecture"],
                name="unique_user_lecture_completion",
            ),
        ]