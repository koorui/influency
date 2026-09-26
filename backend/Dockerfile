FROM node:22.16.0-bookworm-slim AS codex
ARG CODEX_VERSION=0.156.1
RUN npm install --global @openai/codex@${CODEX_VERSION}

FROM python:3.12.14-slim-bookworm
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::https::Timeout=30 -o Acquire::Retries=3 update \
    && apt-get -o Acquire::https::Timeout=30 -o Acquire::Retries=3 install --no-install-recommends -y ca-certificates git ripgrep libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=codex /usr/local/bin/node /usr/local/bin/node
COPY --from=codex /usr/local/lib/node_modules/@openai /usr/local/lib/node_modules/@openai
RUN ln -s /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 CODEX_HOME=/home/app/.codex
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY skills/ /app/skills/
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data/materials /home/app/.codex \
    && chown -R app:app /app /data/materials /home/app/.codex
USER app
ENTRYPOINT ["python", "-m", "app.container_entrypoint"]
