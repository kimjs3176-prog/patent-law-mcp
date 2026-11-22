# 국가직무발명특허권등 업무 보조 도구 (patent-law-mcp) — 원격(HTTP) 배포용 이미지
#   docker build -t patent-law-mcp .
#   docker run -p 8000:8000 -e PATENT_LAW_MCP_TOKEN=... -e KIPRIS_API_KEY=... patent-law-mcp \
#     --allowed-host mcp.example.org
FROM python:3.12-slim
LABEL org.opencontainers.image.title="국가직무발명특허권등 업무 보조 도구" \
      org.opencontainers.image.source="https://github.com/kimjs3176-prog/patent-law-mcp"

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --create-home mcp
USER mcp

ENV PATENT_LAW_MCP_CACHE=/home/mcp/.cache/patent-law-mcp/cache.sqlite3
EXPOSE 8000
ENTRYPOINT ["patent-law-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
