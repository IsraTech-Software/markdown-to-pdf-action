FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install WeasyPrint C-dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    libjpeg-dev \
    libopenjp2-7-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a dedicated directory for the Action's logic
WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the execution script
COPY generator.py .

# We do NOT set WORKDIR back. GitHub Actions will dynamically override WORKDIR 
# to /github/workspace at runtime, ensuring your script reads the consuming repo's files.

ENTRYPOINT ["python", "/app/generator.py"]
