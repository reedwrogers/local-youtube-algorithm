FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir flask flask-cors python-dotenv \
    requests google-api-python-client scikit-learn pandas numpy textblob

EXPOSE 5001

CMD ["python", "run_dashboard.py"]
