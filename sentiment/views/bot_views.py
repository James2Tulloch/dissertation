import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from sentiment.bot_utils import bulk_check_bot_accounts

def check_accounts_view(request):
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