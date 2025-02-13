# Use Python 3.10 slim image as base
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    RAILWAY_ENVIRONMENT=production \
    DEBIAN_FRONTEND=noninteractive \
    # OpenAI and API settings
    OPENAI_API_BASE="https://api.openai.com/v1" \
    OPENAI_API_TYPE="open_ai" \
    OPENAI_API_VERSION="2024-02-01" \
    OPENAI_ORGANIZATION="" \
    MODEL_NAME="gpt-4o-mini" \
    # DeepSeek settings
    DEEPSEEK_API_BASE="https://api.deepseek.com" \
    # Timeout settings
    HTTP_TIMEOUT=300 \
    MAX_RETRIES=3 \
    REQUEST_TIMEOUT=300

# Create a non-root user
RUN useradd -m -s /bin/bash app_user

# Add Chrome repository and install system dependencies
RUN apt-get update && \
    apt-get install -y wget gnupg2 && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    sudo \
    google-chrome-stable \
    chromium-driver \
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
    unzip \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    default-jdk \
    apt-transport-https \
    ca-certificates \
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

# Set up Chrome and ChromeDriver
ENV CHROME_BIN=/usr/bin/google-chrome \
    CHROME_PATH=/usr/bin/google-chrome \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    DISPLAY=:99

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with optimizations - split into smaller chunks for better error handling
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    echo "Installing base dependencies..." && \
    pip install --no-cache-dir numpy==2.2.3 pandas==2.2.3 psutil==5.9.8 python-dotenv==1.0.0 && \
    echo "Installing Selenium and related..." && \
    pip install --no-cache-dir selenium==4.28.1 webdriver-manager==4.0.2 undetected-chromedriver==3.5.5 && \
    echo "Installing OpenAI and dependencies..." && \
    pip install --no-cache-dir "httpx==0.28.1" "openai==1.62.0" "httpcore>=1.0.2" "anyio>=3.5.0" "sniffio>=1.1" && \
    echo "Installing cloud services..." && \
    pip install --no-cache-dir cloudinary==1.38.0 aiohttp==3.11.12 aiosignal==1.3.2 aiodns==3.1.1 aiolimiter==1.1.1 async-timeout==5.0.1 google-cloud-vision==3.10.0 google-cloud-texttospeech==2.14.1 && \
    echo "Installing OpenCV..." && \
    pip install --no-cache-dir opencv-python-headless==4.11.0.86 && \
    echo "Installing core ML dependencies..." && \
    pip install --no-cache-dir scikit-image==0.25.1 scipy==1.15.1 && \
    echo "Installing web dependencies..." && \
    pip install --no-cache-dir fastapi==0.115.8 uvicorn==0.34.0 && \
    echo "Installing yt-dlp..." && \
    pip install --no-cache-dir yt-dlp==2025.1.26 && \
    # Clean up pip cache
    rm -rf /root/.cache/pip/* && \
    # Pre-compile Python files
    python -m compileall /app

# Create necessary directories with proper structure
RUN mkdir -p \
    /home/app_user/.cache/yt-dlp \
    /home/app_user/.cache/youtube-dl \
    /home/app_user/.cache/selenium \
    /home/app_user/.config/chromium \
    /home/app_user/.config/google-chrome \
    /app/credentials \
    /app/analysis_temp \
    /app/framesAndLogo/Nature \
    /app/framesAndLogo/News \
    /app/framesAndLogo/Funny \
    /app/framesAndLogo/Infographic

# Copy the entire application
COPY . .

# Add app_user to sudo group and configure passwordless sudo for X11 management
RUN adduser app_user sudo && \
    echo 'app_user ALL=(ALL) NOPASSWD: /usr/bin/chown root\:root /tmp/.X11-unix/,/usr/bin/chmod 1777 /tmp/.X11-unix/' >> /etc/sudoers

# Create X11 directory with proper permissions
USER root
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix && \
    chown root:root /tmp/.X11-unix

# Set proper permissions
RUN chown -R app_user:app_user \
    /app \
    /home/app_user/.cache \
    /home/app_user/.config \
    && chmod -R 755 /app pipeline \
    && chmod -R 777 \
    /app/credentials \
    /app/analysis_temp \
    /app/framesAndLogo \
    /home/app_user/.config \
    /home/app_user/.cache

# Switch to non-root user
USER app_user

# Set environment variables for the application
ENV HOME=/home/app_user \
    PYTHONPATH=${PYTHONPATH}:/app \
    SELENIUM_CACHE_PATH=/home/app_user/.cache/selenium \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    # OpenCV optimizations
    OPENCV_FFMPEG_CAPTURE_OPTIONS="video_codec;h264_cuvid" \
    OPENCV_VIDEOIO_PRIORITY_BACKEND=2 \
    # FFmpeg optimizations
    FFREPORT=file=/app/analysis_temp/ffmpeg-%p-%t.log \
    # Chrome/Selenium settings
    SELENIUM_HEADLESS=true \
    PYTHONWARNINGS="ignore:Unverified HTTPS request" \
    # API Client settings
    OPENAI_REQUEST_TIMEOUT=300 \
    OPENAI_MAX_RETRIES=3 \
    OPENAI_BACKOFF_FACTOR=1 \
    OPENAI_INITIAL_DELAY=1

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose the port
EXPOSE ${PORT}

# Start the FastAPI server with Xvfb for headless browser support
CMD set -e && \
    sudo -n chown root:root /tmp/.X11-unix && \
    sudo -n chmod 1777 /tmp/.X11-unix && \
    rm -f /tmp/.X99-lock && \
    Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset & \
    python -m uvicorn api:app --host 0.0.0.0 --port ${PORT} 