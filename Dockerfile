ARG PYTHON_VERSION=3.8
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

ENV PATH=/venv/bin:$PATH
ENV PYTHONPATH=/venv
ENV HOME=/home
RUN pip install poetry-core

USER 1000

COPY poetry.lock pyproject.toml ./
RUN touch pinboard_archiver.py
RUN --mount=type=cache,uid=1000,target=/home/.cache pip -v install --no-build-isolation --target /venv .
COPY --chown=1000 *.py ./
RUN --mount=type=cache,uid=1000,target=/home/.cache pip -v install --no-build-isolation --target /venv --upgrade .

# Distroless don't currently have version tags
FROM gcr.io/distroless/python3-debian10:debug@sha256:396827c703e8f43f6483d2e723592ea3bfaeafc5d327bcfca9cddaed74ead3cf

COPY --from=build /venv /venv
ENV PATH=/venv/bin:$PATH
ENV PYTHONPATH=/venv

ENTRYPOINT ["pinboard-archiver"]
