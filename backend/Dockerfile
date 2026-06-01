FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV HOME=/home/user
ENV HF_HOME=/home/user/.cache/huggingface

# Create a non-root user and set up home directory
RUN useradd -m -u 1000 user

# Set working directory
WORKDIR /home/user/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install dependencies globally as root to make sure CLI tools like uvicorn are in system PATH
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the SentenceTransformer model globally during build time
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"

# Copy backend application code with correct ownership
COPY --chown=user . .

# Pre-create logs directory and set correct ownership to avoid PermissionError at runtime
RUN mkdir -p /home/user/app/logs && chown -R user:user /home/user

# Switch to the non-root user for runtime security
USER user

# Expose port
EXPOSE 7860

# Run uvicorn server
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
