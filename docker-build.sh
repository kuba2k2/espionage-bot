#!/bin/sh

# build PyNaCl if not installed already
# this takes a long time so a dirty workaround is used instead ;v
# python3 -m nacl.secret || (apk add --no-cache --virtual .pynacl_deps build-base python3-dev libffi-dev && pip install pynacl && apk del .pynacl_deps)

# install dependencies
apk add py3-aiohttp py3-pynacl libmagic ffmpeg
# rename cffi native library because python on alpine sucks
mv /usr/lib/python3.9/site-packages/_cffi_backend* /usr/lib/python3.9/site-packages/_cffi_backend.so

# install pip project dependencies
pip3 install -r requirements.txt

if [ "$MIDI_IMPL" == "fluidsynth" ]; then
    apk add fluidsynth
elif [ "$MIDI_IMPL" == "timidity" ]; then
    apk add --no-cache --virtual .timidity_deps build-base linux-headers
    URL="http://downloads.sourceforge.net/project/timidity/TiMidity++/TiMidity++-2.15.0/TiMidity++-2.15.0.tar.xz"
    cd /tmp
    wget -O - $URL | tar -xJvf -
    cd TiMidity\+\+-2.15.0/
    ./configure
    make
    make install
    apk del .timidity_deps
fi

cd /app
