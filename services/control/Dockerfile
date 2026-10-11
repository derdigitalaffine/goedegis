FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends gdal-bin ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/goedegis
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
