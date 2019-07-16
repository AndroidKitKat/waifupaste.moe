#!/usr/bin/env python3

import os
import sys

sys.path.append(os.curdir)

import sqlite3
import yldme

db = yldme.Database(os.path.expanduser('/home/akk/.config/yldme/db'))
db.add('faq','1','faq')
# for name, value, type in yldme.YLDME_PRESETS:
#     try:
#         print(name, value, type)
#         db.add(name, value, type)
#     except sqlite3.IntegrityError:
#         pass

