FROM python:3.12-slim

RUN apt update && apt install -y --no-install-recommends curl procps \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
RUN pip install --upgrade pip
COPY . /opt/psijd
RUN pip install -v --no-cache-dir -r psijd/requirements.txt

EXPOSE 5000

CMD ["fastapi", "dev", "--host", "0.0.0.0", "--port", "5000", "psijd/service/app.py"]
