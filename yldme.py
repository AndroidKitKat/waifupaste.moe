#!/usr/bin/env python3

import collections
import itertools
import json
import logging
import os
import time
import socket
import sqlite3
import string
import sys

import tornado.ioloop
import tornado.options
import tornado.web

import pygments
import pygments.lexers
import pygments.formatters
import pygments.styles

# Configuration ----------------------------------------------------------------

YLDME_PRESETS   = [
    ('url'  , 'http://do.yld.me', 'url'),
    ('paste', 'http://do.yld.me', 'url'),
    ('buipj', 'http://cs.uwec.edu/~buipj', 'url'),
    ('base' , 'ALL YOUR BASE ARE BELONG TO US', 'paste'),
]
YLDME_PORT      = 80
YLDME_ADDRESS   = '*'
YLDME_ALPHABET  = string.ascii_letters + string.digits
YLDME_RECENT    = 10
YLDME_MAX_TRIES = 5

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
        value   BLOB NOT NULL UNIQUE
    )
    '''
    SQL_INSERT_DATA   = 'INSERT INTO YldMe (ctime, mtime, type, name, value) VALUES (?, ?, ?, ?, ?)'
    SQL_UPDATE_DATA   = 'UPDATE YldMe SET hits=?,mtime=? WHERE id=?'
    SQL_SELECT_NAME   = 'SELECT * FROM YldMe WHERE name = ?'
    SQL_SELECT_VALUE  = 'SELECT * FROM YldMe WHERE value = ?'
    SQL_SELECT_COUNT  = 'SELECT Count(*) FROM YldMe'
    SQL_SELECT_RECENT = 'SELECT * FROM YldMe ORDER BY ctime DESC LIMIT ?'

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

    def recent(self, limit):
        with self.conn:
            curs = self.conn.cursor()
            return curs.execute(Database.SQL_SELECT_RECENT, (limit,))

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
        if self.get_argument('raw', '').lower() in TRUE_STRINGS:
            self.set_header('Content-Type', 'text/plain')
            self.write(data.value)
            return

        lexer   = pygments.lexers.guess_lexer(data.value)
        linenos = self.get_argument('linenos', 'table')
        style   = self.get_argument('style', 'colorful')
        try:
            formatter = pygments.formatters.HtmlFormatter(full=True, linenos=linenos, style=style)
        except pygments.ClassNotFound:
            formatter = pygments.formatters.HtmlFormatter(full=True, linenos=linenos)

        self.write(pygments.highlight(data.value, lexer, formatter))

    def _index(self):
        limit = self.get_argument('recent', YLDME_RECENT)
        self.render('index.tmpl', **{'recent': self.application.database.recent(limit), 'time': time})

    def post(self, type=None):
        value = self.request.body.decode('utf-8')
        data  = self.application.database.lookup(value)
        tries = 0

        while data is None and tries < YLDME_MAX_TRIES:
            tries = tries + 1

            try:
                name = self.application.generate_name()
                self.application.database.add(name, value, type)
                data = self.application.database.get(name)
            except (sqlite3.OperationalError, sqlite3.IntegrityError):
                continue

        if tries >= YLDME_MAX_TRIES:
            raise tornado.web.HTTPError(500, 'Could not produce new database entry')

        self.write(json.dumps({
            'name' : data.name,
            'type' : data.type,
            'value': data.value,
            'ctime': data.ctime,
            'mtime': data.mtime,
            'hits' : data.hits,
        }))

# Application ------------------------------------------------------------------

class YldMeApplication(tornado.web.Application):

    def __init__(self, **settings):
        tornado.web.Application.__init__(self, **settings)

        self.logger   = logging.getLogger()
        self.address  = settings.get('address', YLDME_ADDRESS)
        self.port     = settings.get('port', YLDME_PORT)
        self.ioloop   = tornado.ioloop.IOLoop.instance()
        self.database = Database()
        self.counter  = itertools.count(self.database.count())

        self.add_handlers('', [
                (r'.*/(.*)', YldMeHandler),
        ])

    def generate_name(self):
        return integer_to_identifier(next(self.counter))

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
