FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Skill bundle is mounted by Compose; Codex CLI must be installed/authenticated on the worker host.
RUN useradd --create-home app && mkdir -p /data/materials && chown -R app:app /app /data/materials
USER app
