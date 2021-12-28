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

USER 1000

COPY poetry.lock pyproject.toml *.py ./
RUN pip install --target /venv .
RUN false
