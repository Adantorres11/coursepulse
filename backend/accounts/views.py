from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegisterSerializer


def account_data(user):
    profile = getattr(user, "profile", None)
    return {
        "id": user.id,
        "email": user.email,
        "role": profile.role if profile else None,
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                user = serializer.save()
                token = Token.objects.create(user=user)
        except IntegrityError:
            return Response(
                {"email": ["An account with this email already exists."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "token": token.key,
                "user": account_data(user),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not isinstance(email, str) or not isinstance(password, str):
            return Response(
                {"detail": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(
            request=request,
            username=email.strip().lower(),
            password=password,
        )

        if user is None:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "user": account_data(user),
            }
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(account_data(request.user))