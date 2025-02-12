# Use Python 3.10 slim image as base
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    RAILWAY_ENVIRONMENT=production \
    DEBIAN_FRONTEND=noninteractive

# Create a non-root user
RUN useradd -m -s /bin/bash app_user

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    git \
    libmagic1 \
    libpython3-dev \
    build-essential \
    python3-dev \
    pkg-config \
    curl \
    # Video processing dependencies
    libavcodec-extra \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libatlas-base-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    # Additional dependencies for Python packages
    python3-pip \
    python3-setuptools \
    python3-wheel \
    gcc \
    g++ \
    # Cleanup
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with optimizations
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    echo "Installing base dependencies..." && \
    pip install --no-cache-dir numpy==1.24.3 pandas==2.2.3 psutil==5.9.8 python-dotenv==1.0.0 openai==1.3.5 cloudinary==1.38.0 aiohttp==3.9.3 aiosignal==1.3.2 aiodns==3.1.1 aiolimiter==1.1.1 google-cloud-vision==3.9.0 google-cloud-texttospeech==2.14.1 moviepy==1.0.3 ffmpeg-python==0.2.0 && \
    echo "Installing OpenCV..." && \
    pip install --no-cache-dir opencv-python-headless==4.11.0.86 && \
    echo "Installing core ML dependencies..." && \
    pip install --no-cache-dir scikit-image==0.25.1 scipy==1.15.1 && \
    echo "Installing web dependencies..." && \
    pip install --no-cache-dir fastapi==0.115.8 uvicorn==0.34.0 && \
    echo "Installing Google Cloud dependencies..." && \
    pip install --no-cache-dir google-cloud-vision==3.9.0 google-cloud-texttospeech==2.14.1 && \
    echo "Installing remaining requirements..." && \
    pip install --no-cache-dir -r requirements.txt && \
    echo "Installing yt-dlp..." && \
    pip install --no-cache-dir yt-dlp && \
    # Clean up pip cache
    rm -rf /root/.cache/pip/* && \
    # Pre-compile Python files
    python -m compileall /app

# Create necessary directories with proper structure
RUN mkdir -p \
    /app/credentials \
    /app/analysis_temp \
    /app/framesAndLogo/Nature \
    /app/framesAndLogo/News \
    /app/framesAndLogo/Funny \
    /app/framesAndLogo/Infographic

# Copy the entire application
COPY . .

# Set proper permissions
RUN chown -R app_user:app_user \
    /app \
    && chmod -R 755 /app pipeline \
    && chmod -R 777 \
    /app/credentials \
    /app/analysis_temp \
    /app/framesAndLogo

# Switch to non-root user
USER app_user

# Set environment variables for the application
ENV HOME=/home/app_user \
    PYTHONPATH=${PYTHONPATH}:/app \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    # OpenCV optimizations
    OPENCV_FFMPEG_CAPTURE_OPTIONS="video_codec;h264_cuvid" \
    OPENCV_VIDEOIO_PRIORITY_BACKEND=2 \
    # FFmpeg optimizations
    FFREPORT=file=/app/analysis_temp/ffmpeg-%p-%t.log \
    PYTHONWARNINGS="ignore:Unverified HTTPS request"

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose the port
EXPOSE ${PORT}

# Start the FastAPI server
CMD python -m uvicorn api:app --host 0.0.0.0 --port ${PORT} 