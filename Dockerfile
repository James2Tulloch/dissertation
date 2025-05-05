FROM python:3.9

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system packages (TensorFlow needs these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libxml2 \
    libxslt1.1 \
    libjpeg-dev \
    zlib1g-dev \
    libpq-dev \
    gcc \
    curl \
    git \
    wget \
    ca-certificates \   
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to take advantage of Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy rest of the app
COPY . .
RUN chmod +x migrations.sh
# Expose port for dev
EXPOSE 8000

# Default run
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
