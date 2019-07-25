#!/bin/sh

exec docker run --name="yldme" \
    -v /pub/data/yldme:/var/lib/yldme \
    -p 20010:9515 \
    pbui/yldme
