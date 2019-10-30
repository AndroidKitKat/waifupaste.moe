#!/usr/bin/env python3

import os
import re
import subprocess
import tempfile
import time
import unittest

import requests
import yldme

# Constants

TEST_PORT = 9999
TEST_URL  = 'http://localhost:' + str(TEST_PORT)

# Test Cases

class YldMeHandlerTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.config_dir = tempfile.TemporaryDirectory()
        cls.process    = subprocess.Popen([
            './yldme.py',
            '--port=' + str(TEST_PORT),
            '--config_dir=' + cls.config_dir.name,
        ], stderr=subprocess.DEVNULL)
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.config_dir.cleanup()

    def test_get_index(self):
        response = requests.get(TEST_URL)
        self.assertTrue(response.status_code == 200)
        self.assertTrue('/paste' in response.text)
        self.assertTrue('/url'   in response.text)
    
    def test_post_url(self, method=requests.post):
        response = method(TEST_URL + '/url', data = 'https://yld.me')
        self.assertTrue(response.status_code == 200)

        shorturl = response.text.strip()
        self.assertTrue(re.match('https://yld.me/[a-zA-Z0-9]{1}', shorturl))
        
        shorturl = TEST_URL + '/' + os.path.basename(shorturl)
        response = requests.get(shorturl, allow_redirects=False)
        self.assertTrue(response.status_code == 302)
        self.assertTrue(response.headers['Location'] == 'https://yld.me')
    
    def test_put_url(self):
        self.test_post_url(requests.put)
    
    def test_post_paste_batch(self, method=requests.post):
        data     = 'Sic Mundus Creatus Est'
        response = method(TEST_URL + '/paste', data=data)
        self.assertTrue(response.status_code == 200)
        
        shorturl = response.text.strip()
        self.assertTrue(re.match('https://yld.me/[a-zA-Z0-9]{1}', shorturl))

        shorturl = TEST_URL + '/' + os.path.basename(shorturl)
        response = requests.get(shorturl)
        self.assertTrue(response.status_code == 200)
        for word in data.split():
            self.assertTrue(word in response.text)

        rawurl = TEST_URL + '/raw/' + os.path.basename(shorturl)
        response = requests.get(rawurl)
        self.assertTrue(response.status_code == 200)
        self.assertTrue(response.text == data)
        
        rawurl = TEST_URL + '/raw/' + os.path.basename(shorturl) + '.txt'
        response = requests.get(rawurl)
        self.assertTrue(response.status_code == 200)
        self.assertTrue(response.text == data)
    
    def test_put_paste_url(self):
        self.test_post_paste_batch(requests.put)

# Main Execution

if __name__ == '__main__':
    unittest.main()
