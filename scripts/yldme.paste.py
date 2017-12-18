#!/usr/bin/env python3

import subprocess
import sys

import tornado.httpclient

PASTE_URL  = 'https://yld.me/paste'

httpclient = tornado.httpclient.HTTPClient()
request    = tornado.httpclient.HTTPRequest(url=PASTE_URL, method='POST', body=sys.stdin.read())
response   = httpclient.fetch(request)
shorturl   = response.body

try:
    subprocess.Popen(['xclip'], stdin=subprocess.PIPE).communicate(shorturl.encode('utf-8'))
except OSError:
    pass

print(shorturl)
