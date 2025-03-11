import csv
import io
import base64

# Django & Celery imports
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.conf import settings
from django.http import HttpResponse
from django.contrib import messages

from celery.result import AsyncResult

# For charts
import matplotlib
matplotlib.use("Agg")  # Use a non-GUI backend for matplotlib
import matplotlib.pyplot as plt

import pandas as pd
from wordcloud import WordCloud

#plotly implementation 
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import plot


# Local imports
from .forms import UploadFileForm
from .tasks import run_sentiment_analysis

#Botomer Imports
from .bot_utils import bulk_check_bot_accounts

#File uplaod and task

def upload_file(request):
    #CSV, Celery task and redirect.
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['file']
            if not csv_file.name.endswith('.csv'):
                return render(request, 'sentiment/upload.html', {
                    'form': form,
                    'error': 'Please upload a CSV file.'
                })

            # Read the file into memory
            file_data = csv_file.read().decode('utf-8', errors='ignore')

            # Optionally, count the rows for a basic progress calculation
            row_count = file_data.count('\n')  # naive approach

            # Start the Celery task
            task = run_sentiment_analysis.delay(file_data, row_count)

            # Redirect to a page that shows the progress bar
            return redirect('show_progress', task_id=task.id)
    else:
        form = UploadFileForm()
    return render(request, 'sentiment/upload.html', {'form': form})


def show_progress(request, task_id):
   #Progress bar
    return render(request, 'sentiment/progress.html', {'task_id': task_id})


def task_status(request, task_id):
    #Complicated AJAX Situation. 
    result = AsyncResult(task_id)

    if result.state == 'PENDING':
        # The task hasn't started or doesn't exist
        response = {
            'state': 'PENDING',
            'progress': 0,
            'eta': '',
            'status': 'Starting...'
        }
    elif result.state != 'FAILURE':
        # The task is either PROGRESS or SUCCESS
        meta = result.info or {}
        current = meta.get('current', 0)
        total = meta.get('total', 1)

        # Calculate percentage
        progress_percent = int((current / total) * 100)

        response = {
            'state': result.state,    # e.g. "PROGRESS" or "SUCCESS"
            'progress': progress_percent,
            'current': current,
            'total': total,
            'eta': meta.get('eta', ''),
            'status': meta.get('status', '')
        }
    else:
        # The task failed
        response = {
            'state': 'FAILURE',
            'progress': 100,
            'eta': '',
            'status': str(result.info)
        }

    return JsonResponse(response)


def kill_task(request, task_id):
    #Kill the task
    result = AsyncResult(task_id)
    # Revoke/terminate the Celery task
    result.revoke(terminate=True)
    # Redirect home (adjust 'upload_file' if that’s your home page)
    return redirect('upload_file')


#placeholder precomputed results

# Existing helpers
def precomputed_results(request):
    """
    Loads a pre-analyzed CSV (precomputed_results.csv) that includes Sentiment,
    Score, text, and date columns, then displays charts including 'Sentiment Over Time'.
    """

    # 1. Path to your precomputed CSV
    csv_path = str(settings.BASE_DIR / "precomputed_results.csv")
    df = pd.read_csv(csv_path)

    # 2. Generate visuals
    bar_chart_b64 = create_bar_chart(df)
    hist_chart_b64 = create_histogram(df)
    pos_wc_b64, neg_wc_b64 = create_wordclouds(df)

    # 3. Create the 'Sentiment Over Time' plot
    sentiment_over_time_b64 = create_sentiment_trends_plot(csv_path)

    # 4. Show a snippet of the data (first 50 rows)
    table_html = df.head(50).to_html(index=False)

    # 5. Pass everything into the template context
    context = {
        "table_data": table_html,
        "bar_chart": bar_chart_b64,
        "hist_chart": hist_chart_b64,
        "positive_wordcloud": pos_wc_b64,
        "negative_wordcloud": neg_wc_b64,
        "sentiment_over_time": sentiment_over_time_b64,  # New line chart
    }

    return render(request, "sentiment/results.html", context)

# your_app/views.py
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from django.conf import settings
from django.shortcuts import render
import os

import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from django.conf import settings
from django.shortcuts import render

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from django.conf import settings
from django.shortcuts import render

def results(request):
    """
    Reads 'precomputed_results.csv', computes daily average sentiment and a 7-day rolling
    average, highlights large day-to-day changes, and plots both a line chart and 
    an OLS trend line chart in Plotly. Uses 'date_ordinal' for OLS regression.
    """

    # 1) Read CSV
    csv_path = os.path.join(settings.BASE_DIR, "precomputed_results.csv")
    df = pd.read_csv(csv_path)

    # 2) Parse date
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df.dropna(subset=['date'], inplace=True)

    # 3) Check which column we have for sentiment
    if 'Sentiment' in df.columns:
        # If it's POSITIVE/NEGATIVE
        df['sentiment_score'] = df['Sentiment'].map({
            'POSITIVE': 1,
            'NEGATIVE': 0
        })
    elif 'sentiment' in df.columns:
        # If it's POSITIVE/NEGATIVE
        df['sentiment_score'] = df['sentiment'].map({
            'POSITIVE': 1,
            'NEGATIVE': 0
        })
    elif 'Score' in df.columns:
        # If it's numeric
        df.rename(columns={'Score': 'sentiment_score'}, inplace=True)
    else:
        raise ValueError("No recognized sentiment column found!")

    # Drop rows that didn't map properly
    df.dropna(subset=['sentiment_score'], inplace=True)

    # --------------------------------------------------------------------------
    # 4. Group by day, compute daily average
    # --------------------------------------------------------------------------
    daily_sentiment = (
        df.groupby(df['date'].dt.date)['sentiment_score']
          .mean()
          .reset_index(name='avg_sentiment')
    )

    # Sort by date in ascending order (just in case)
    daily_sentiment = daily_sentiment.sort_values('date')

    # --------------------------------------------------------------------------
    # 5. Rolling average (7-day). Larger window = smoother line.
    # --------------------------------------------------------------------------
    daily_sentiment['rolling_avg'] = daily_sentiment['avg_sentiment'].rolling(window=7).mean()

    # --------------------------------------------------------------------------
    # 6. Detect large changes (day-to-day difference) for annotation
    # --------------------------------------------------------------------------
    daily_sentiment['day_diff'] = daily_sentiment['avg_sentiment'].diff()

    # Suppose a "large shift" is > 0.15 or < -0.15 (tweak as needed)
    threshold = 0.15
    big_shifts = daily_sentiment[abs(daily_sentiment['day_diff']) >= threshold]

    # --------------------------------------------------------------------------
    # 7. Plot the daily average + rolling average with Plotly
    # --------------------------------------------------------------------------
    fig = go.Figure()

    # Daily average line
    fig.add_trace(go.Scatter(
        x=daily_sentiment['date'],
        y=daily_sentiment['avg_sentiment'],
        mode='lines+markers',
        name='Daily Avg',
        line=dict(color='blue')
    ))

    # Rolling average line
    fig.add_trace(go.Scatter(
        x=daily_sentiment['date'],
        y=daily_sentiment['rolling_avg'],
        mode='lines',
        name='7-Day Rolling',
        line=dict(color='red', width=3)
    ))

    # Add annotations for big shifts
    for idx, row in big_shifts.iterrows():
        fig.add_annotation(
            x=row['date'],
            y=row['avg_sentiment'],
            text=f"Δ={row['day_diff']:.2f}",
            showarrow=True,
            arrowhead=2,
            ax=20,
            ay=-30,
            font=dict(color="darkred", size=12, family="Arial")
        )

    fig.update_layout(
        title='Sentiment Over Time (Daily & Rolling Avg)',
        xaxis_title='Date',
        yaxis_title='Average Sentiment',
        template='plotly_white'
    )

    # Convert to HTML snippet
    chart_html = fig.to_html(full_html=False)

    # --------------------------------------------------------------------------
    # 8. Create a second figure with an OLS trend line on numeric x
    #    We'll convert our 'date' (which is a datetime.date) to ordinal integers
    # --------------------------------------------------------------------------
    daily_sentiment['date_ordinal'] = daily_sentiment['date'].apply(lambda d: d.toordinal())

    trend_fig = px.scatter(
        daily_sentiment,
        x='date_ordinal',      # numeric ordinal
        y='avg_sentiment',
        title='Sentiment Over Time (OLS Trend)',
        trendline='ols',
        trendline_color_override='green'
    )

    # We want to show date labels, not raw integers. We'll sample every ~30 rows:
    step = 30
    sampled = daily_sentiment.iloc[::step]  # every 30th row
    trend_fig.update_xaxes(
        tickmode='array',
        tickvals=sampled['date_ordinal'],
        ticktext=sampled['date'].astype(str)  # e.g. "2025-02-19"
    )

    trend_fig.update_layout(
        xaxis_title='Date',
        yaxis_title='Avg Sentiment'
    )

    trend_chart_html = trend_fig.to_html(full_html=False)

    # --------------------------------------------------------------------------
    # 9. Render both charts in the template
    # --------------------------------------------------------------------------
    return render(request, 'sentiment/results.html', {
        'chart_html': chart_html,
        'trend_chart_html': trend_chart_html
    })

    """
    Reads 'precomputed_results.csv', computes daily average sentiment and a 7-day rolling
    average, highlights large day-to-day changes, and plots both a line chart and an OLS
    trend line chart in Plotly.
    """
    # 1) Read CSV
    csv_path = os.path.join(settings.BASE_DIR, "precomputed_results.csv")
    df = pd.read_csv(csv_path)

    # 2) Parse date
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df.dropna(subset=['date'], inplace=True)

    # 3) Check which column we have for sentiment
    #    e.g. "Sentiment" or "sentiment" or "Score"
    if 'Sentiment' in df.columns:
        # If it's POSITIVE/NEGATIVE
        df['sentiment_score'] = df['Sentiment'].map({
            'POSITIVE': 1,
            'NEGATIVE': 0
        })
    elif 'sentiment' in df.columns:
        # If it's POSITIVE/NEGATIVE
        df['sentiment_score'] = df['sentiment'].map({
            'POSITIVE': 1,
            'NEGATIVE': 0
        })
    elif 'Score' in df.columns:
        # If it's numeric
        df.rename(columns={'Score': 'sentiment_score'}, inplace=True)
    else:
        # No recognized sentiment column
        raise ValueError("No recognized sentiment column found!")

    # Drop rows that didn't map properly (NaN after map or rename)
    df.dropna(subset=['sentiment_score'], inplace=True)

    # --------------------------------------------------------------------------
    # 4. Group by day, compute daily average
    # --------------------------------------------------------------------------
    daily_sentiment = (
        df.groupby(df['date'].dt.date)['sentiment_score']
          .mean()
          .reset_index(name='avg_sentiment')
    )

    # Sort by date in ascending order (just in case)
    daily_sentiment = daily_sentiment.sort_values('date')

    # --------------------------------------------------------------------------
    # 5. Rolling average (7-day). Larger window = smoother line.
    # --------------------------------------------------------------------------
    daily_sentiment['rolling_avg'] = daily_sentiment['avg_sentiment'].rolling(window=7).mean()

    # --------------------------------------------------------------------------
    # 6. Detect large changes (day-to-day difference) for annotation
    # --------------------------------------------------------------------------
    daily_sentiment['day_diff'] = daily_sentiment['avg_sentiment'].diff()

    # Suppose a "large shift" is > 0.15 or < -0.15 (tweak as needed)
    threshold = 0.15
    big_shifts = daily_sentiment[abs(daily_sentiment['day_diff']) >= threshold]

    # --------------------------------------------------------------------------
    # 7. Plot the daily average + rolling average with Plotly
    # --------------------------------------------------------------------------
    fig = go.Figure()

    # Daily average line
    fig.add_trace(go.Scatter(
        x=daily_sentiment['date'],
        y=daily_sentiment['avg_sentiment'],
        mode='lines+markers',
        name='Daily Avg',
        line=dict(color='blue')
    ))

    # Rolling average line
    fig.add_trace(go.Scatter(
        x=daily_sentiment['date'],
        y=daily_sentiment['rolling_avg'],
        mode='lines',
        name='7-Day Rolling',
        line=dict(color='red', width=3)
    ))

    # Add annotations for big shifts
    for idx, row in big_shifts.iterrows():
        fig.add_annotation(
            x=row['date'],
            y=row['avg_sentiment'],
            text=f"Δ={row['day_diff']:.2f}",
            showarrow=True,
            arrowhead=2,
            ax=20,   # horizontal offset
            ay=-30,  # vertical offset
            font=dict(color="darkred", size=12, family="Arial")
        )

    fig.update_layout(
        title='Sentiment Over Time (Daily & Rolling Avg)',
        xaxis_title='Date',
        yaxis_title='Average Sentiment',
        template='plotly_white'
    )

    # Convert to HTML snippet
    chart_html = fig.to_html(full_html=False)

    # --------------------------------------------------------------------------
    # 8. Optional: Create a second figure with an OLS trend line
    #    We'll do a scatter of daily_sentiment. If you prefer only the daily points,
    #    we can omit rolling_avg here.
    # --------------------------------------------------------------------------
    trend_fig = px.scatter(
        daily_sentiment,
        x='date',
        y='avg_sentiment',
        title='Sentiment Over Time (OLS Trend)',
        trendline='ols',  # Adds the best-fit line
        trendline_color_override='green'
    )
    trend_fig.update_layout(
        xaxis_title='Date',
        yaxis_title='Avg Sentiment'
    )

    trend_chart_html = trend_fig.to_html(full_html=False)

    # --------------------------------------------------------------------------
    # Render both charts in the template
    # --------------------------------------------------------------------------
    return render(request, 'your_app/results.html', {
        'chart_html': chart_html,
        'trend_chart_html': trend_chart_html
    })

'''
# Actual Results Page 
def results(request):
    merged_csv_path = str(settings.BASE_DIR / "merged_data_with_timestamps.csv")
    df = pd.read_csv(merged_csv_path)

    # Create the table HTML for DataTables
    table_html = df.to_html(
        classes="table table-striped table-bordered",  # helps with styling
        index=False
    )

    # Create your Plotly charts (these return HTML snippets)
    bar_chart_html = create_bar_chart(df)
    hist_chart_html = create_histogram(df)
    pos_wc_b64, neg_wc_b64 = create_wordclouds(df)
    sentiment_over_time_html = create_sentiment_trends_plot(merged_csv_path)

    context = {
        "table_html": table_html,
        "bar_chart": bar_chart_html,
        "hist_chart": hist_chart_html,
        "positive_wordcloud": pos_wc_b64,
        "negative_wordcloud": neg_wc_b64,
        "sentiment_over_time": sentiment_over_time_html,
    }
    return render(request, "sentiment/results.html", context)
'''

#charts

def create_bar_chart(df: pd.DataFrame) -> str:
    """
    Creates a bar chart showing distribution of 'Sentiment'.
    Returns an HTML snippet (Plotly figure) for embedding in the template.
    """
    # Count sentiment
    sentiment_counts = df["Sentiment"].value_counts().reset_index()
    sentiment_counts.columns = ["Sentiment", "Count"]

    # Use Plotly Express for a quick bar chart
    fig = px.bar(
        sentiment_counts,
        x="Sentiment",
        y="Count",
        color="Sentiment",
        title="Sentiment Distribution",
        color_discrete_map={
            "POSITIVE": "skyblue",
            "NEGATIVE": "salmon",
        }
    )

    fig.update_layout(
        xaxis_title="Sentiment",
        yaxis_title="Count",
        template="plotly_white"
    )

    # Return as HTML snippet (which you'll mark 'safe' in your template)
    return fig.to_html(full_html=False)

def create_histogram(df: pd.DataFrame) -> str:
    """
    Creates a histogram of 'Score' for POSITIVE vs. NEGATIVE using Plotly.
    Returns an HTML snippet for embedding in the template.
    """
    positive_scores = df[df["Sentiment"] == "POSITIVE"]["Score"]
    negative_scores = df[df["Sentiment"] == "NEGATIVE"]["Score"]

    fig = go.Figure()

    # Add positive histogram
    fig.add_trace(go.Histogram(
        x=positive_scores,
        name='Positive',
        marker_color='skyblue',
        opacity=0.7
    ))
    # Add negative histogram
    fig.add_trace(go.Histogram(
        x=negative_scores,
        name='Negative',
        marker_color='salmon',
        opacity=0.7
    ))

    fig.update_layout(
        barmode='overlay',  # so that we see them overlapping
        title="Confidence Score Distribution by Sentiment",
        xaxis_title="Score",
        yaxis_title="Frequency",
        template="plotly_white"
    )
    fig.update_traces(marker_line_color='black', marker_line_width=1)

    return fig.to_html(full_html=False)

def create_wordclouds(df: pd.DataFrame):
    """
    Creates word clouds for rows with Sentiment == 'POSITIVE' and 'NEGATIVE'.
    Returns two base64-encoded PNG strings: (pos_wc_b64, neg_wc_b64).
    """
    from wordcloud import WordCloud
    import matplotlib.pyplot as plt

    positive_text = " ".join(df[df["Sentiment"] == "POSITIVE"]["text"].astype(str))
    negative_text = " ".join(df[df["Sentiment"] == "NEGATIVE"]["text"].astype(str))

    # POSITIVE
    pos_wc = WordCloud(width=800, height=400, background_color="white").generate(positive_text)
    pos_io = io.BytesIO()
    plt.figure(figsize=(8, 4))
    plt.imshow(pos_wc, interpolation="bilinear")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(pos_io, format="png")
    plt.close()
    pos_io.seek(0)
    pos_wc_b64 = base64.b64encode(pos_io.getvalue()).decode("utf-8")

    # NEGATIVE
    neg_wc = WordCloud(width=800, height=400, background_color="white").generate(negative_text)
    neg_io = io.BytesIO()
    plt.figure(figsize=(8, 4))
    plt.imshow(neg_wc, interpolation="bilinear")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(neg_io, format="png")
    plt.close()
    neg_io.seek(0)
    neg_wc_b64 = base64.b64encode(neg_io.getvalue()).decode("utf-8")

    return pos_wc_b64, neg_wc_b64

def create_sentiment_trends_plot(csv_path: str) -> str:
    """
    Reads a single CSV that already has 'text', 'Sentiment', and 'date' columns.
    Groups by date and sentiment to plot a line chart of sentiment counts over time,
    returns a Plotly HTML snippet.
    """
    df = pd.read_csv(csv_path)

    # Convert date column to datetime
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    # Drop rows without valid dates
    df = df.dropna(subset=['date'])

    # Group by date (day) and sentiment (unstack so that each sentiment is its own column)
    sentiment_trends = (
        df.groupby([df['date'].dt.date, 'Sentiment'])
          .size()
          .unstack(fill_value=0)
    )

    # Create a Plotly figure with each sentiment as a separate trace
    fig = go.Figure()
    for sentiment_label in sentiment_trends.columns:
        fig.add_trace(go.Scatter(
            x=sentiment_trends.index,
            y=sentiment_trends[sentiment_label],
            mode='lines+markers',
            name=sentiment_label
        ))

    fig.update_layout(
        title="Sentiment Trends Over Time",
        xaxis_title="Date",
        yaxis_title="Count",
        template="plotly_white"
    )

    return fig.to_html(full_html=False)

#Botometer
def check_accounts_view(request):
    """
    1. Reads a CSV file with a 'screen_name' column (uploaded or stored).
    2. Calls Botometer for each screen name.
    3. Displays the results in a table or page.
    """
    if request.method == 'POST':
        # Example: user uploaded a CSV of Twitter usernames
        csv_file = request.FILES['file'] if 'file' in request.FILES else None
        if not csv_file or not csv_file.name.endswith('.csv'):
            messages.error(request, "Please upload a valid CSV file.")
            return redirect('check_accounts')

        # read into a DataFrame
        df = pd.read_csv(csv_file)

        if 'user_name' not in df.columns:
            messages.error(request, "No 'screen_name' column found in CSV.")
            return redirect('check_accounts')

        screen_names = df['user_name'].astype(str).tolist()

        # Your RapidAPI key from environment or Django settings
        rapidapi_key = getattr(settings, 'RAPIDAPI_KEY', None)
        if not rapidapi_key:
            messages.error(request, "Missing RAPIDAPI_KEY in Django settings.")
            return redirect('check_accounts')

        # 2. Call Botometer for each screen name
        results = bulk_check_bot_accounts(screen_names, rapidapi_key)

        # 3. Convert results to a DataFrame (if you like)
        #    Each item is { "screen_name": <>, "botometer_result": {...} }
        results_df = pd.DataFrame(results)

        # Example: let's parse top-level fields from the API response
        # In practice, you'd adapt this to your returned JSON structure
        def parse_score(row):
            data = row['botometer_result']
            if isinstance(data, dict) and 'scores' in data:
                return data['scores'].get('universal', None)
            return None

        results_df['bot_score'] = results_df.apply(parse_score, axis=1)

        # 4. Pass results to template
        table_html = results_df[['screen_name','bot_score']].to_html(index=False)
        context = {'table': table_html}
        return render(request, 'sentiment/bot_check_results.html', context)

    # GET request: show upload form
    return render(request, 'sentiment/check_accounts.html')


# new graphs 
import pandas as pd
import plotly.graph_objects as go
from plotly.offline import plot  # or to_html
from django.conf import settings
from django.shortcuts import render

def sentiment_trends(request):
    # 1. Load CSV
    csv_path = str(settings.BASE_DIR / "npt.csv")
    df = pd.read_csv(csv_path)

    # 2. Parse date -> datetime
    df['date'] = pd.to_datetime(df['date'], errors='coerce')  

    # Drop rows with no valid date
    df = df.dropna(subset=['date'])

    # 3. If your sentiment column is numeric:
    #    Let's call it "sentiment_score"
    #    If your column is named differently, adjust below
    #    Example: If you just have "Score" or "sentiment" as a float, rename it:
    df.rename(columns={'sentiment': 'sentiment_score'}, inplace=True)

    # 4. Group by day -> get average sentiment
    daily_sentiment = (
        df.groupby(df['date'].dt.date)['sentiment_score']
          .mean()
          .reset_index(name='avg_sentiment')
    )

    # 5. Sort by date in case it's not sorted
    daily_sentiment = daily_sentiment.sort_values(by='date')

    # 6. Create rolling average (7-day or 14-day)
    daily_sentiment['rolling_avg'] = daily_sentiment['avg_sentiment'].rolling(window=7).mean()

    # 7. Plot with Plotly
    fig = go.Figure()

    # Daily avg line
    fig.add_trace(go.Scatter(
        x=daily_sentiment['date'],
        y=daily_sentiment['avg_sentiment'],
        mode='lines+markers',
        name='Daily Avg Sentiment',
        line=dict(color='blue')
    ))

    # Rolling avg line
    fig.add_trace(go.Scatter(
        x=daily_sentiment['date'],
        y=daily_sentiment['rolling_avg'],
        mode='lines',
        name='7-day Rolling Avg',
        line=dict(color='red', width=3)
    ))

    fig.update_layout(
        title='Sentiment Over Time',
        xaxis_title='Date',
        yaxis_title='Average Sentiment',
        template='plotly_white',
    )

    # 8. Convert figure to HTML snippet
    chart_html = fig.to_html(full_html=False)

    # 9. Render in template
    return render(request, 'sentiment/trends.html', {
        'chart_html': chart_html
    })


