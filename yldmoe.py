#!/usr/bin/env python3

import collections
import glob
import hashlib
import json
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
import datetime
import tornado.ioloop
import tornado.options
import tornado.web

from base64 import b64decode

import pygments
import pygments.lexers
import pygments.formatters
import pygments.styles
import pygments.util

# Constants

YLDME_ADDRESS   = '0.0.0.0'
YLDME_PORT      = 9516
TRUE_STRINGS    = ('1', 'true', 'on', 'yes')

LOG_FILE = '/home/yldmoe-admin/.config/yldme/log.txt'
URL_FILE = '/home/yldmoe-admin/.config/yldme/urls.txt'

MIME_TYPES = {
    'image/jpeg'        : '.jpg',
    'image/png'         : '.png',
    'video/mp4'         : '.mp4',
    'text/plain'        : '.txt',
    'text/x-c++'        : '.cpp',
    'text/x-python'     : '.py',
    'text/x-shellscript': '.sh',
}

# Utilities

def log_url(wp_url, real_url, ip):
    with open(URL_FILE, 'a') as url_file:
        url_file.write('Time: {} | WP: {} | URL: {} | IP: {} | Source: YldMoe\n'.format(datetime.datetime.now(), wp_url, real_url, ip))

def log_ip(extension, ip):
    with open(LOG_FILE, 'a') as log_file:
        log_file.write('Time: {} | URL: {} | IP: {} | Source: YldMoe\n'.format(datetime.datetime.now(), extension, ip))
        return

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


def determine_text_format(file_data, file_mime='text/plain', file_ext='.txt', style='default', linenos=False):
    try:
        file_data = file_data.decode('utf8')
    except UnicodeDecodeError:
        file_data = file_data.decode('latin-1')
    json_data = None
    yaml_data = None

    if file_mime == 'text/plain':
        try:
            yaml_data = yaml.safe_load(file_data)
            if not isinstance(yaml_data, list) and not isinstance(yaml_data, dict):
                yaml_data = None
            else:
                file_mime = 'text/x-yaml'
                file_ext  = '.yaml'
        except (yaml.parser.ParserError, yaml.scanner.ScannerError, yaml.reader.ReaderError):
            pass

        try:
            json_data = json.loads(file_data)
            file_mime = 'application/json'
            file_ext  = '.json'
        except json.decoder.JSONDecodeError:
            pass

    if json_data:
        lexer     = pygments.lexers.get_lexer_for_mimetype(file_mime)
        file_data = json.dumps(json_data, indent=4)
    elif yaml_data:
        lexer     = pygments.lexers.get_lexer_for_mimetype(file_mime)
        file_data = yaml.safe_dump(yaml_data, default_flow_style=False)
    else:
        try:
            lexer = pygments.lexers.guess_lexer(file_data)
        except pygments.util.ClassNotFound:
            lexer = pygments.lexers.get_lexer_for_mimetype('text/plain')

    formatter = pygments.formatters.HtmlFormatter(cssclass='hll', linenos=linenos, style=style)
    file_html = pygments.highlight(file_data, lexer, formatter)
    return file_ext, file_html

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

class YldMeRobotsHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header('Content-Type', 'text/plain')
        self.write('''# Block Webcrawlers
User-agent: *
Disallow: /
''')

class YldMeHandler(tornado.web.RequestHandler):

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "OPTIONS,POST")
        self.set_header("Access-Control-Allow-Headers", "*")

    # needed for CORS, probably breaks all sorts of other things
    def options(self, *args):
        print("what the frick")
        self.set_status(204)
        self.finish()
        
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
            file_ext, file_html = determine_text_format(
                file_data, file_mime, file_ext, style, linenos
            )
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

    def post(self, type=None, extra_type=None):
        # legacy variable
        imgJpeg = False
        # new variable
        base64 = False
        if extra_type == 'imgJpeg' or extra_type == 'base64':
            type = 'paste'

        if type == 'image.jpeg' or type == 'image.jpg':
            imgJpeg = True
            type = 'paste'
            
        if type == 'base64':
            base64 = True

        if 'source' in self.request.files:
            use_template = True
            value        = self.request.files['source'][0].body
        elif 'file' in self.request.files:
            use_template = False
            value        = self.request.files['file'][0].body
        else:
            use_template = False
            value        = self.request.body
        
        if type == 'base64':
            use_template = False
            # value = base64.b64decode(self.get_argument('image'))
            image_base64_string = self.get_argument('image').encode()
            value = b64decode(image_base64_string)
            type = 'paste'
            
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
        #log urls
        if type != 'paste':
            log_url(preview_url, value, self.request.headers.get('CF-Connecting-IP',''))

        if type == 'paste':
            file_path = os.path.join(self.application.uploads_dir, data.name)
            file_mime = determine_mimetype(file_path)
            file_ext  = guess_extension(file_mime)
            raw_url   = '{}/raw/{}{}'.format(self.application.url, data.name, file_ext)
            self.application.logger.info('Posted: {}'.format(raw_url))
            log_ip(raw_url, self.request.headers.get('CF-Connecting-IP', ''))
        
        if use_template:
            self.render('url.tmpl', name=data.name, preview_url=preview_url, raw_url=raw_url)
        else:
            self.set_header('Content-Type', 'text/plain')
            if imageJpeg:
                self.write(raw_url)
            elif self.get_argument('raw', '').lower() in TRUE_STRINGS:
                self.write(raw_url)
            else:
                self.write(preview_url + '\n')


    def put(self, type=None):
        if type == 'image.jpeg' or type == 'image.jpg':
            type == 'paste'
            return self.post(type, 'imgJpeg')
        elif type == 'base64':
            type = 'paste'
            return self.post(type, 'base64')
        else:
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

        settings['template_path'] = settings.get('templates') or self.templates_dir

        tornado.web.Application.__init__(self, **settings)

        self.address  = settings.get('address') or self.address
        self.port     = settings.get('port')    or self.port
        self.ioloop   = tornado.ioloop.IOLoop.instance()
        self.database = Database(os.path.join(self.config_dir, 'db'), self.presets)
        self.styles   = [os.path.basename(path)[:-4] for path in sorted(glob.glob(os.path.join(self.styles_dir, '*.css')))]

        self.logger.info('Port:                    %d', self.port)
        self.logger.info('Address:                 %s', self.address)

        self.add_handlers('.*', [
                (r'.*/assets/(.*)', tornado.web.StaticFileHandler, {'path': self.assets_dir}),
                (r'.*/md/(.*)'    , YldMeMarkdownHandler),
                (r'.*/raw/(.*)'   , YldMeRawHandler),
                (r'.*/robots.txt' , YldMeRobotsHandler),
                (r'.*/(.*)'       , YldMeHandler),
        ])

    def generate_name(self):
        count = self.database.count() or 1
        return integer_to_identifier(random.randrange(count*10), self.alphabet)

    def run(self):
        try:
            self.listen(self.port, self.address)
        except socket.error as e:
            self.logger.fatal('Unable to listen on {}:{} = {}'.format(self.address, self.port, e))
            sys.exit(1)

        self.ioloop.start()

    def load_configuration(self, config_dir=None):
        self.config_dir  = os.path.expanduser(config_dir or '~/.config/yldme')
        self.config_path = os.path.expanduser('~/.config/yldmoe/config.yaml')

        if os.path.exists(self.config_path):
            config = yaml.safe_load(open(self.config_path))
        else:
            config = {}

        self.logger.info('Configuration Directory: %s', self.config_dir)
        self.logger.info('Configuration Path:      %s', self.config_path)

        self.url                = config.get('url'               , 'https://yld.me')
        self.port               = config.get('port'              , 9515)
        self.address            = config.get('address'           , '127.0.0.1')
        self.alphabet           = config.get('alphabet'          , string.ascii_letters + string.digits)
        self.max_tries          = config.get('max_tries'         , 10)
        self.cors_allow_origin  = config.get('cors_allow_origin' , None)
        self.cors_allow_methods = config.get('cors_allow_methods', None)
        self.cors_allow_headers = config.get('cors_allow_headers', None)
        
        

        self.logger.info('URL:                     %s', self.url)
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
    tornado.options.define('templates', default=None, help='Path to templates')
    tornado.options.parse_command_line()

    options = tornado.options.options.as_dict()
    yldme   = YldMeApplication(**options)

    try:
        import markdown
        import markdown.extensions.codehilite
    except ImportError:
        yldme.logger.warning('Markdown module missing!')

    yldme.run()

# vim: sts=4 sw=4 ts=8 expandtab ft=python
