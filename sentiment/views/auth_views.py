from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token
from rest_framework import serializers
from .serializers import RegisterSerializer
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login


class SessionLoginView(APIView):
    permission_classes = [AllowAny]

    @ensure_csrf_cookie
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('upload_file')
        return Response({"error": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)

