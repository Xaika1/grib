FROM python:3.12-slim
WORKDIR /demo
RUN pip install --no-cache-dir "psycopg[binary]>=3.2"
COPY generator.py .
CMD ["python", "generator.py", "--url", "postgresql://shop:shop@demo-db/shop"]
