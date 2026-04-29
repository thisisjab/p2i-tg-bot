FROM python:3.14-alpine

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./

RUN uv pip install --system -r pyproject.toml

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "p2i.main"]
