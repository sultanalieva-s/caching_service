# setup python
FROM python:3.14-slim

# for getting errors
ENV PYTHONUNBUFFERED=1

# install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# setup working directory
WORKDIR /app

# install required packages
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# copy uv files
COPY pyproject.toml uv.lock README.md /app/

# install dependencies via uv
RUN PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/usr/local uv sync --frozen --no-cache --all-extras --all-groups --no-install-project

# copy application source code to the app working directory
COPY . /app/

# Expose the port FastAPI will run on
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]