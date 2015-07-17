#!/usr/bin/env python2.7

import json
import subprocess
import sys

import tornado.httpclient

DYM_URL       = 'http://do.yld.me'
DYM_PASTE_URL = DYM_URL + '/paste'

httpclient = tornado.httpclient.HTTPClient()
request    = tornado.httpclient.HTTPRequest(url=DYM_PASTE_URL, method='POST', body=sys.stdin.read())
response   = httpclient.fetch(request)
data       = json.loads(response.body)
shorturl   = '{}/{}'.format(DYM_URL, data['name'])

try:
    subprocess.Popen(['xclip'], stdin=subprocess.PIPE).communicate(shorturl.encode('utf-8'))
except OSError:
    pass

print(shorturl)
