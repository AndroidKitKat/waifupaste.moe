#!/usr/bin/env python3

import collections
import glob
import hashlib
import logging
import mimetypes
import os
import random
import socket
import sqlite3
import string
import subprocess
import sys
import time
import yaml

import tornado.ioloop
import tornado.options
import tornado.web

import pygments
import pygments.lexers
import pygments.formatters
import pygments.styles
import pygments.util

# Constants

YLDME_ADDRESS   = '127.0.0.1'
YLDME_PORT      = 9515
TRUE_STRINGS    = ('1', 'true', 'on', 'yes')

MIME_TYPES = {
    'image/jpeg': '.jpg',
    'image/png' : '.png',
    'video/mp4' : '.mp4',
    'text/plain': '.txt',
}

# Utilities

def make_parent_directories(path):
    dirname = os.path.dirname(path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

def integer_to_identifier(integer, alphabet):
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

    return result.decode('utf8').split(':', 1)[-1].strip()


def guess_extension(mime_type):
    return (MIME_TYPES.get(mime_type)
            or mimetypes.guess_extension(mime_type)
            or '.txt')

# Database

YldMeTupleFields = 'id ctime mtime hits type name value'.split()
YldMeTuple       = collections.namedtuple('YldMeTuple', YldMeTupleFields)

def DatabaseRowFactory(cursor, row):
    if len(row) == len(YldMeTupleFields):
        return YldMeTuple(*row)
    else:
        return row

class Database(object):

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

    def __init__(self, path=None, presets=[]):
        self.path = path

        if not os.path.exists(self.path):
            make_parent_directories(self.path)

        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = DatabaseRowFactory

        with self.conn:
            curs = self.conn.cursor()
            curs.execute(Database.SQL_CREATE_TABLE)

        for preset in presets:
            try:
                self.add(preset['name'], preset['link'], 'url')
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

# Handlers

class YldMeHandler(tornado.web.RequestHandler):

    def get(self, name=None):
        if name is None:
            return self._index()

        name = name.split('.')[0]
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
        file_path = os.path.join(self.application.uploads_dir, name)
        try:
            file_data = open(file_path, 'rb').read()
        except (OSError, IOError):
            raise tornado.web.HTTPError(410, 'Upload has been removed')

        file_mime = determine_mimetype(file_path)
        file_ext  = guess_extension(file_mime)

        if self.get_argument('raw', '').lower() in TRUE_STRINGS:
            self.set_header('Content-Type', file_mime)
            self.write(file_data)
            return

        style   = self.get_argument('style', 'default')
        linenos = self.get_argument('linenos', False)

        if 'text/' in file_mime or 'message/' in file_mime:
            try:
                lexer = pygments.lexers.guess_lexer(file_data.decode('utf8'))
            except pygments.util.ClassNotFound:
                lexer = pygments.lexers.get_lexer_for_mimetype('text/plain')

            formatter = pygments.formatters.HtmlFormatter(cssclass='hll', linenos=linenos, style=style)
            file_html = pygments.highlight(file_data, lexer, formatter)
        elif 'image/' in file_mime:
            file_html = '<div class="thumbnail text-center"><img src="/raw/{}" class="img-responsive"></div>'.format(name)
        elif 'video/' in file_mime:
            file_html = '<div class="thumbnail text-center"><video controls><source src="/raw/{}" type="{}" class="embed-responsive"></video></div>'.format(name, file_mime)
        else:
            file_html = '''
<div class="btn-toolbar" style="text-align: center">
    <a href="/raw/{}{}" class="btn btn-primary"><i class="fa fa-download"></i> Download</a>
</div>
'''.format(name, file_ext)

        self.render('paste.tmpl', **{
            'name'      : name,
            'file_html' : file_html,
            'file_ext'  : file_ext,
            'mime_type' : file_mime,
            'pygment'   : style,
            'styles'    : self.application.styles,
        })

    def _index(self):
        self.render('index.tmpl')

    def post(self, type=None):
        if 'source' in self.request.files:
            use_template = True
            value        = self.request.files['source'][0].body
        else:
            use_template = False
            value        = self.request.body

        if type == 'url':
            value_hash = value
        elif type == 'paste':
            value_hash = checksum(value)
        else:
            raise tornado.web.HTTPError(405, 'Could not post to {}'.format(type))

        data  = self.application.database.lookup(value_hash)
        tries = 0
        while data is None and tries < self.application.max_tries:
            tries = tries + 1

            try:
                name = self.application.generate_name()
                self.application.database.add(name, value_hash, type)
                if type != 'url':
                    path = os.path.join(self.application.uploads_dir, name)
                    with open(path, 'wb+') as fs:
                        fs.write(value)
                data = self.application.database.get(name)
            except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
                self.application.logger.warn(e)
                self.application.logger.info('name: %s', name)
                continue

        if tries >= self.application.max_tries:
            raise tornado.web.HTTPError(500, 'Could not produce new database entry')

        preview_url = '{}/{}'.format(self.application.url, data.name)
        if type == 'paste':
            file_path = os.path.join(self.application.uploads_dir, data.name)
            file_mime = determine_mimetype(file_path)
            file_ext  = guess_extension(file_mime)
            raw_url   = '{}/raw/{}{}'.format(self.application.url, data.name, file_ext)

        if use_template:
            self.render('url.tmpl', name=data.name, preview_url=preview_url, raw_url=raw_url)
        else:
            self.set_header('Content-Type', 'text/plain')
            if self.get_argument('raw', '').lower() in TRUE_STRINGS:
                self.write(raw_url)
            else:
                self.write(preview_url + '\n')

    def put(self, type=None):
        return self.post(type)


class YldMeMarkdownHandler(YldMeHandler):
    def get(self, name=None):
        if name is None:
            return self._index()

        name = name.split('.')[0]
        data = self.application.database.get(name)
        if data is None:
            return self._index()

        self.application.database.hit(name)

        if data.type != 'paste':
            return self._index()

        file_path = os.path.join(self.application.uploads_dir, name)
        try:
            file_data = open(file_path, 'rb').read()
        except (OSError, IOError):
            raise tornado.web.HTTPError(410, 'Upload has been removed')

        try:
            hilite    = markdown.extensions.codehilite.CodeHiliteExtension(noclasses=True)
            file_html = markdown.markdown(file_data.decode(), extensions=['extra', hilite])
        except NameError:
            raise tornado.web.HTTPError(501, 'Server does not support Markdown')
        except UnicodeDecodeError:
            raise tornado.web.HTTPError(405, 'Requested resource is not a Markdown file')

        self.render('paste.tmpl', **{
            'name'      : name,
            'file_html' : file_html,
            'mime_type' : 'text/markdown',
            'file_ext'  : '.md',
            'pygment'   : 'default',
            'styles'    : self.application.styles,
        })


class YldMeRawHandler(YldMeHandler):
    def get(self, name=None):
        self.request.arguments['raw'] = '1'
        return YldMeHandler.get(self, name)

    def post(self, type=None):
        self.request.arguments['raw'] = '1'
        return YldMeHandler.post(self, type)


# Application

class YldMeApplication(tornado.web.Application):

    def __init__(self, config_dir=None, **settings):
        self.logger   = logging.getLogger()
        self.load_configuration(config_dir)

        settings['template_path'] = settings.get('templates', self.templates_dir)

        tornado.web.Application.__init__(self, **settings)

        self.address  = settings.get('address', self.address)
        self.port     = settings.get('port', self.port)
        self.ioloop   = tornado.ioloop.IOLoop.instance()
        self.database = Database(os.path.join(self.config_dir, 'db'), self.presets)
        self.styles   = [os.path.basename(path)[:-4] for path in sorted(glob.glob(os.path.join(self.styles_dir, '*.css')))]

        self.add_handlers('.*', [
                (r'.*/assets/(.*)', tornado.web.StaticFileHandler, {'path': self.assets_dir}),
                (r'.*/md/(.*)'    , YldMeMarkdownHandler),
                (r'.*/raw/(.*)'   , YldMeRawHandler),
                (r'.*/(.*)'       , YldMeHandler),
        ])

    def generate_name(self):
        return integer_to_identifier(random.randrange(self.database.count()*10), self.alphabet)

    def run(self):
        try:
            self.listen(self.port, self.address)
        except socket.error as e:
            self.logger.fatal('Unable to listen on {}:{} = {}'.format(self.address, self.port, e))
            sys.exit(1)

        self.ioloop.start()

    def load_configuration(self, config_dir=None):
        self.config_dir  = os.path.expanduser(config_dir or '~/.config/yldme')
        self.config_path = os.path.join(self.config_dir, 'config.yaml')

        if os.path.exists(self.config_path):
            config = yaml.load(open(self.config_path))
        else:
            config = {}

        self.logger.info('Configuration Directory: %s', self.config_dir)
        self.logger.info('Configuration Path:      %s', self.config_path)

        self.url       = config.get('url'      , 'https://yld.me')
        self.port      = config.get('port'     , 9515)
        self.address   = config.get('address'  , '127.0.0.1')
        self.alphabet  = config.get('alphabet' , string.ascii_letters + string.digits)
        self.max_tries = config.get('max_tries', 10)

        self.logger.info('URL:                     %s', self.url)
        self.logger.info('Port:                    %d', self.port)
        self.logger.info('Address:                 %s', self.address)
        self.logger.info('Alphabet:                %s', self.alphabet)
        self.logger.info('Max Tries:               %d', self.max_tries)

        self.assets_dir    = config.get('assets'   , os.path.join(os.path.dirname(__file__), 'assets'))
        self.styles_dir    = config.get('styles'   , os.path.join(self.assets_dir, 'css', 'pygments'))
        self.uploads_dir   = config.get('uploads'  , os.path.join(self.config_dir, 'uploads'))
        self.templates_dir = config.get('templates', os.path.join(os.path.dirname(__file__), 'templates'))

        self.logger.info('Assets Directory:        %s', self.assets_dir)
        self.logger.info('Styles Directory:        %s', self.styles_dir)
        self.logger.info('Uploads Directory:       %s', self.uploads_dir)
        self.logger.info('Templates Directory:     %s', self.templates_dir)

        if not os.path.isdir(self.uploads_dir):
            os.makedirs(self.uploads_dir)

        self.presets = config.get('presets', [])
        for preset in self.presets:
            self.logger.info('Preset: %s -> %s', preset['name'], preset['link'])

# Main execution

if __name__ == '__main__':
    tornado.options.define('address', default=YLDME_ADDRESS, help='Address to listen on.')
    tornado.options.define('port', default=YLDME_PORT, help='Port to listen on.')
    tornado.options.define('config_dir', default='~/.config/yldme',  help='Configuration directory')
    tornado.options.define('debug', default=False, help='Enable debugging mode.')
    tornado.options.define('templates', default='templates', help='Path to templates')
    tornado.options.parse_command_line()

    options = tornado.options.options.as_dict()
    yldme   = YldMeApplication(**options)

    try:
        import markdown
        import markdown.extensions.codehilite
    except ImportError:
        yldme.logger.warn('Markdown module missing!')

    yldme.run()

# vim: sts=4 sw=4 ts=8 expandtab ft=python
