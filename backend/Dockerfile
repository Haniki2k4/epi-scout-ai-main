FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV HOME=/home/user
ENV HF_HOME=/home/user/.cache/huggingface

# Create a non-root user and set up home directory
RUN useradd -m -u 1000 user
WORKDIR $HOME/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY --chown=user requirements.txt .

# Install dependencies with pip cache disabled
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the SentenceTransformer model during build time to speed up container startup
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"

# Copy backend application code with correct ownership
COPY --chown=user . .

# Switch to the non-root user
USER user

# Expose port
EXPOSE 7860

# Run uvicorn server
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
