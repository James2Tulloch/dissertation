from django.urls import path
from .views.upload_views import upload_file, show_progress, task_status, kill_task
from .views.analysis_views import analysis_results
from .views.bot_views import check_accounts_view
from .views.users import RegisterView
from django.contrib.auth.views import LoginView, LogoutView 


urlpatterns = [
    # Data Views
    path('upload/', upload_file, name='upload_file'),
    path('progress/<str:task_id>/', show_progress, name='show_progress'),
    path('task-status/<str:task_id>/', task_status, name='task_status'),
    path('kill-task/<str:task_id>/', kill_task, name='kill_task'),
    path('results/', analysis_results, name='results'),
    path('check-accounts/', check_accounts_view, name='check_accounts'),

    # User Authentication Views

    path('login', LoginView.as_view(template_name='sentiment/login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='register'), name='logout'),
    path('', RegisterView, name='register'),
]