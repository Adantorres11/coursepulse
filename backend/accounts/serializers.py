from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Profile
from .usernames import (
    BLANK_USERNAME_MESSAGE,
    INVALID_USERNAME_MESSAGE,
    TAKEN_USERNAME_MESSAGE,
    USERNAME_PATTERN,
)

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=150)
    username = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
        allow_blank=False,
        error_messages={
            "blank": BLANK_USERNAME_MESSAGE,
            "required": BLANK_USERNAME_MESSAGE,
        },
    )
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=8,
    )
    role = serializers.ChoiceField(choices=Profile.Role.choices)

    def validate_email(self, value):
        email = value.strip().lower()

        if (
            User.objects.filter(email__iexact=email).exists()
            or User.objects.filter(username__iexact=email).exists()
        ):
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return email

    def validate_username(self, value):
        username = value.strip()

        if not username:
            raise serializers.ValidationError(BLANK_USERNAME_MESSAGE)

        if USERNAME_PATTERN.fullmatch(username) is None:
            raise serializers.ValidationError(INVALID_USERNAME_MESSAGE)

        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError(TAKEN_USERNAME_MESSAGE)

        return username

    def validate(self, attrs):
        user = User(
            username=attrs["username"],
            email=attrs["email"],
        )

        try:
            validate_password(attrs["password"], user=user)
        except ValidationError as error:
            raise serializers.ValidationError(
                {"password": error.messages}
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )

        Profile.objects.create(
            user=user,
            role=validated_data["role"],
        )

        return user
