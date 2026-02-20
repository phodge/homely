ARG PYTHON_VERSION

FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-alpine

# git executable is required for many tests
RUN apk add git

WORKDIR /repo

# Pull in minimum number of project files required for installing dependencies
# so that the cached layer containing dependency installation isn't invalidated
# by other source code changes.
RUN mkdir homely
COPY homely/__init__.py ./homely/
COPY pyproject.toml ./
COPY uv.lock ./
RUN uv venv .venv && uv pip install -e . --group=dev

COPY ./test ./test
COPY ./homely ./homely

RUN .venv/bin/pytest -W error test -x

RUN .venv/bin/mypy homely test
