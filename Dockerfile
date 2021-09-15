# syntax=docker/dockerfile:1

FROM python:3.9-alpine

WORKDIR /app

ENV PYTHONPATH "${PYTHONPATH}:/usr/lib/python3.9/site-packages"

# build PyNaCl if not installed already
# this takes a long time so a dirty workaround is used instead ;v
# RUN python3 -m nacl.secret || (apk add --no-cache --virtual .pynacl_deps build-base python3-dev libffi-dev && pip install pynacl && apk del .pynacl_deps)

# install dependencies
RUN apk add py3-aiohttp py3-pynacl libmagic ffmpeg fluidsynth
# rename cffi native library because python on alpine sucks
RUN mv /usr/lib/python3.9/site-packages/_cffi_backend* /usr/lib/python3.9/site-packages/_cffi_backend.so

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD python3 start.py
