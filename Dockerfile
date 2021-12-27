ARG PYTHON_VERSION=3.7
FROM python:${PYTHON_VERSION}-slim-buster AS build

WORKDIR /usr/src

RUN \
  mkdir -p \
    /home/.cache \
    /venv \
  && \
  chmod -R a+rw \
    /home/.cache \
    /usr/src \
    /venv \
  ;
  # && \
  # chown -R 1000 \
  #   /home/.cache \
  #   /usr/src \
  #   /venv \

ENV PATH=/venv/bin:$PATH
ENV PYTHONPATH=/venv
ENV HOME=/home

USER 1000

COPY poetry.lock pyproject.toml ./
RUN touch pinboard_archiver.py
COPY pip.conf /etc/
RUN --mount=type=cache,uid=1000,target=/home/.cache pip download . poetry-core
RUN --mount=type=cache,uid=1000,target=/home/.cache pip install --no-index --find-links=/home/.cache/packages --target /venv .
COPY --chown=1000 *.py ./
RUN --mount=type=cache,uid=1000,target=/home/.cache pip install --no-index --find-links=/home/.cache/packages --target /venv --upgrade .
RUN false

# Distroless don't currently have version tags
FROM gcr.io/distroless/python3-root/debian10:debug@sha256:1bc65c2e05156ee7ac2d3819d425591c4ebbc459d57a27c36fba38ea08019fae AS prod

USER 1000

COPY --from=build /venv /venv
ENV PATH=/venv/bin:$PATH
ENV PYTHONPATH=/venv

ENTRYPOINT ["python3", "-m", "grafana_consumer"]
