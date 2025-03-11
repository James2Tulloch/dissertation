from django.core.management.base import BaseCommand
import csv
from myapp.models import CsvRow
from datetime import datetime

class Command(BaseCommand):
    help = 'Import CSV data into the CsvRow model.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file.')

    def handle(self, *args, **options):
        csv_file = options['csv_file']

        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = []
            for row in reader:
                # Convert/parse fields
                date_str = row.get('date')
                text = row.get('text', '')
                sentiment = row.get('sentiment', '')
                score = row.get('score', None)

                parsed_date = None
                if date_str:
                    try:
                        # Adjust format as needed
                        parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except ValueError:
                        pass

                # Create model instance in memory
                csv_row = CsvRow(
                    date=parsed_date,
                    text=text,
                    sentiment=sentiment,
                    score=score if score else None
                )
                rows.append(csv_row)

            # Bulk create for efficiency
            CsvRow.objects.bulk_create(rows)
            self.stdout.write(self.style.SUCCESS("CSV imported successfully!"))

