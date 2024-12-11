FROM python:3.9-slim
WORKDIR /app
COPY . .
ENTRYPOINT ["python", "app/upgrade.py"]