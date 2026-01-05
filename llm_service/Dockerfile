FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# poppler-utils is required for pdf2image/pyzerox if used, or fitz sometimes relies on libs
# git might be needed if installing dependencies from git
RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
