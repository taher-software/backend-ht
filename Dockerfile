FROM python:3.10-slim AS bodor_web_app
COPY . /app/
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt



