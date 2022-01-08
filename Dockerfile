ARG PYTHON_VERSION=3.9
FROM python:${PYTHON_VERSION}-slim-bullseye AS build

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

ENV PATH=/venv/bin:$PATH
ENV PYTHONPATH=/venv
ENV HOME=/home
RUN pip install poetry-core

USER 1000

COPY poetry.lock pyproject.toml ./
RUN touch pinboard_archiver.py
RUN --mount=type=cache,uid=1000,target=/home/.cache pip -v install --no-build-isolation --target /venv .
COPY --chown=1000 *.py *.capnp ./
RUN --mount=type=cache,uid=1000,target=/home/.cache pip -v install --no-build-isolation --target /venv --upgrade .

# Distroless don't currently have version tags
FROM gcr.io/distroless/python3-debian11:debug@sha256:a401f50d892a2d5bf067182f5d1d94f84375d92ea3b50e8ede613d5da2d91d86

COPY --from=build /venv /venv
ENV PATH=/venv/bin:$PATH
ENV PYTHONPATH=/venv

ENTRYPOINT ["pinboard-archiver"]
