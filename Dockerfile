# syntax=docker/dockerfile:1

FROM python:3.9-alpine

ARG MIDI_IMPL=nomidi

WORKDIR /app

ENV PYTHONPATH "${PYTHONPATH}:/usr/lib/python3.9/site-packages"
ENV MIDI_IMPL "${MIDI_IMPL}"

COPY docker-build.sh .
COPY requirements.txt .

RUN ./docker-build.sh

COPY . .

CMD python3 start.py
