# Pyttai - AI-Native Terminal
FROM python:3.11-slim AS deps

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    vim \
    xclip \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM deps AS final

COPY main.py .
COPY lmchat/ ./lmchat/

RUN mkdir -p /home/pyttai/.pyttai
COPY config.json /home/pyttai/.pyttai/config.json

COPY scripts/ /scripts

RUN mkdir -p /workspace /sessions /data /logs /config

# Create non-root user
RUN useradd -m -s /bin/bash pyttai && \
    chown -R pyttai:pyttai /workspace /sessions &&\
    chown -R pyttai:pyttai /data /logs /config /home/pyttai

# Set up volume mount points
VOLUME ["/sessions", "/data", "/logs", "/config"]

# Default to workspace directory
WORKDIR /workspace

# Switch to non-root user
USER pyttai

# Environment setup
ENV PYTHONUNBUFFERED=1
ENV PYTTAI_CONTAINER=1

# Default command
CMD ["/bin/bash", "/scripts/entrypoint.sh"]

# docker run -it --rm -v ./my-project:/data:ro <IMAGE_LABEL>

# For SSH mode (future)
# EXPOSE 22
# CMD ["/usr/sbin/sshd", "-D"]