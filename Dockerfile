FROM python:3.9-slim
ADD /app /app
WORKDIR /app

ENV PYTHONPATH /app
CMD ["/app/upgrade.py"]