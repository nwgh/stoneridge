#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.

import glob
import json
import os
import platform
import subprocess
import sys
import time

import stoneridge

import logging

class StoneRidgeRunner(object):
    """Does the actual work of running the stone ridge xpcshell tests
    """
    def __init__(self, tests=None, heads=None):
        """tests - a subset of the tests to run
        heads - js files that provide extra functionality
        """
        # These we just copy over and worry about them later
        self.tests = tests
        self.heads = heads if heads else []
        logging.debug('requested tests: %s' % (tests,))
        logging.debug('heads: %s' % (heads,))

    def _build_testlist(self):
        """Return a list of test file names, all relative to the test root.
        This weeds out any tests that may be missing from the directory.
        """
        if not self.tests:
            logging.debug('searching for all tests in %s' %
                    (stoneridge.testroot,))
            if stoneridge.get_config('test', 'enabled'):
                tests = ['fake.js']
            else:
                tests = [os.path.basename(f) for f in
                         glob.glob(os.path.join(stoneridge.testroot, '*.js'))]
                tests.remove('fake.js')
            logging.debug('tests found %s' % (tests,))
            return tests

        tests = []
        for candidate in self.tests:
            logging.debug('candidate test %s' % (candidate,))
            if not candidate.endswith('.js'):
                logging.error('invalid test filename %s' % (candidate,))
            elif not os.path.exists(os.path.join(stoneridge.testroot, candidate)):
                logging.error('missing test %s' % (candidate,))
            else:
                logging.debug('valid test file %s' % (candidate,))
                tests.append(candidate)

        logging.debug('tests selected %s' % (tests,))
        return tests

    def _build_preargs(self):
        """Build the list of arguments (including head js files) for everything
        except the actual command to run.
        """
        preargs = ['-v', '180']

        for head in self.heads:
            abshead = os.path.abspath(head)
            preargs.extend(['-f', abshead])

        logging.debug('calculated preargs %s' % (preargs,))
        return preargs

    def run(self):
        logging.debug('runner running')
        tests = self._build_testlist()
        preargs = self._build_preargs()
        logging.debug('tests to run: %s' % (tests,))
        logging.debug('args to prepend: %s' % (preargs,))

        # Ensure our output directory exists
        logging.debug('ensuring %s exists' % (stoneridge.xpcoutdir,))
        try:
            os.makedirs(stoneridge.xpcoutdir)
            logging.debug('%s created' % (stoneridge.xpcoutdir,))
        except OSError:
            logging.debug('%s already exists' % (stoneridge.xpcoutdir,))
            pass

        for test in tests:
            logging.debug('test: %s' % (test,))
            outfile = '%s.out' % (test,)
            logging.debug('outfile: %s' % (outfile,))
            args = preargs + [
                '-e', 'const _SR_OUT_SUBDIR = "%s";' % (stoneridge.xpcoutleaf,),
                '-e', 'const _SR_OUT_FILE = "%s";' % (outfile,),
                '-f', os.path.join(stoneridge.installroot, 'head.js'),
                '-f', os.path.join(stoneridge.testroot, test),
                '-e', 'do_stoneridge(); quit(0);'
            ]
            logging.debug('xpcshell args: %s' % (args,))
            res, xpcshell_out = stoneridge.run_xpcshell(args)
            logging.debug('xpcshell output\n%s' % (xpcshell_out.read(),))
            if res:
                logging.error('TEST FAILED: %s' % (test,))
            else:
                logging.debug('test succeeded')


@stoneridge.main
def main():
    parser = stoneridge.ArgumentParser()
    parser.add_argument('--head', dest='heads', action='append', metavar='HEADFILE',
                        help='Extra head.js file to append (can be used more than once)')
    parser.add_argument('tests', nargs='*', metavar='TEST',
                        help='Name of single test file to run')

    args = parser.parse_args()

    runner = StoneRidgeRunner(args.tests, args.heads)
    runner.run()