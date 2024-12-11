FROM python:3.9-slim
ADD /app /app
WORKDIR /app

ENV PYTHONPATH /app
ENTRYPOINT ["python", "/app/upgrade.py"]
CMD []