/*
 * This Source Code Form is subject to the terms of the Mozilla Public License,
 * v. 2.0. If a copy of the MPL was not distributed with this file, You can
 * obtain one at http://mozilla.org/MPL/2.0/.
 *
 * This file defines the commonly-used functionality needed by a stone ridge
 * test suite. This must be run under xpcshell running in JS v1.8 mode.
 */

var _stoneridge_finished = null;
var _stoneridge_results = null;
var _save_results = true;

var Cc = Components.classes;
var Ci = Components.interfaces;
var Cr = Components.results;

/*
 * Store some results for writing once we're all done
 */
function do_write_result(key, start, stop) {
  var startms = start.valueOf();
  var stopms = stop.valueOf();

  var val = {'start':startms, 'stop':stopms, 'total':stopms - startms};

  if (_stoneridge_results.hasOwnProperty(key)) {
    _stoneridge_results[key].push(val);
  } else {
    _stoneridge_results[key] = [val];
  }
}

/*
 * This is used to indicate that the tests are done. Now that we know we're
 * done, we can write the results to disk for the python harness to do its thing
 * with.
 */
function do_test_finish() {
  _stoneridge_finished = true;
}

function do_ipc_test_finish() {
  _save_results = false;
  do_test_finish();
}

/*
 * This is only here for symmetry with xpcshell unit tests, stone ridge assumes
 * everything it runs is going to be asynchronous.
 */
function do_test_pending() {}

function _do_save_results() {
  // Create a file pointing to our output directory
  var ofile = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsILocalFile);
  ofile.initWithPath(_SR_OUT_SUBDIR);

  // And use the file determined by our caller
  ofile.append(_SR_OUT_FILE);

  // Now get an output stream for our file
  var ostream = Cc["@mozilla.org/network/file-output-stream;1"].
                createInstance(Ci.nsIFileOutputStream);
  ostream.init(ofile, -1, -1, 0);

  var jstring = JSON.stringify(_stoneridge_results);
  ostream.write(jstring, jstring.length);
  ostream.close();
}

function make_channel(url) {
  var ios = Cc["@mozilla.org/network/io-service;1"].getService(Ci.nsIIOService);
  return ios.newChannel(url, "", null);
}

/*
 * The main entry point for all stone ridge tests
 */
function do_stoneridge() {
  _stoneridge_finished = false;
  _stoneridge_results = {};

  run_test();

  // Pump the event loop until we're told to stop
  var thread = Cc["@mozilla.org/thread-manager;1"].
               getService().currentThread;
  while (!_stoneridge_finished)
    thread.processNextEvent(true);
  while (thread.hasPendingEvents())
    thread.processNextEvent(true);

  if (_save_results) {
    _do_save_results();
  }
}

function do_stoneridge_ipc() {
}

var _child_harness_loaded = false;

function run_test_in_child() {
  if (!_child_harness_loaded) {
    _child_harness_loaded = true;

    // Disable necko IPC security checks, since we don't have a docshell
    var prefs = Cc["@mozilla.org/preferences-service;1"]
        .getService(Ci.nsIPrefBranch);
    prefs.setBoolPref('network.disable.ipc.security', true);

    // Set up all the variables we need to run the test appropriately
    pescape = function pescape(path) {
        return path.replace(/\\/g, "\\\\");
    };
    sendCommand("const _SR_HEAD_JS='" + pescape(_SR_HEAD_JS) + "';" +
                "const _SR_TEST_JS='" + pescape(_SR_TEST_JS) + "';" +
                "const _SR_OUT_SUBDIR='" + pescape(_SR_OUT_SUBDIR) + "';" +
                "const _SR_OUT_FILE='" + pescape(_SR_OUT_FILE) + "';" +
                "load(_SR_HEAD_JS);" +
                "load(_SR_TEST_JS);");
  }

  sendCommand("do_stoneridge();", do_ipc_test_finish);
}
