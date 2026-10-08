from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Profile

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=150)
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

    def validate(self, attrs):
        user = User(
            username=attrs["email"],
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
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
        )

        Profile.objects.create(
            user=user,
            role=validated_data["role"],
        )

        return user