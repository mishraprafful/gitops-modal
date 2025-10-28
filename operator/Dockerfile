FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy operator code
COPY . .

# Run as non-root user
RUN groupadd -r operator && useradd -r -g operator operator
RUN chown -R operator:operator /app
USER operator

CMD ["python", "main.py"]
