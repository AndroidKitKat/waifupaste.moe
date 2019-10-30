#!/usr/bin/env python3

import os
import sys

sys.path.append(os.curdir)

import sqlite3
import yldme

db = yldme.Database(os.path.expanduser('~/.config/yldme/db'))

paste_name = sys.argv[1]
paste_path = sys.argv[2]
paste_hash = yldme.checksum(open(paste_path, 'rb').read())

db.add(paste_name, paste_hash, 'paste')
