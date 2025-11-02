FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN pip install --no-cache-dir uv

# Install Python dependencies using uv
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Verify Modal CLI is available
RUN python -c "import modal; print('Modal package installed successfully')"

# Copy operator code
COPY . .

# Run tests to ensure code quality (fail build if tests fail)
RUN echo "Running test_modal.py..." && \
    python test_modal.py && \
    echo "✅ All tests passed!"

# Create operator user and set permissions
RUN groupadd -r operator || true
RUN useradd -r -g operator -m -d /home/operator -u 1000 -s /bin/bash operator || true
RUN chown -R operator:operator /app

# Switch to operator user
USER operator

# Set USER environment variable for getpass.getuser() compatibility
ENV USER=operator
ENV HOME=/home/operator

# Set up Modal CLI environment
ENV PATH="/home/operator/.local/bin:${PATH}"

# Create Modal config directory (Modal will use default location ~/.modal/)
RUN mkdir -p /home/operator/.modal

# Health check to ensure Modal package can be imported
# Note: Full Modal functionality requires credentials configured at runtime
RUN python -c "import modal; print('Modal package imported successfully')"

# Create startup script that uses uv
RUN echo '#!/bin/bash\n\
echo "Setting up Modal GitOps Operator..."\n\
uv run setup_modal.py\n\
if [ $? -eq 0 ]; then\n\
    echo "Starting operator..."\n\
    exec uv run main.py\n\
else\n\
    echo "Setup failed, exiting..."\n\
    exit 1\n\
fi' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]
