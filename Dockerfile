FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create models dir for artifact storage
RUN mkdir -p models

EXPOSE 8000

# Start the API server serving the pre-trained model
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
