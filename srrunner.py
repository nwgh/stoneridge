#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.

import glob
import logging
import os

import stoneridge


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

        self.testroot = stoneridge.get_config('stoneridge', 'testroot')
        self.unittest = stoneridge.get_config_bool('stoneridge', 'unittest')

        logging.debug('testroot: %s' % (self.testroot,))
        logging.debug('unittest: %s' % (self.unittest,))

    def _build_testlist(self):
        """Return a list of test file names, all relative to the test root.
        This weeds out any tests that may be missing from the directory.
        """
        if not self.tests:
            logging.debug('searching for all tests in %s' %
                          (self.testroot,))
            if stoneridge.get_config('test', 'enabled'):
                tests = ['fake.js']
            else:
                tests = [os.path.basename(f) for f in
                         glob.glob(os.path.join(self.testroot, '*.js'))]
                tests.remove('fake.js')
            logging.debug('tests found %s' % (tests,))
            return tests

        tests = []
        for candidate in self.tests:
            logging.debug('candidate test %s' % (candidate,))
            if not candidate.endswith('.js'):
                logging.error('invalid test filename %s' % (candidate,))
            elif not os.path.exists(os.path.join(self.testroot, candidate)):
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
        def escape(path):
            return path.replace('\\', '\\\\')

        outdir = stoneridge.get_config('run', 'out')
        installroot = stoneridge.get_config('stoneridge', 'root')
        head_path = os.path.join(installroot, 'head.js')

        for test in tests:
            logging.debug('test: %s' % (test,))
            outfile = '%s.out' % (test,)
            logging.debug('outfile: %s' % (outfile,))
            test_path = os.path.join(self.testroot, test)
            args = preargs + [
                '-e', 'const _SR_OUT_SUBDIR = "%s";' % (escape(outdir),),
                '-e', 'const _SR_OUT_FILE = "%s";' % (outfile,),
                '-e', 'const _SR_HEAD_JS = "%s";' % (escape(head_path),),
            ]
            if test_path.endswith('.ipc.js'):
                test_bits = test_path.rsplit('.', 2)
                real_test_path = '.'.join([test_bits[0], test_bits[2]])
                args += [
                    '-e', 'const _SR_TEST_JS = "%s";' %
                    (escape(real_test_path),)
                ]
            else:
                args += [
                    '-e', 'const _SR_TEST_JS = "%s";' % (escape(test_path),)
                ]
            args += [
                '-f', head_path,
                '-f', test_path,
                '-e', 'do_stoneridge(); quit(0);'
            ]
            logging.debug('xpcshell args: %s' % (args,))
            if self.unittest:
                logging.debug('Not running processes: in unit test mode')
            else:
                xpcshell_out_file = '%s.xpcshell.out' % (test,)
                xpcshell_out_file = os.path.join(outdir, xpcshell_out_file)
                logging.debug('xpcshell output at %s' % (xpcshell_out_file,))
                timed_out = False
                with file(xpcshell_out_file, 'wb') as f:
                    try:
                        res, _ = stoneridge.run_xpcshell(args, stdout=f)
                    except stoneridge.XpcshellTimeout:
                        logging.exception('xpcshell timed out!')
                        timed_out = True
                        res = None
                if res or timed_out:
                    logging.error('TEST FAILED: %s' % (test,))
                else:
                    logging.debug('test succeeded')


@stoneridge.main
def main():
    parser = stoneridge.TestRunArgumentParser()
    parser.add_argument('--head', dest='heads', action='append',
                        metavar='HEADFILE',
                        help='Extra head.js file to append (can be used more '
                             'than once)')
    parser.add_argument('tests', nargs='*', metavar='TEST',
                        help='Name of single test file to run')

    args = parser.parse_args()

    runner = StoneRidgeRunner(args.tests, args.heads)
    runner.run()
