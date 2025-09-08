FROM python:3.10-slim-bookworm
COPY --from=docker.io/astral/uv:latest /uv /uvx /bin/

WORKDIR /app

ENTRYPOINT /bin/uv
CMD ["geocruncher_api.api:app"]
