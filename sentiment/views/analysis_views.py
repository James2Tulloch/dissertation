import pandas as pd
import os
from django.conf import settings
from django.shortcuts import render
import base64
from io import BytesIO
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import plotly.express as px
import plotly.graph_objects as go
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage


def analysis_results(request):
    if request.method == "POST" and request.FILES.get("csv_file"):
        uploaded_file: UploadedFile = request.FILES["csv_file"]


        temp_path = default_storage.save(f"temp_uploads/{uploaded_file.name}", uploaded_file)
        csv_path = default_storage.path(temp_path)
    else:
  
        csv_path = os.path.join(settings.BASE_DIR, "precomputed_results.csv")

    if not os.path.exists(csv_path):
        return render(request, "sentiment/error.html", {"message": "Results file not found."})

    df = pd.read_csv(csv_path)

    if df.empty:
        return render(request, "sentiment/error.html", {"message": "Results file is empty."})


    timestamp_col = None
    for col in ['date', 'time']:
        if col in df.columns:
            timestamp_col = col
            break

    if not timestamp_col:
        return render(request, "sentiment/error.html", {
            "message": "The uploaded CSV must contain a 'date' or 'time' column."
        })


    df['date'] = pd.to_datetime(df[timestamp_col], errors='coerce')
    df.dropna(subset=['date'], inplace=True)

    if df.empty:
        return render(request, "sentiment/error.html", {
            "message": f"No valid date/time values found in '{timestamp_col}' column."
        })


    if 'Sentiment' in df.columns:
        df['sentiment_score'] = df['Sentiment'].map({'POSITIVE': 1, 'NEGATIVE': 0})
        sentiment_column = 'Sentiment'
    elif 'sentiment' in df.columns:
        df['sentiment_score'] = df['sentiment'].map({'POSITIVE': 1, 'NEGATIVE': 0})
        sentiment_column = 'sentiment'
    elif 'Score' in df.columns:
        df.rename(columns={'Score': 'sentiment_score'}, inplace=True)
        df['Sentiment_Category'] = df['sentiment_score'].apply(lambda x: 'POSITIVE' if x > 0.5 else 'NEGATIVE')
        sentiment_column = 'Sentiment_Category'
    else:
        return render(request, "sentiment/error.html", {"message": "No recognized sentiment column found."})

    if df['sentiment_score'].isna().all():
        return render(request, "sentiment/error.html", {"message": "No valid sentiment scores found."})

    original_len = len(df)
    df.dropna(subset=['sentiment_score'], inplace=True)
    rows_dropped = original_len - len(df)

    if df.empty:
        return render(request, "sentiment/error.html", {"message": "No valid sentiment scores after cleaning."})


    daily_sentiment = (
        df.groupby(df['date'].dt.date)['sentiment_score']
          .mean()
          .reset_index(name='avg_sentiment')
    )
    daily_sentiment = daily_sentiment.sort_values('date')
    daily_sentiment['rolling_avg'] = daily_sentiment['avg_sentiment'].rolling(window=7).mean()


    daily_sentiment['day_diff'] = daily_sentiment['avg_sentiment'].diff()
    threshold = 0.15
    big_shifts = daily_sentiment[abs(daily_sentiment['day_diff']) >= threshold]

    #Daily sentiment line
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily_sentiment['date'],
        y=daily_sentiment['avg_sentiment'],
        mode='lines+markers',
        name='Daily Avg'
    ))
    fig.add_trace(go.Scatter(
        x=daily_sentiment['date'],
        y=daily_sentiment['rolling_avg'],
        mode='lines',
        name='7-Day Rolling'
    ))
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

    # OLS Trend Line figure
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
        yaxis_title='Average Sentiment',
        template='plotly_white'
    )
    trend_chart_html = trend_fig.to_html(full_html=False)

    # Sentiment Distribution 
    sentiment_counts = df[sentiment_column].value_counts().reset_index()
    sentiment_counts.columns = ["Sentiment", "Count"]

    bar_fig = px.bar(
        sentiment_counts,
        x="Sentiment",
        y="Count",
        color="Sentiment",
        color_discrete_map={"POSITIVE": "skyblue", "NEGATIVE": "salmon"},
        title="Sentiment Distribution"
    )
    bar_fig.update_layout(
        xaxis_title="Sentiment",
        yaxis_title="Count",
        template="plotly_white"
    )
    bar_chart_html = bar_fig.to_html(full_html=False)

    # Confidence Score Histogram
    hist_fig = go.Figure()
    positive_scores = df[df[sentiment_column] == "POSITIVE"]["sentiment_score"]
    negative_scores = df[df[sentiment_column] == "NEGATIVE"]["sentiment_score"]

    if not positive_scores.empty:
        hist_fig.add_trace(go.Histogram(x=positive_scores, name='Positive', marker_color='skyblue', opacity=0.7))
    if not negative_scores.empty:
        hist_fig.add_trace(go.Histogram(x=negative_scores, name='Negative', marker_color='salmon', opacity=0.7))

    if not positive_scores.empty or not negative_scores.empty:
        hist_fig.update_layout(
            barmode='overlay',
            title="Confidence Score Distribution",
            xaxis_title="Score",
            yaxis_title="Frequency",
            template="plotly_white"
        )
        hist_fig.update_traces(marker_line_color='black', marker_line_width=1)
    else:
        hist_fig.add_annotation(
            x=0.5, y=0.5,
            xref="paper", yref="paper",
            text="No sentiment data available",
            showarrow=False,
            font=dict(size=20)
        )

    hist_chart_html = hist_fig.to_html(full_html=False)

    # WordClouds
    def generate_wordcloud(text):
        buffer = BytesIO()
        if not text.strip():
            plt.figure(figsize=(8, 4))
            plt.text(0.5, 0.5, "No text available for analysis",
                     horizontalalignment='center', verticalalignment='center',
                     fontsize=20, color='gray', transform=plt.gca().transAxes)
            plt.axis("off")
        else:
            wc = WordCloud(width=800, height=400, background_color="white").generate(text)
            plt.figure(figsize=(8, 4))
            plt.imshow(wc, interpolation="bilinear")
            plt.axis("off")
        plt.tight_layout()
        plt.savefig(buffer, format="png")
        plt.close()
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    positive_text = " ".join(df[df[sentiment_column] == "POSITIVE"]["text"].astype(str)) if 'text' in df.columns else ""
    negative_text = " ".join(df[df[sentiment_column] == "NEGATIVE"]["text"].astype(str)) if 'text' in df.columns else ""

    pos_wc_b64 = generate_wordcloud(positive_text)
    neg_wc_b64 = generate_wordcloud(negative_text)

    return render(request, "sentiment/results.html", {
        "chart_html": chart_html,
        "trend_chart_html": trend_chart_html,
        "bar_chart_html": bar_chart_html,
        "hist_chart_html": hist_chart_html,
        "positive_wordcloud": pos_wc_b64,
        "negative_wordcloud": neg_wc_b64,
        "rows_dropped": rows_dropped
    })
