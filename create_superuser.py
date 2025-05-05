import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'disv2.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@admin.com')
password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'admin')

if not User.objects.filter(username=username).exists():
    print(f"Creating superuser '{username}'...")
    User.objects.create_superuser(username=username, email=email, password=password)
else:
    print(f"Superuser '{username}' already exists.")
