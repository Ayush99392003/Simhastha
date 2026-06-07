# Use the official Python image
FROM python:3.11-slim

# Create a non-root user required by Hugging Face Spaces
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Set the working directory
WORKDIR /app

# Install uv for fast dependency management
RUN pip install --user uv

# Copy the application files
COPY --chown=user . /app

# Install dependencies using uv
RUN uv sync --frozen

# Hugging Face Spaces expose port 7860 by default
EXPOSE 7860
ENV PORT=7860

# Run the pipeline orchestrator
CMD ["uv", "run", "pipeline.py"]
