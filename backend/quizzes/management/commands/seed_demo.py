from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from classrooms.models import Classroom
from quizzes.models import Lecture, Question


DEMO_QUESTIONS = [
    {
        "prompt": "In Scrum, what is a Sprint?",
        "choices": [
            "A fixed-length period of work lasting one month or less",
            "A meeting held once per year",
            "A list of Git branches",
            "The final release of a project",
        ],
        "correct_index": 0,
        "difficulty": "easy",
    },
    {
        "prompt": "Which Git command shows your current branch and file changes?",
        "choices": [
            "git push",
            "git status",
            "git clone",
            "git merge",
        ],
        "correct_index": 1,
        "difficulty": "easy",
    },
    {
        "prompt": "What is the main purpose of a Scrum Sprint Retrospective?",
        "choices": [
            "Assign a final grade to the team",
            "Publish every unfinished feature",
            "Inspect how the team worked and plan improvements",
            "Replace the Product Backlog",
        ],
        "correct_index": 2,
        "difficulty": "medium",
    },
    {
        "prompt": "You committed locally. What does pushing your branch do?",
        "choices": [
            "Deletes your local commits",
            "Automatically merges your branch into main",
            "Installs your project's dependencies",
            "Sends your branch's commits to the remote repository",
        ],
        "correct_index": 3,
        "difficulty": "medium",
    },
    {
        "prompt": (
            "Git reports a merge conflict because two branches changed "
            "the same lines. What should you do?"
        ),
        "choices": [
            "Resolve the conflicting content, stage it, and complete the merge",
            "Delete the entire repository",
            "Run git push repeatedly until the conflict disappears",
            "Always discard the other branch's changes",
        ],
        "correct_index": 0,
        "difficulty": "hard",
    },
]


class Command(BaseCommand):
    help = "Create or update a demo classroom, lecture, and five questions."

    @transaction.atomic
    def handle(self, *args, **options):
        classroom, _ = Classroom.objects.update_or_create(
            name="CS 3398 Software Engineering",
            defaults={
                "course_code": "CS 3398",
                "access_code": "DEMO01",
            },
        )

        lecture, _ = Lecture.objects.get_or_create(
            classroom=classroom,
            title="Demo Lecture: Scrum and Git",
            defaults={"published_at": timezone.now()},
        )

        if lecture.published_at is None:
            lecture.published_at = timezone.now()
            lecture.save(update_fields=["published_at"])

        for position, question_data in enumerate(DEMO_QUESTIONS, start=1):
            Question.objects.update_or_create(
                lecture=lecture,
                position=position,
                defaults=question_data,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo quiz ready: lecture {lecture.pk}, "
                f"five questions. Class code: {classroom.access_code}"
            )
        )