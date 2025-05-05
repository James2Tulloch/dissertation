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

@login_required(login_url='/login/')
def results(request):
    csv_path = os.path.join(settings.BASE_DIR, "precomputed_results.csv")
    df = pd.read_csv(csv_path)

    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df.dropna(subset=['date'], inplace=True)

    # Detect which column holds sentiment
    if 'Sentiment' in df.columns:
        df['sentiment_score'] = df['Sentiment'].map({'POSITIVE': 1, 'NEGATIVE': 0})
    elif 'sentiment' in df.columns:
        df['sentiment_score'] = df['sentiment'].map({'POSITIVE': 1, 'NEGATIVE': 0})
    elif 'Score' in df.columns:
        df.rename(columns={'Score': 'sentiment_score'}, inplace=True)
    else:
        raise ValueError("No recognized sentiment column found!")

    df.dropna(subset=['sentiment_score'], inplace=True)

    # Group by date (day)
    daily_sentiment = (
        df.groupby(df['date'].dt.date)['sentiment_score']
          .mean()
          .reset_index(name='avg_sentiment')
    )
    daily_sentiment = daily_sentiment.sort_values('date')
    daily_sentiment['rolling_avg'] = daily_sentiment['avg_sentiment'].rolling(window=7).mean()

    # Detect large day-to-day changes
    daily_sentiment['day_diff'] = daily_sentiment['avg_sentiment'].diff()
    threshold = 0.15
    big_shifts = daily_sentiment[abs(daily_sentiment['day_diff']) >= threshold]

    fig = go.Figure()

    # Daily average line
    fig.add_trace(go.Scatter(
        x=daily_sentiment['date'],
        y=daily_sentiment['avg_sentiment'],
        mode='lines+markers',
        name='Daily Avg'
    ))

    # Rolling average line
    fig.add_trace(go.Scatter(
        x=daily_sentiment['date'],
        y=daily_sentiment['rolling_avg'],
        mode='lines',
        name='7-Day Rolling'
    ))

    # Annotations for large shifts
    for _, row in big_shifts.iterrows():
        fig.add_annotation(
            x=row['date'],
            y=row['avg_sentiment'],
            text=f"Δ={row['day_diff']:.2f}",
            showarrow=True,
            arrowhead=2,
            ax=20,
            ay=-30,
        )

    fig.update_layout(
        title='Sentiment Over Time (Daily & Rolling Avg)',
        xaxis_title='Date',
        yaxis_title='Average Sentiment',
        template='plotly_white'
    )
    chart_html = fig.to_html(full_html=False)

    # Second figure with OLS trend line
    daily_sentiment['date_ordinal'] = daily_sentiment['date'].apply(lambda d: d.toordinal())
    trend_fig = px.scatter(
        daily_sentiment,
        x='date_ordinal',
        y='avg_sentiment',
        title='Sentiment Over Time (OLS Trend)',
        trendline='ols',
        trendline_color_override='green'
    )
    step = 30
    sampled = daily_sentiment.iloc[::step]
    trend_fig.update_xaxes(
        tickmode='array',
        tickvals=sampled['date_ordinal'],
        ticktext=sampled['date'].astype(str)
    )
    trend_fig.update_layout(
        xaxis_title='Date',
        yaxis_title='Avg Sentiment'
    )
    trend_chart_html = trend_fig.to_html(full_html=False)

    return render(request, 'sentiment/results.html', {
        'chart_html': chart_html,
        'trend_chart_html': trend_chart_html
    })

@login_required(login_url='/login/')
def check_accounts_view(request):
    """
    Reads a CSV of Twitter usernames, calls Botometer for each, and displays the results.
    """
    if request.method == 'POST':
        csv_file = request.FILES.get('file', None)
        if not csv_file or not csv_file.name.endswith('.csv'):
            messages.error(request, "Please upload a valid CSV file.")
            return redirect('check_accounts')

        df = pd.read_csv(csv_file)
        if 'user_name' not in df.columns:
            messages.error(request, "No 'user_name' column found in CSV.")
            return redirect('check_accounts')

        screen_names = df['user_name'].astype(str).tolist()
        rapidapi_key = getattr(settings, 'RAPIDAPI_KEY', None)
        if not rapidapi_key:
            messages.error(request, "Missing RAPIDAPI_KEY in Django settings.")
            return redirect('check_accounts')

        results = bulk_check_bot_accounts(screen_names, rapidapi_key)
        results_df = pd.DataFrame(results)

        def parse_score(row):
            data = row['botometer_result']
            if isinstance(data, dict) and 'scores' in data:
                return data['scores'].get('universal', None)
            return None

        results_df['bot_score'] = results_df.apply(parse_score, axis=1)
        table_html = results_df[['screen_name', 'bot_score']].to_html(index=False)
        return render(request, 'sentiment/bot_check_results.html', {'table': table_html})

    return render(request, 'sentiment/check_accounts.html')

