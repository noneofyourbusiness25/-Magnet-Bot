FROM python:3.11-slim

# Install necessary packages including ffmpeg, mkvtoolnix, and mediainfo
RUN apt-get update && \
    apt-get install -y ffmpeg mkvtoolnix mediainfo && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Command to run the bot
ENV PYTHONPATH=/app
CMD ["python", "src/main.py"]
