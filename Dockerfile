FROM python:3.12-slim-bookworm
WORKDIR /app

COPY pyproject.toml ./
RUN pip install uv 
RUN pip install uvicorn
RUN uv sync

COPY src ./src/
RUN uv sync

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
