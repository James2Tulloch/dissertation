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
import statsmodels.api as sm  # Added for OLS trendline support

def analysis_results(request):
    csv_path = os.path.join(settings.BASE_DIR, 'precomputed_results.csv')
    try:
        df = pd.read_csv(csv_path)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df.dropna(subset=['date'], inplace=True)
        
        # Check if any rows remain after date filtering
        if len(df) == 0:
            return render(request, "sentiment/error.html", {"message": "No valid dates found in data."})
        
        # Handle sentiment scoring properly with better column detection
        if 'Sentiment' in df.columns:
            df['sentiment_score'] = df['Sentiment'].map({'POSITIVE': 1, 'NEGATIVE': 0})
            sentiment_column = 'Sentiment'
        elif 'sentiment' in df.columns:
            df['sentiment_score'] = df['sentiment'].map({'POSITIVE': 1, 'NEGATIVE': 0})
            sentiment_column = 'sentiment'
        elif 'Score' in df.columns:
            df.rename(columns={'Score': 'sentiment_score'}, inplace=True)
            # Create a derived sentiment column for charts
            df['Sentiment_Category'] = df['sentiment_score'].apply(lambda x: 'POSITIVE' if x > 0.5 else 'NEGATIVE')
            sentiment_column = 'Sentiment_Category'
        else:
            return render(request, "sentiment/error.html", {"message": "No recognized sentiment column found in data."})
        
        # Check if sentiment mapping worked
        if df['sentiment_score'].isna().all():
            return render(request, "sentiment/error.html", {"message": "Could not map sentiment values to scores."})
            
        # Now drop nulls with tracking
        original_len = len(df)
        df.dropna(subset=['sentiment_score'], inplace=True)
        rows_dropped = original_len - len(df)
        
        if len(df) == 0:
            return render(request, "sentiment/error.html", {"message": "No valid sentiment scores found in data."})

        # Compute daily average and rolling
        daily_sentiment = (
            df.groupby(df['date'].dt.date)['sentiment_score']
              .mean()
              .reset_index(name='avg_sentiment')
        )
        daily_sentiment = daily_sentiment.sort_values('date')
        daily_sentiment['rolling_avg'] = daily_sentiment['avg_sentiment'].rolling(window=7).mean()

        # Detect big daily shifts
        daily_sentiment['day_diff'] = daily_sentiment['avg_sentiment'].diff()
        threshold = 0.15
        big_shifts = daily_sentiment[abs(daily_sentiment['day_diff']) >= threshold]

        # Daily Sentiment Chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily_sentiment['date'], y=daily_sentiment['avg_sentiment'], mode='lines+markers', name='Daily Avg'))
        fig.add_trace(go.Scatter(x=daily_sentiment['date'], y=daily_sentiment['rolling_avg'], mode='lines', name='7-Day Rolling'))

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

        # OLS Trend Chart - Improved date handling
        trend_fig = px.scatter(
            daily_sentiment, 
            x='date', 
            y='avg_sentiment', 
            title='OLS Trend Over Time', 
            trendline='ols', 
            trendline_color_override='green'
        )
        
        trend_fig.update_layout(
            xaxis_title='Date',
            yaxis_title='Average Sentiment',
            template='plotly_white'
        )
        trend_chart_html = trend_fig.to_html(full_html=False)

        # Bar Chart - Sentiment Distribution with proper column handling
        sentiment_counts = df[sentiment_column].value_counts().reset_index()
        sentiment_counts.columns = ["Sentiment", "Count"]
        bar_fig = px.bar(sentiment_counts, x="Sentiment", y="Count", color="Sentiment",
                         color_discrete_map={"POSITIVE": "skyblue", "NEGATIVE": "salmon"},
                         title="Sentiment Distribution")
        bar_fig.update_layout(xaxis_title="Sentiment", yaxis_title="Count", template="plotly_white")
        bar_chart_html = bar_fig.to_html(full_html=False)

        # Confidence Score Histogram with error handling
        hist_fig = go.Figure()
        
        # Get positive and negative scores based on available columns
        positive_scores = df[df[sentiment_column] == "POSITIVE"]["sentiment_score"]
        negative_scores = df[df[sentiment_column] == "NEGATIVE"]["sentiment_score"]

        # Add histograms with error handling
        if not positive_scores.empty:
            hist_fig.add_trace(go.Histogram(x=positive_scores, name='Positive', marker_color='skyblue', opacity=0.7))
        if not negative_scores.empty:
            hist_fig.add_trace(go.Histogram(x=negative_scores, name='Negative', marker_color='salmon', opacity=0.7))

        # If both are empty, add a message
        if positive_scores.empty and negative_scores.empty:
            hist_fig.add_annotation(
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                text="No sentiment data available",
                showarrow=False,
                font=dict(size=20)
            )
        else:
            hist_fig.update_layout(
                barmode='overlay',
                title="Confidence Score Distribution",
                xaxis_title="Score",
                yaxis_title="Frequency",
                template="plotly_white"
            )
            hist_fig.update_traces(marker_line_color='black', marker_line_width=1)
        hist_chart_html = hist_fig.to_html(full_html=False)
        # Word Clouds
        positive_text = " ".join(df[df[sentiment_column] == "POSITIVE"]["text"].astype(str))
        negative_text = " ".join(df[df[sentiment_column] == "NEGATIVE"]["text"].astype(str))
        positive_wordcloud = WordCloud(width=800, height=400, background_color='white').generate(positive_text)
        negative_wordcloud = WordCloud(width=800, height=400, background_color='white').generate(negative_text)
        positive_wordcloud_image = BytesIO()
        positive_wordcloud.to_image().save(positive_wordcloud_image, format='PNG')
        positive_wordcloud_image.seek(0)
        negative_wordcloud_image = BytesIO()
        negative_wordcloud.to_image().save(negative_wordcloud_image, format='PNG')
        negative_wordcloud_image.seek(0)
        pos_wc_b64 = base64.b64encode(positive_wordcloud_image.getvalue()).decode('utf-8')
        neg_wc_b64 = base64.b64encode(negative_wordcloud_image.getvalue()).decode('utf-8')
        return render(request, "sentiment/results.html", {
            "chart_html": chart_html,
            "trend_chart_html": trend_chart_html,
            "bar_chart_html": bar_chart_html,
            "hist_chart_html": hist_chart_html,
            "positive_wordcloud": pos_wc_b64,
            "negative_wordcloud": neg_wc_b64,
            "rows_dropped": rows_dropped
        })
    except FileNotFoundError:
        return render(request, "sentiment/error.html", {"message": "Results file not found."})
    except pd.errors.EmptyDataError:
        return render(request, "sentiment/error.html", {"message": "Results file is empty."})
    except Exception as e:
        return render(request, "sentiment/error.html", {"message": f"An error occurred: {str(e)}"})
