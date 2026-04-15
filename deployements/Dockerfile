FROM python:3.11-slim-bookworm AS bodor_web_app
COPY . /app/
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt
ENV ENV_FILE=./.envprod
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

#CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", $PORT]
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port $PORT"]