#!/usr/bin/env python3

import subprocess
import sys

import requests

DYM_URL       = 'http://do.yld.me'
DYM_PASTE_URL = DYM_URL + '/paste'

result   = requests.post(DYM_PASTE_URL, data=sys.stdin.read())
shorturl = '{}/{}'.format(DYM_URL, result.json()['name'])

subprocess.Popen(['xclip'], stdin=subprocess.PIPE).communicate(shorturl.encode('utf-8'))
print(shorturl)
