ARG PYTHON_VERSION=3.12

# Build image: non-slim, in particular to build the mysqlclient wheel
FROM python:${PYTHON_VERSION} AS build

COPY requirements.txt /app/
RUN apt update && apt install -y pkg-config default-libmysqlclient-dev gcc python3-dev \
    && pip install --no-cache-dir -r requirements.txt mysqlclient


# Actual image (based on slim)
FROM python:${PYTHON_VERSION}-slim

# ARGs are not inherited from the build stage; https://stackoverflow.com/a/56748289/339144
ARG WHEEL_FILE
ENV PYTHONUNBUFFERED=1

ENV PORT=8000

WORKDIR /app

# mysqlclient dependencies; needed here too, because the built wheel depends on .o files
RUN apt update && apt install default-libmysqlclient-dev -y

COPY requirements.txt /app/
RUN apt update && apt install -y pkg-config default-libmysqlclient-dev gcc python3-dev \
    && pip install --no-cache-dir -r requirements.txt mysqlclient
RUN --mount=type=cache,target=/var/cache/buildkit/pip \
    pip install "psycopg[binary]"

COPY bugsink/conf_templates/docker.py.template bugsink_conf.py
COPY . /app/
RUN apt update && apt install -y git
RUN pip install -e .
RUN ["bugsink-manage", "migrate", "snappea", "--database=snappea"]

CMD [ "monofy", "bugsink-manage", "check", "--deploy", "--fail-level", "WARNING", "&&", "bugsink-manage", "migrate", "&&", "bugsink-manage", "prestart", "&&", "gunicorn", "--bind=0.0.0.0:$PORT", "--workers=10", "--access-logfile", "-", "bugsink.wsgi", "|||", "bugsink-runsnappea"]
