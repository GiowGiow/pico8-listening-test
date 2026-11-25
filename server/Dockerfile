FROM python:3.8-slim

WORKDIR /app

COPY . .

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY certs/cert.pem certs/key.pem /app/certs/

ENV FLASK_APP=app.server
ENV FLASK_ENV=HML
ENV FLASK_RUN_CERT=/app/certs/cert.pem
ENV FLASK_RUN_KEY=/app/certs/key.pem

EXPOSE 5000

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]