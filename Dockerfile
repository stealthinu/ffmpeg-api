FROM python:3.12-slim

RUN apt-get update && \
   apt-get install -y ffmpeg && \
   rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ /app/src/

EXPOSE 5000

CMD ["python", "-m", "src.app"]
