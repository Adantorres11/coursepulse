from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegisterSerializer
from .usernames import TAKEN_USERNAME_MESSAGE, display_username

User = get_user_model()


def account_data(user):
    profile = getattr(user, "profile", None)
    return {
        "id": user.id,
        "email": user.email,
        "username": display_username(user),
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
            username = serializer.validated_data.get("username", "")
            if User.objects.filter(username__iexact=username).exists():
                return Response(
                    {"username": [TAKEN_USERNAME_MESSAGE]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
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

        account = User.objects.filter(
            email__iexact=email.strip().lower()
        ).first()
        user = None
        if account is not None:
            user = authenticate(
                request=request,
                username=account.username,
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