FROM python:3.11-slim AS bodor_web_app
COPY . /app/
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt
ENV ENV_FILE=./.envprod

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]