#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.

import base64
import dzclient
import json
import logging
import os
import time

import stoneridge


EMAIL_MESSAGE = '''Hello, %s!

Your stone ridge test has completed its run. Your results are attached.
For your reference, here's the details about this particular run:

    ID: %s
    Operating System: %s
    Network Configuration: %s

Enjoy!
-The Stone Ridge System
'''


class StoneRidgeReporter(stoneridge.QueueListener):
    def setup(self):
        self.host = stoneridge.get_config('report', 'host')
        self.project = stoneridge.get_config('report', 'project')
        self.key = stoneridge.get_config('report', 'key')
        self.secret = stoneridge.get_config('report', 'secret')
        self.archives = stoneridge.get_config('stoneridge', 'archives')
        self.unittest = stoneridge.get_config_bool('stoneridge', 'unittest')

        logging.debug('report host: %s' % (self.host,))
        logging.debug('project: %s' % (self.project,))
        logging.debug('oauth key: %s' % (self.key,))
        logging.debug('oauth secret: %s' % (self.secret,))
        logging.debug('archives: %s' % (self.archives,))
        logging.debug('unittest: %s' % (self.unittest,))

    def save_data(self, srid, netconfig, operating_system, results,
                  metadata_b64, ldap, tstamp):
        gmtime = time.gmtime(tstamp)
        tstr = time.strftime('%Y%m%d%H%M%S', gmtime)
        dirname = os.path.join('%s_%s' % (tstr, srid), netconfig,
                               operating_system)
        archivedir = os.path.join(self.archives, dirname)
        os.makedirs(archivedir)

        results_file = os.path.join(archivedir, 'results.json')
        with file(results_file, 'w') as f:
            json.dump(results, f)

        metadata = base64.b64decode(metadata_b64)
        metadata_file = os.path.join(archivedir, 'metadata.zip')
        with file(metadata_file, 'wb') as f:
            f.write(metadata)

        if ldap is not None:
            msg_text = EMAIL_MESSAGE % (ldap, srid, operating_system,
                                        netconfig)
            stoneridge.sendmail(ldap, 'Stone Ridge Complete',
                                msg_text, (metadata_file, 'results.zip'))

    def handle(self, srid, netconfig, operating_system, results, metadata,
               ldap, tstamp):
        logging.debug('uploading results for %s' % (srid,))

        for name in results:
            dataset = results[name]
            if not isinstance(dataset, dict):
                # This one is crap, ignore it
                logging.error('bad json: %s' % (results[name],))
                continue

            if self.unittest:
                logging.debug('would upload data via https to %s, project %s' %
                              (self.host, self.project))
                logging.debug('dataset: %s' % (dataset,))
            else:
                logging.debug('uploading data')
                request = dzclient.DatazillaRequest('https', self.host,
                                                    self.project, self.key,
                                                    self.secret)
                response = request.send(dataset)
                logging.debug('got status code %s' % (response.status,))
                if response.status != 200:
                    logging.error('bad http status %s for %s' %
                                  (response.status, srid))

                try:
                    result = json.load(response)
                except:
                    result = ''
                logging.debug('got result %s' % (result,))
                if result['status'] != 'well-formed JSON stored':
                    logging.error('bad status for %s: %s' %
                                  (srid, result['status']))

        self.save_data(srid, netconfig, operating_system, results, metadata,
                       ldap, tstamp)


def daemon():
    reporter = StoneRidgeReporter(stoneridge.OUTGOING_QUEUE)
    reporter.run()


@stoneridge.main
def main():
    parser = stoneridge.DaemonArgumentParser()
    parser.parse_args()

    parser.start_daemon(daemon)
