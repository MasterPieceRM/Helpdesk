FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV POSTGRES_HOST=db
ENV POSTGRES_USER=helpdesk
ENV POSTGRES_PASSWORD=helpdesk
ENV POSTGRES_DB=helpdesk

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
