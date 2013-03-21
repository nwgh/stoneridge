#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
import subprocess

import stoneridge


class StoneRidgeException(Exception):
    pass


class StoneRidgeWorker(stoneridge.QueueListener):
    def setup(self):
        self.srconffile = stoneridge.get_config_file()
        self.unittest = stoneridge.get_config_bool('stoneridge', 'unittest')
        self.workroot = stoneridge.get_config('stoneridge', 'work')
        logging.debug('srconffile: %s' % (self.srconffile,))
        logging.debug('unittest: %s' % (self.unittest,))

        self.runconfig = None  # Needs to be here so reset doesn't barf
        self.reset()

    def handle(self, srid, netconfig, tstamp, ldap):
        # Create the directory where data we want to save from this run will go
        srwork = os.path.join(self.workroot, srid, netconfig)
        if os.path.exists(srwork):
            srwork = '%s_%s' % (srwork, tstamp)
        os.makedirs(srwork)
        srout = os.path.join(srwork, 'out')
        os.mkdir(srout)

        # Have a logger just for this run
        self.logdir = os.path.join(srout, 'logs')
        os.makedirs(self.logdir)
        logging.debug('Running test with logs in %s' % (self.logdir,))

        logfile = os.path.join(self.logdir, '00_worker.log')
        handler = logging.FileHandler(logfile)
        formatter = logging.Formatter(fmt=stoneridge.LOG_FMT)
        handler.setFormatter(formatter)
        self.logger = logging.getLogger('%s_%s_%s' % (srid, netconfig, tstamp))
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)

        # Create the rest of the working space for this run
        srdownload = os.path.join(srwork, 'download')
        os.mkdir(srdownload)
        firefox_path = stoneridge.get_config('machine', 'firefox_path')
        srbindir = os.path.join(srwork, firefox_path)
        metadata = os.path.join(srout, 'metadata.zip')
        info = os.path.join(srout, 'info.json')

        self.srnetconfig = netconfig
        self.uploaded = False
        self.archive_on_failure = True
        self.procno = 1
        self.childlog = None
        self.need_dns_reset = False

        self.runconfig = os.path.join(srout, 'run.ini')
        with file(self.runconfig, 'w') as f:
            f.write('[run]\n')
            f.write('netconfig = %s\n' % (netconfig,))
            f.write('work = %s\n' % (srwork,))
            f.write('download = %s\n' % (srdownload,))
            f.write('bin = %s\n' % (srbindir,))
            f.write('out = %s\n' % (srout,))
            f.write('metadata = %s\n' % (metadata,))
            f.write('info = %s\n' % (info,))
            f.write('tstamp = %s\n' % (tstamp,))
            f.write('srid = %s\n' % (srid,))
            if ldap:
                f.write('ldap = %s\n' % (ldap,))

        self.logger.debug('srnetconfig: %s' % (self.srnetconfig,))
        self.logger.debug('uploaded: %s' % (self.uploaded,))
        self.logger.debug('archive on failure: %s' %
                          (self.archive_on_failure,))
        self.logger.debug('procno: %s' % (self.procno,))
        self.logger.debug('childlog: %s' % (self.childlog,))
        self.logger.debug('logdir: %s' % (self.logdir,))
        self.logger.debug('runconfig: %s' % (self.runconfig,))
        self.logger.debug('ldap: %s' % (ldap,))

        res = {'ok': True}

        try:
            self.run_test()
        except StoneRidgeException as e:
            self.logger.exception(e)
            res['ok'] = False
            res['msg'] = str(e)

        self.reset()

        return res

    def reset(self):
        self.srnetconfig = None
        self.uploaded = False
        self.archive_on_failure = True
        self.procno = -1
        self.childlog = None
        self.logdir = None
        self.logger = None
        if self.runconfig and os.path.exists(self.runconfig):
            os.unlink(self.runconfig)
        self.runconfig = None

    def do_error(self, stage):
        """Print an error and raise an exception that will be handled by the
        top level
        """
        self.logger.error('Error exit during %s' % (stage,))
        raise StoneRidgeException('Error running %s: see %s\n' %
                                  (stage, self.childlog))

    def run_process(self, stage, *args):
        """Run a particular subprocess with the default arguments, as well as
        any arguments requested by the caller
        """
        script = 'sr%s.py' % (stage,)
        logfile = os.path.join(self.logdir, '%02d_%s_%s.log' %
                               (self.procno, stage, self.srnetconfig))
        self.procno += 1

        command = [script,
                   '--config', self.srconffile,
                   '--runconfig', self.runconfig,
                   '--log', logfile]
        command.extend(args)

        if self.unittest:
            # This code path is used for unit testing the worker
            self.logger.debug('Would run %s' % (command,))
            return

        try:
            stoneridge.run_process(*command, logger=self.logger)
        except subprocess.CalledProcessError:
            # The process failed to run correctly, we need to say so
            self.childlog = logfile

            if self.need_dns_reset:
                # We were in the midst of having our dns all screwy, so we
                # need to try our best to fix that. Let's hope it works!

                # First of all, we don't want to archive or upload during
                # the process of running the dns updater.
                do_archive = self.archive_on_failure
                self.archive_on_failure = False

                uploaded = self.uploaded
                self.uploaded = True

                try:
                    self.run_process('dnsupdater', '--restore')
                except StoneRidgeException:
                    logging.error('Was unable to reset DNS after failure')

                # Reset this state back to where it was previously so the rest
                # of this block can work as expected.
                self.archive_on_failure = do_archive
                self.uploaded = uploaded

            if self.archive_on_failure:
                # We've reached the point in our run where we have something to
                # save off for usage. Archive it, but don't try to archive
                # again if for some reason the archival process fails :)
                self.archive_on_failure = False
                try:
                    self.run_process('archiver')
                except StoneRidgeException:
                    pass
            if not self.uploaded:
                self.uploaded = True
                try:
                    self.run_process('uploader')
                except StoneRidgeException:
                    pass

            # Finally, bubble the error up to the top level
            self.do_error(stage)

    def run_test(self):
        self.run_process('downloader')

        self.run_process('unpacker')

        self.run_process('infogatherer')

        self.run_process('pcap', '--start')

        self.run_process('dnsupdater')

        self.need_dns_reset = True

        self.run_process('dnscheck')

        self.run_process('arpfixer')

        self.run_process('runner')

        self.need_dns_reset = False

        self.run_process('dnsupdater', '--restore')

        self.run_process('dnscheck', '--public')

        self.run_process('pcap', '--stop')

        self.run_process('collator')

        self.archive_on_failure = False

        self.run_process('archiver')

        self.uploaded = True

        self.run_process('uploader')


@stoneridge.main
def main():
    parser = stoneridge.ArgumentParser()
    parser.parse_args()

    osname = stoneridge.get_config('machine', 'os')
    queue = stoneridge.CLIENT_QUEUES[osname]

    while True:
        try:
            worker = StoneRidgeWorker(queue)
            worker.run()
        except:
            logging.exception('Worker failed')
