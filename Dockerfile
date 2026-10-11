FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /service

RUN addgroup --system app && adduser --system --ingroup app app
COPY pyproject.toml README.md ./
COPY app ./app
COPY resources ./resources
RUN pip install --no-cache-dir .
RUN mkdir -p /service/data && chown -R app:app /service

USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
