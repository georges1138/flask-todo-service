FROM python:3.12-slim

WORKDIR /service

RUN pip install --no-cache-dir Flask

COPY . .

EXPOSE 4000

CMD ["python", "app.py"]
