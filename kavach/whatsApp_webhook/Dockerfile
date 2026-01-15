# Use official Python slim image
FROM python:3.10-slim

# Set working directory in container
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your FastAPI app files
COPY . .

# Expose the port your app will run on
EXPOSE 8080

# Run the application with Uvicorn ASGI server
CMD ["sh", "-c", "uvicorn cloudrun_whatsapp_webhook_server:app --host 0.0.0.0 --port ${PORT:-8080}"]



