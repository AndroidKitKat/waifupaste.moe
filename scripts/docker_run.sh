#!/bin/sh

exec 2>&1
exec docker run --name="yldme" \
    --init \
    -v $HOME/.config/yldme:/var/lib/yldme \
    -p 9515:9515 \
    pbui/yldme
