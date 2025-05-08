import io
import time
import datetime
import uuid
import pandas as pd
from celery import shared_task
from transformers import pipeline
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Load the sentiment analysis pipeline once
SENTIMENT_PIPELINE = pipeline("sentiment-analysis")

@shared_task(bind=True)
def run_sentiment_analysis(self, file_data, num_rows):
    # Read the uploaded CSV file
    df = pd.read_csv(io.StringIO(file_data))

    start_time = time.time()  # Track processing time

    for i, row in df.iterrows():
        text = str(row['text'])[:512]  # Limit to 512 tokens
        result = SENTIMENT_PIPELINE(text)[0]

        # Save sentiment results to DataFrame
        df.at[i, 'Sentiment'] = result['label']
        df.at[i, 'Score'] = result['score']

        # Progress tracking
        current = i + 1
        elapsed = time.time() - start_time
        avg_time_per_row = elapsed / current
        eta_seconds = avg_time_per_row * (num_rows - current)
        eta_formatted = str(datetime.timedelta(seconds=int(eta_seconds)))

        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': current,
                'total': num_rows,
                'eta': eta_formatted,
                'status': f"Processing row {current}/{num_rows}"
            }
        )

    # Save DataFrame to CSV in memory
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()

    # Prepare file for Django storage
    content_file = ContentFile(csv_content)
    filename = f"sentiment_results_{uuid.uuid4().hex}.csv"
    file_path = default_storage.save(f"sentiment_outputs/{filename}", content_file)

    # Get file URL
    if hasattr(default_storage, 'url'):
        file_url = default_storage.url(file_path)
    else:
        file_url = file_path  # fallback

    return {
        'current': num_rows,
        'total': num_rows,
        'eta': "0:00:00",
        'status': "Task completed!",
        'file_url': file_url
    }
