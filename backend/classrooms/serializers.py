from pathlib import Path

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
            ".mp3", ".mp4", ".m4a", ".wav"
        }

        extension = Path(file.name).suffix.lower()

        if extension not in allowed_extensions:
            raise serializers.ValidationError(
                "Only MP3, MP4, M4A, and WAV files are allowed."
            )

        allowed_types = {
            ".mp3": {"audio/mpeg", "audio/mp3"},
            ".mp4": {"video/mp4", "audio/mp4"},
            ".m4a": {"audio/mp4", "audio/x-m4a"},
            ".wav": {"audio/wav", "audio/x-wav", "audio/wave"},
        }

        content_type = getattr(file, "content_type", "")

        if content_type not in allowed_types[extension]:
            raise serializers.ValidationError(
                "Invalid recording content type."
            )

        max_size = 100 * 1024 * 1024

        if file.size > max_size:
            raise serializers.ValidationError(
                "File must be 100 MB or smaller."
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

        elif extension == ".wav":
            valid_signature = (
                header.startswith(b"RIFF")
                and header[8:12] == b"WAVE"
            )

        elif extension in {".mp4", ".m4a"}:
            valid_signature = header[4:8] == b"ftyp"

        if not valid_signature:
            raise serializers.ValidationError(
                "Invalid audio or video file."
            )

        return file