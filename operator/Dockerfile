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

# Create operator user and set permissions
RUN groupadd -r operator || true
RUN useradd -r -g operator -m -d /home/operator operator || true
RUN chown -R operator:operator /app

# Switch to operator user
USER operator

# Set up Modal CLI environment
ENV PATH="/home/operator/.local/bin:${PATH}"
ENV MODAL_CONFIG_PATH="/home/operator/.modal"

# Create Modal config directory
RUN mkdir -p /home/operator/.modal

# Health check to ensure Modal is working
RUN python -c "import modal; app = modal.App('health-check'); print('Modal CLI ready')"

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
