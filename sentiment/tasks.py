import time
import pandas as pd
from celery import shared_task
from transformers import pipeline

SENTIMENT_PIPELINE = pipeline("sentiment-analysis")
@shared_task(bind=True)
def run_sentiment_analysis(self, file_data, num_rows):
    import time
    import io
    import pandas as pd
    from transformers import pipeline

    SENTIMENT_PIPELINE = pipeline("sentiment-analysis")

    df = pd.read_csv(io.StringIO(file_data))

    start_time = time.time()  # Record the starting time

    for i, row in df.iterrows():
        text = str(row['text'])[:512]
        result = SENTIMENT_PIPELINE(text)[0]
        
        # ... store results in df
        df.at[i, 'Sentiment'] = result['label']
        df.at[i, 'Score'] = result['score']

        # Calculate progress
        current = i + 1

        # Calculate how long we've taken so far
        elapsed = time.time() - start_time

        # Average time per row
        avg_time_per_row = elapsed / current

        # Remaining rows
        remaining = num_rows - current

        # Estimate how many seconds remain
        eta_seconds = avg_time_per_row * remaining

        # Convert to HH:MM:SS format (optional)
        import datetime
        eta_formatted = str(datetime.timedelta(seconds=int(eta_seconds)))

        # Update Celery state with current progress and ETA
        self.update_state(
            state='PROGRESS',
            meta={
                'current': current,
                'total': num_rows,
                'eta': eta_formatted,   # e.g., "0:00:53"
                'status': f"Processing row {current}/{num_rows}"
            }
        )

    # Finished
    return {
        'current': num_rows,
        'total': num_rows,
        'eta': "0:00:00", 
        'status': "Task completed!"
    }

