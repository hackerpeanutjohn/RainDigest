FROM python:3.11-slim

# Install system dependencies
# ffmpeg is required for yt-dlp audio extraction and processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install poetry
RUN pip install "poetry==1.7.1"

# Copy project files
COPY pyproject.toml poetry.lock* ./

# Config poetry: create virtualenv inside project (optional, or just disable)
# We disable virtualenvs.create to install directly into system python in the container
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY . .

# Create output directories
RUN mkdir -p output data

# Default command
CMD ["python", "-m", "src.main"]
