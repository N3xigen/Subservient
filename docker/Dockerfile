FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    mkvtoolnix \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all Subservient files
COPY *.py ./
COPY data/ ./data/

# Create initialization script for Docker environment
RUN echo '#!/bin/bash\n\
# Initialize Subservient paths for Docker environment\n\
mkdir -p /root/.config/Subservient\n\
cat > /root/.config/Subservient/Subservient_pathfiles << EOF\n\
subservient_anchor=/app\n\
subordinate_path=/app/subordinate.py\n\
extraction_path=/app/extraction.py\n\
acquisition_path=/app/acquisition.py\n\
synchronisation_path=/app/synchronisation.py\n\
utils_path=/app/utils.py\n\
EOF\n\
\n\
# Create .config directory in anchor path (required by get_subservient_folder)\n\
mkdir -p /app/.config\n\
\n\
# Execute the original command\n\
exec "$@"\n\
' > /app/docker-init.sh && chmod +x /app/docker-init.sh

# Create volumes for movies, config, and logs
VOLUME ["/movies", "/config", "/logs"]

# Set environment variables
ENV PYTHONPATH=/app
ENV TERM=xterm

# Start interactive bash shell with initialization
ENTRYPOINT ["/app/docker-init.sh"]
CMD ["/bin/bash"]
