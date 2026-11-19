from pathlib import Path

from django.conf import settings
from rest_framework import serializers

from .models import Classroom, Enrollment
from .people import dedicated_username, person_display_name

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
            "name": person_display_name(professor),
        }


class ClassCodeSerializer(serializers.Serializer):
    code = serializers.CharField(
        max_length=6,
        min_length=6,
        trim_whitespace=True,
    )

    def validate_code(self, value):
        code = value.upper()

        if any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            for character in code
        ):
            raise serializers.ValidationError(
                "Enter a 6-character code using letters and numbers."
            )

        return code

class LectureUploadSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    recording = serializers.FileField()

    def validate_recording(self, file):
        allowed_extensions = {
            ".mp3", ".mp4", ".m4a", ".wav", ".mov", ".mkv",
            ".webm", ".avi", ".ogg", ".flac", ".aac",
        }

        extension = Path(file.name).suffix.lower()

        if extension not in allowed_extensions:
            raise serializers.ValidationError(
                "Only MP3, MP4, M4A, WAV, MOV, MKV, WEBM, AVI, "
                "OGG, FLAC, and AAC files are allowed."
            )

        max_size = settings.LECTURE_UPLOAD_MAX_BYTES

        if file.size > max_size:
            raise serializers.ValidationError(
                f"File must be {max_size // (1024 * 1024)} MB or smaller."
            )

        header = file.read(12)
        file.seek(0)

        valid_signature = False

        if extension == ".mp3":
            valid_signature = (
                header.startswith(b"ID3")
                or (
                    len(header) >= 2
                    and header[0] == 0xFF
                    and header[1] & 0xE0 == 0xE0
                )
            )

        elif extension == ".aac":
            valid_signature = (
                header.startswith(b"ID3")
                or (
                    len(header) >= 2
                    and header[0] == 0xFF
                    and header[1] & 0xF6 == 0xF0
                )
            )

        elif extension == ".wav":
            valid_signature = (
                header.startswith(b"RIFF")
                and header[8:12] == b"WAVE"
            )

        elif extension == ".avi":
            valid_signature = (
                header.startswith(b"RIFF")
                and header[8:12] == b"AVI "
            )

        elif extension == ".ogg":
            valid_signature = header.startswith(b"OggS")

        elif extension == ".flac":
            valid_signature = (
                header.startswith(b"fLaC")
                or header.startswith(b"ID3")
            )

        elif extension in {".mkv", ".webm"}:
            valid_signature = header.startswith(b"\x1aE\xdf\xa3")

        elif extension in {".mp4", ".m4a", ".mov"}:
            valid_signature = header[4:8] in {
                b"ftyp", b"moov", b"mdat",
                b"wide", b"free", b"skip",
            }

        if not valid_signature:
            raise serializers.ValidationError(
                "Invalid audio or video file."
            )

        return file

class ClassCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = ["id", "name", "access_code"]
        read_only_fields = ["id", "access_code"]


class ProfessorClassSerializer(serializers.ModelSerializer):
    student_count = serializers.IntegerField(read_only=True)
    lecture_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Classroom
        fields = [
            "id",
            "name",
            "access_code",
            "student_count",
            "lecture_count",
        ]

class ClassRosterSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = ["name", "username", "joined_at"]

    def get_name(self, enrollment):
        return person_display_name(enrollment.user)

    def get_username(self, enrollment):
        return dedicated_username(enrollment.user)
