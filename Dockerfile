# Use a lightweight Python base image
FROM python:3.11-slim

# Build arguments
ARG BUILD_DATE
ARG VERSION
ARG VCS_REF

# Set environment variable to disable output buffering (improves Flask logging)
ENV PYTHONUNBUFFERED=1

# Labels for metadata (OCI Image Format Specification)
LABEL org.opencontainers.image.created=$BUILD_DATE \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$VCS_REF \
      org.opencontainers.image.source="https://github.com/dockpeek/dockpeek" \
      org.opencontainers.image.url="https://github.com/dockpeek/dockpeek" \
      org.opencontainers.image.documentation="https://github.com/dockpeek/dockpeek#readme" \
      org.opencontainers.image.title="Dockpeek" \
      org.opencontainers.image.description="Docker container monitoring and management tool" \
      org.opencontainers.image.authors="Dockpeek" 

# Create app directory and set it as the working directory
WORKDIR /app

# Copy dependency files
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application code into the container
COPY . .

# Optional: expose the port Flask runs on (can also be declared in docker-compose)
EXPOSE 8000

# Default command to run the Flask app
CMD ["python", "app.py"]