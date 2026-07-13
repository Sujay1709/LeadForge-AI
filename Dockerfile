FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY lead_gen_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY lead_gen_agent/ .

# Streamlit config for production
RUN mkdir -p /root/.streamlit
COPY streamlit_config.toml /root/.streamlit/config.toml

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
