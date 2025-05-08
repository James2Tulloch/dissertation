import csv
import io
import base64
import pandas as pd
import os
import matplotlib.pyplot as plt
from celery.result import AsyncResult
from sentiment.tasks import run_sentiment_analysis
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.contrib import messages
from sentiment.forms import UploadFileForm
from django.contrib.auth.decorators import login_required

# Data upload and processing views
@login_required(login_url='/login/')
def upload_file(request):
    """
    Handles CSV uploads and starts a Celery task for sentiment analysis.
    """
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['file']
            if not csv_file.name.endswith('.csv'):
                return render(request, 'sentiment/upload.html', {
                    'form': form,
                    'error': 'Please upload a CSV file.'
                })

            file_data = csv_file.read().decode('utf-8', errors='ignore')
            row_count = file_data.count('\n')

            task = run_sentiment_analysis.delay(file_data, row_count)
            return redirect('show_progress', task_id=task.id)
    else:
        form = UploadFileForm()
    return render(request, 'sentiment/upload.html', {'form': form})

@login_required(login_url='/login/')
def show_progress(request, task_id):
    """
    Displays a progress bar for the ongoing Celery task.
    """
    return render(request, 'sentiment/progress.html', {'task_id': task_id})

@login_required(login_url='/login/')
def task_status(request, task_id):
    """
    Returns JSON with the Celery task status (used by AJAX polling).
    """
    result = AsyncResult(task_id)

    if result.state == 'PENDING':
        response = {
            'state': 'PENDING',
            'progress': 0,
            'eta': '',
            'status': 'Starting...'
        }
    elif result.state != 'FAILURE':
        meta = result.info or {}
        current = meta.get('current', 0)
        total = meta.get('total', 1)
        progress_percent = int((current / total) * 100)
        response = {
            'state': result.state,
            'progress': progress_percent,
            'current': current,
            'total': total,
            'eta': meta.get('eta', ''),
            'status': meta.get('status', '')
        }
    else:
        response = {
            'state': 'FAILURE',
            'progress': 100,
            'eta': '',
            'status': str(result.info)
        }

    return JsonResponse(response)
@login_required(login_url='/login/')
def kill_task(request, task_id):
    """
    Terminates the Celery task.
    """
    result = AsyncResult(task_id)
    result.revoke(terminate=True)
    return redirect('upload_file')



