# Use a lightweight Python base image
FROM python:3.9-slim

# Create a working directory in the container
WORKDIR /app

# Copy the entire project into the container
COPY . /app

# Install system dependencies (if needed for e.g. pandas, matplotlib)
# You can adjust or remove if your packages need additional system libs
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libxml2 \
    libxslt1.1 \
    libjpeg-dev \
    zlib1g-dev \
    gcc \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies in one go (based on your imports):
RUN pip install --no-cache-dir \
    celery \
    django>=3.2 \
    django-data-browser \
    matplotlib \
    numpy \
    pandas \
    plotly \
    requests \
    transformers \
    wordcloud \
    torch 

# Expose Django’s default port
EXPOSE 8000

# By default, run the development server on port 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
