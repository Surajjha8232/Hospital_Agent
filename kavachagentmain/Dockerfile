# Use official Python slim image
FROM python:3.10-slim

# Set working directory in container
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your FastAPI app files
COPY . .

# Install nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 8080
ENV PORT=8080

CMD ["sh", "-c", "echo STARTING ADK && adk web & sleep 5 && echo STARTING NGINX && nginx -g 'daemon off;'"]

#CMD["sh","-c","adk","web","--port=8080","--host=0.0.0.0"]

