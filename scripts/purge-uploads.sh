#!/bin/sh

UPLOADS_PATH=${1:-uploads}

find "$UPLOADS_PATH" -mtime +365 | xargs rm
