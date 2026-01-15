FROM python:3.10-slim

# Set working directory in container
WORKDIR /app


# Install system dependencies required for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . /app

# Ensure python output is sent directly to terminal
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Run the server
CMD ["python", "mcp_hospital.py"]

