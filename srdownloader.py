#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.

import os
import requests

import stoneridge

import logging

class StoneRidgeDownloader(object):
    """Downloads the firefox archive and the tests.zip for a the machine this is
    running on and puts them in the stone ridge working directory
    """
    def __init__(self):
        self.server = stoneridge.get_config('download', 'server')
        self.downloadroot = stoneridge.get_config('download', 'root')
        logging.debug('server = %s' % (self.server,))
        logging.debug('download root = %s' % (self.downloadroot,))

    def _download_file(self, filename):
        url = 'http://%s/%s/%s/%s' % (self.server, self.downloadroot,
                stoneridge.download_platform, filename)
        logging.debug('downloading %s from %s' % (filename, url))
        r = requests.get(url)
        if r.status_code != 200:
            logging.critical('Error downloading %s: %s' % (filename,
                                                           r.status_code))
            raise Exception, 'Error downloading %s: %s' % (filename,
                    r.status_code)
        with file(filename, 'wb') as f:
            f.write(r.content)

    def run(self):
        logging.debug('downloader running')
        if not os.path.exists(stoneridge.downloaddir):
            logging.debug('creating download directory %s' %
                    (stoneridge.downloaddir,))
            os.mkdir(stoneridge.downloaddir)
        os.chdir(stoneridge.downloaddir)

        self._download_file('firefox.%s' % (stoneridge.download_suffix,))
        self._download_file('tests.zip')


@stoneridge.main
def main():
    parser = stoneridge.ArgumentParser()
    args = parser.parse_args()

    downloader = StoneRidgeDownloader()
    downloader.run()