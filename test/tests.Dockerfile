ARG PYTHON_VERSION

FROM python:${PYTHON_VERSION}

WORKDIR /repo

# install app requirements
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# install dev/test requirements
COPY requirements_dev.txt requirements_dev.txt
RUN pip install -r requirements_dev.txt

COPY ./test ./test
COPY ./homely ./homely

RUN PYTHONPATH=. pytest test -x
