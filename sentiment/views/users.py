from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token
from django.shortcuts import render, redirect

# Session Login API View
from django.shortcuts import redirect

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.views.decorators.csrf import ensure_csrf_cookie

# Login HTML page 
def login_page(request):
    return render(request, 'sentiment/login.html')

# Logout API View
class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)

# Django Template Registration View
def RegisterView(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # log the user in immediately after registration
            return redirect('upload_file')  # Redirect to upload after signup
    else:
        form = UserCreationForm()
    return render(request, 'sentiment/register.html', {'form': form})
