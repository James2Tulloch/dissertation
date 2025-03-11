from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_file, name='upload_file'),
    path('progress/<str:task_id>/', views.show_progress, name='show_progress'),
    path('task-status/<str:task_id>/', views.task_status, name='task_status'),
    path('kill-task/<str:task_id>/', views.kill_task, name='kill_task'),
    path('precomputed-results/', views.precomputed_results, name='precomputed_results'),
    path('results/', views.results, name='results'),
    path('check-accounts/', views.check_accounts_view, name='check_accounts'),



]


