FROM python:3.12-slim

WORKDIR /workspaces
RUN pip install --upgrade pip
COPY . psijd
RUN pip install -v --no-cache-dir -r psijd/requirements.txt

EXPOSE 5000

CMD ["fastapi", "run", "--host", "0.0.0.0", "--port", "5000", "psijd/service/app.py"]
