FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -e .[dev]

ENTRYPOINT ["momo"]
CMD ["version"]


