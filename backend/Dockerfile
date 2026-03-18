# Use the official Playwright Python image - comes with Chromium + all system deps
# This avoids manual dep installation which breaks on some Debian versions
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=120 -r requirements.txt

# Copy application code
COPY . .

# Run the FastAPI app with uvicorn
# --reload enables hot-reloading during development (volume mount)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
