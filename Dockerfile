FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/brawlbuddy
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home brawlbuddy \
    && mkdir -p /var/lib/brawlbuddy \
    && chown brawlbuddy:brawlbuddy /var/lib/brawlbuddy
COPY app ./app
COPY config ./config
COPY data ./data
USER brawlbuddy
EXPOSE 8000
CMD ["python", "-m", "app"]
