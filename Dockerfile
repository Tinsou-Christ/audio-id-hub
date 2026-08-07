FROM python:3.11-slim

WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py gunicorn.conf.py ./
COPY shazamapi ./shazamapi

ENV PYTHONUNBUFFERED=1
ENV PORT=10000
EXPOSE 10000
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
