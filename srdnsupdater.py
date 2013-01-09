#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.

import struct
import socket
import sys
import time

import stoneridge

import logging

class StoneRidgeDnsUpdater(object):
    def __init__(self, restore):
        self.restore = restore
        self.peer = ('127.0.0.1', 63250)
        logging.debug('restore: %s' % (restore,))
        logging.debug('peer: %s' % (self.peer,))

    def _converse(self, msgtype, msgdata=None):
        logging.debug('msgtype: %s' % (msgtype,))
        logging.debug('msgdata: %s' % (msgdata,))
        if msgdata is None:
            msgdata = ''

        # Set up our connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(self.peer)
        logging.debug('socket connected')

        # First message is type + length of following message
        msghdr = struct.pack('cB', msgtype, len(msgdata))
        logging.debug('sending header %s' % (msghdr,))
        sock.send(msghdr)

        # Send the data if we have any
        if msgdata:
            logging.debug('sending data %s' % (msgdata,))
            sock.send(msgdata)

        # Get our result and clean up
        result = sock.recv(2)
        logging.debug('received result %s' % (result,))
        sock.close()

        if result != 'ok':
            logging.error('Could not %sset dns server' %
                    ('re' if msgtype == 'r' else ''))

    def _set_dns(self, dnsserver):
        logging.debug('setting dns server to %s' % (dnsserver,))
        self._converse('s', dnsserver)

    def _reset_dns(self):
        logging.debug('resetting dns server')
        self._converse('r')

        # XXX - WARNING! UGLY HACK BELOW!
        # Since, on Windows, we have to actually disable the WAN interface to
        # make our DNS switch properly (at least with my current knowledge of
        # Windows DNS stuff), we have to wait for the interface to come back up
        # before we can try to do anything that would use the WAN interface
        # (such as uploading results).
        if stoneridge.os_name == 'windows':
            logging.debug('sleeping 15 seconds for the windows hack')
            time.sleep(15)

    def run(self):
        logging.debug('dns updater running')
        if self.restore:
            self._reset_dns()
            return

        logging.debug('Searching for dns server for netconfig %s' %
                (stoneridge.current_netconfig,))
        dns_server = stoneridge.get_config('dns', stoneridge.current_netconfig)
        if dns_server is None:
            logging.error('Error finding dns server')
            return

        self._set_dns(dns_server)

@stoneridge.main
def main():
    parser = stoneridge.ArgumentParser()

    parser.add_argument('--restore', dest='restore', action='store_true',
            default=False, help='Restore DNS server to default settings')

    args = parser.parse_args()

    dns_updater = StoneRidgeDnsUpdater(args.restore)
    dns_updater.run()