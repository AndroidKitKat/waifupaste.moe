#!/usr/bin/env python2.7

import collections
import glob
import hashlib
import logging
import os
import random
import socket
import sqlite3
import string
import subprocess
import sys
import time

import tornado.ioloop
import tornado.options
import tornado.web

import pygments
import pygments.lexers
import pygments.formatters
import pygments.styles
import pygments.util

# Configuration ----------------------------------------------------------------

YLDME_PRESETS   = [
    ('url'              , 'http://yld.me', 'url'),
    ('paste'            , 'http://yld.me', 'url'),
    ('pbui'             , 'http://www3.nd.edu/~pbui', 'url'),
    ('cdt-30010-fa15'   , 'https://www3.nd.edu/~pbui/teaching/cdt.30010.fa15/', 'url'),
    ('cdt-30020-sp16'   , 'https://www3.nd.edu/~pbui/teaching/cdt.30020.sp16/', 'url'),
    ('cse-20189-sp16'   , 'https://www3.nd.edu/~pbui/teaching/cse.20189.sp16/', 'url'),
    ('cse-40175-sp16'   , 'https://www3.nd.edu/~pbui/teaching/cse.40175.sp16/', 'url'),
    ('cdt-30010-fa16'   , 'https://www3.nd.edu/~pbui/teaching/cdt.30010.fa16/', 'url'),
    ('cse-30331-fa16'   , 'https://www3.nd.edu/~pbui/teaching/cse.30331.fa16/', 'url'),
    ('cse-40175-fa16'   , 'https://www3.nd.edu/~pbui/teaching/cse.40175.fa16/', 'url'),
    ('cse-40175-sp17'   , 'https://www3.nd.edu/~pbui/teaching/cse.40175.sp17/', 'url'),
    ('cse-40842-sp17'   , 'https://www3.nd.edu/~pbui/teaching/cse.40842.sp17/', 'url'),
    ('cse-20289-sp17'   , 'https://www3.nd.edu/~pbui/teaching/cse.20289.sp17/', 'url'),
    ('cse-30341-fa17'   , 'https://www3.nd.edu/~pbui/teaching/cse.30341.fa17/', 'url'),
    ('cse-30872-fa17'   , 'https://www3.nd.edu/~pbui/teaching/cse.30872.fa17/', 'url'),
    ('cse-40175-fa17'   , 'https://www3.nd.edu/~pbui/teaching/cse.40175.fa17/', 'url'),
    ('pbc-su17'         , 'https://www3.nd.edu/~pbui/teaching/pbc.su17/'      , 'url'),
]
YLDME_URL       = 'http://yld.me'
YLDME_PORT      = 9515
YLDME_ADDRESS   = '127.0.0.1'
YLDME_ALPHABET  = string.ascii_letters + string.digits
YLDME_MAX_TRIES = 10
YLDME_ASSETS    = os.path.join(os.path.dirname(__file__), 'assets')
YLDME_STYLES    = os.path.join(YLDME_ASSETS, 'css', 'pygments')
YLDME_UPLOADS   = os.path.join(os.path.dirname(__file__), 'uploads')

# Constants --------------------------------------------------------------------

TRUE_STRINGS = ('1', 'true', 'on', 'yes')

# Utilities --------------------------------------------------------------------

def make_parent_directories(path):
    dirname = os.path.dirname(path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)


def integer_to_identifier(integer, alphabet=YLDME_ALPHABET):
    ''' Returns a string given an integer identifier '''
    identifier = ''
    number     = int(integer)
    length     = len(alphabet)

    while number >= length:
        quotient, remainder = divmod(number, length)
        identifier = alphabet[remainder] + identifier
        number     = quotient - 1

    identifier = alphabet[number] + identifier
    return identifier


def checksum(data):
    return hashlib.sha1(data).hexdigest()


def determine_mimetype(path):
    try:
        result = subprocess.check_output(['file', '--mime-type', path])
    except subprocess.CalledProcessError:
        result = '{}: text/plain'.format(path)

    return result.split(':', 1)[-1].strip()

# Database ---------------------------------------------------------------------

YldMeTupleFields = 'id ctime mtime hits type name value'.split()
YldMeTuple       = collections.namedtuple('YldMeTuple', YldMeTupleFields)

def DatabaseRowFactory(cursor, row):
    if len(row) == len(YldMeTupleFields):
        return YldMeTuple(*row)
    else:
        return row

class Database(object):

    DEFAULT_PATH = os.path.expanduser('~/.config/yldme/db')

    SQL_CREATE_TABLE = '''
    CREATE TABLE IF NOT EXISTS YldMe (
        id      INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        ctime   INTEGER NOT NULL,
        mtime   INTEGER NOT NULL,
        hits    INTEGER NOT NULL DEFAULT 0,
        type    TEXT NOT NULL CHECK (type IN ('paste','url')) DEFAULT 'url',
        name    TEXT NOT NULL UNIQUE,
        value   TEXT NOT NULL UNIQUE
    )
    '''
    SQL_INSERT_DATA   = 'INSERT INTO YldMe (ctime, mtime, type, name, value) VALUES (?, ?, ?, ?, ?)'
    SQL_UPDATE_DATA   = 'UPDATE YldMe SET hits=?,mtime=? WHERE id=?'
    SQL_SELECT_NAME   = 'SELECT * FROM YldMe WHERE name = ?'
    SQL_SELECT_VALUE  = 'SELECT * FROM YldMe WHERE value = ?'
    SQL_SELECT_COUNT  = 'SELECT Count(*) FROM YldMe'

    def __init__(self, path=None):
        self.path = path or Database.DEFAULT_PATH

        if not os.path.exists(self.path):
            make_parent_directories(self.path)

        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = DatabaseRowFactory

        with self.conn:
            curs = self.conn.cursor()
            curs.execute(Database.SQL_CREATE_TABLE)

        for name, value, type in YLDME_PRESETS:
            try:
                self.add(name, value, type)
            except sqlite3.IntegrityError:
                pass

    def add(self, name, value, type=None):
        type = type or 'url'
        with self.conn:
            data = (
                int(time.time()),
                int(time.time()),
                type,
                name,
                value,
            )
            curs = self.conn.cursor()
            curs.execute(Database.SQL_INSERT_DATA, data)

    def get(self, name):
        with self.conn:
            curs = self.conn.cursor()
            curs.execute(Database.SQL_SELECT_NAME, (name,))
            return curs.fetchone()

    def hit(self, name):
        data = self.get(name)
        with self.conn:
            curs = self.conn.cursor()
            curs.execute(Database.SQL_UPDATE_DATA, (data.hits + 1, int(time.time()), data.id))

    def lookup(self, value):
        with self.conn:
            curs = self.conn.cursor()
            curs.execute(Database.SQL_SELECT_VALUE, (value,))
            return curs.fetchone()

    def count(self):
        with self.conn:
            curs = self.conn.cursor()
            curs.execute(Database.SQL_SELECT_COUNT)
            return int(curs.fetchone()[0])

# Handlers ---------------------------------------------------------------------

class YldMeHandler(tornado.web.RequestHandler):

    def get(self, name=None):
        if name is None:
            return self._index()

        data = self.application.database.get(name)
        if data is None:
            return self._index()

        self.application.database.hit(name)

        if data.type == 'url':
            self._get_url(name, data)
        else:
            self._get_paste(name, data)

    def _get_url(self, name, data):
        self.redirect(data.value)

    def _get_paste(self, name, data):
        file_path = os.path.join(YLDME_UPLOADS, name)
        file_data = open(file_path, 'rb').read()
        file_mime = determine_mimetype(file_path)

        if self.get_argument('raw', '').lower() in TRUE_STRINGS:
            self.set_header('Content-Type', file_mime)
            self.write(file_data)
            return

        style   = self.get_argument('style', 'default')
        linenos = self.get_argument('linenos', False)

        if 'text/' in file_mime or 'message/' in file_mime:
            try:
                lexer = pygments.lexers.guess_lexer(file_data)
            except pygments.util.ClassNotFound:
                lexer = pygments.lexers.get_lexer_for_mimetype('text/plain')

            formatter = pygments.formatters.HtmlFormatter(cssclass='hll', linenos=linenos, style=style)
            file_html = pygments.highlight(file_data, lexer, formatter)
        elif 'image/' in file_mime:
            file_html = '<div class="thumbnail"><img src="/{}?raw=1" class="img-responsive"></div>'.format(name)
        else:
            file_html = '''
<div class="btn-toolbar" style="text-align: center">
    <a href="/{}?raw=1" class="btn btn-primary"><i class="fa fa-download"></i> Download</a>
</div>
'''.format(name)

        self.render('paste.tmpl', **{
            'name'      : name,
            'file_html' : file_html,
            'pygment'   : style,
            'styles'    : self.application.styles,
        })

    def _index(self):
        self.render('index.tmpl')

    def post(self, type=None):
        value = self.request.body
        if type == 'url':
            value_hash = value
        else:
            value_hash = checksum(value)
        data  = self.application.database.lookup(value_hash)
        tries = 0

        while data is None and tries < YLDME_MAX_TRIES:
            tries = tries + 1

            try:
                name = self.application.generate_name()
                self.application.database.add(name, value_hash, type)
                if type != 'url':
                    with open(os.path.join(YLDME_UPLOADS, name), 'wb+') as fs:
                        fs.write(value)
                data = self.application.database.get(name)
            except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
                self.application.logger.warn(e)
                self.application.logger.info('name: %s', name)
                continue

        if tries >= YLDME_MAX_TRIES:
            raise tornado.web.HTTPError(500, 'Could not produce new database entry')

        self.write('{}/{}\n'.format(YLDME_URL, data.name))

# Application ------------------------------------------------------------------

class YldMeApplication(tornado.web.Application):

    def __init__(self, **settings):
        tornado.web.Application.__init__(self, **settings)

        self.logger   = logging.getLogger()
        self.address  = settings.get('address', YLDME_ADDRESS)
        self.port     = settings.get('port', YLDME_PORT)
        self.ioloop   = tornado.ioloop.IOLoop.instance()
        self.database = Database()
        self.styles   = [os.path.basename(path)[:-4] for path in sorted(glob.glob(os.path.join(YLDME_STYLES, '*.css')))]

        self.add_handlers('.*', [
                (r'.*/assets/(.*)', tornado.web.StaticFileHandler, {'path': YLDME_ASSETS}),
                (r'.*/(.*)'       , YldMeHandler),
        ])

    def generate_name(self):
        return integer_to_identifier(random.randrange(self.database.count()*10))

    def run(self):
        try:
            self.listen(self.port, self.address)
        except socket.error as e:
            self.logger.fatal('Unable to listen on {}:{} = {}'.format(self.address, self.port, e))
            sys.exit(1)

        self.ioloop.start()

# Main execution ---------------------------------------------------------------

if __name__ == '__main__':
    tornado.options.define('debug', default=False, help='Enable debugging mode.')
    tornado.options.define('port', default=YLDME_PORT, help='Port to listen on.')
    tornado.options.define('template_path', default=os.path.join(os.path.dirname(__file__), "templates"), help='Path to templates')
    tornado.options.parse_command_line()

    options = tornado.options.options.as_dict()
    yldme   = YldMeApplication(**options)
    yldme.run()

# vim: sts=4 sw=4 ts=8 expandtab ft=python
