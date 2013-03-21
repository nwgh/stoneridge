/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/*jshint es5:true, esnext:true*/

try {
  if (Cc === undefined) {
    var Cc = Components.classes;
    var Ci = Components.interfaces;
  }
} catch (ex) {}

var winWidth = 1024;
var winHeight = 768;

var pages;
var pageIndex;
var start_time;
var timeout = -1;
var delay = 250;
var timeoutEvent = -1;
var running = false;

var useMozAfterPaint = false;
var gPaintListener = false;

var content;

var pageUrls;

var outputFile = null;

// the io service
var gIOS = null;

function plInit() {
  if (running) {
    return;
  }
  running = true;

  try {
    var args = window.arguments[0].wrappedJSObject;

    outputFile = args.outputfile;
    if (!outputFile) {
        dumpLine('sr: no output file, quitting');
        plStop(true);
    }

    var manifestURI = args.manifest;
    if (args.width) winWidth = parseInt(args.width, 10);
    if (args.height) winHeight = parseInt(args.height, 10);
    if (args.timeout) timeout = parseInt(args.timeout, 10);
    if (args.delay) delay = parseInt(args.delay, 10);
    if (args.mozafterpaint) useMozAfterPaint = true;

    gIOS = Cc["@mozilla.org/network/io-service;1"]
      .getService(Ci.nsIIOService);
    var fileURI = gIOS.newURI(manifestURI, null, null);
    pages = plLoadURLsFromURI(fileURI);

    if (!pages) {
      dumpLine('sr: could not load URLs, quitting');
      plStop(true);
    }

    if (pages.length === 0) {
      dumpLine('sr: no pages to test, quitting');
      plStop(true);
    }

    pageUrls = pages.map(function(p) { return p.url; });

    pageIndex = 0;

    window.resizeTo(winWidth, winHeight);

    content = document.getElementById('contentPageloader');

    setTimeout(plLoadPage, delay);
  } catch(e) {
    dumpLine(e);
    plStop(true);
  }
}

// load the current page, start timing
var removeLastAddedListener = null;
var removeLastAddedMsgListener = null;
function plLoadPage() {
  var pageName = pages[pageIndex].url;

  if (removeLastAddedListener)
    removeLastAddedListener();

  if (removeLastAddedMsgListener)
    removeLastAddedMsgListener();

  // XXX we use a capturing event here -- load events don't bubble up
  // to the <browser> element.  See bug 390263.
  content.addEventListener('load', plLoadHandler, true);
  removeLastAddedListener = function() {
    content.removeEventListener('load', plLoadHandler, true);
    if (useMozAfterPaint) {
      window.removeEventListener("MozAfterPaint", plPainted, true);
      gPaintListener = false;
    }
  };

  // If the test browser is remote (e10s / IPC) we need to use messages to watch for page load
  if (content.getAttribute("remote") == "true") {
    content.messageManager.addMessageListener('PageLoader:Load', plLoadHandlerMessage);
    content.messageManager.addMessageListener('PageLoader:RecordTime', plRecordTimeMessage);
    if (useMozAfterPaint)
      content.messageManager.addMessageListener('PageLoader:MozAfterPaint', plPaintHandler);
    removeLastAddedMsgListener = function() {
      content.messageManager.removeMessageListener('PageLoader:Load', plLoadHandlerMessage);
      content.messageManager.removeMessageListener('PageLoader:RecordTime', plRecordTimeMessage);
      if (useMozAfterPaint)
        content.messageManager.removeMessageListener('PageLoader:MozAfterPaint', plPaintHandler);
    };
  }

  if (timeout > 0) {
    timeoutEvent = setTimeout(loadFail, timeout);
  }
  startAndLoadURI(pageName);
}

function startAndLoadURI(pageName) {
  start_time = Date.now();
  content.loadURI(pageName);
}

function loadFail() {
  var pageName = pages[pageIndex].url;
  dumpLine("__FAILTimeout exceeded on " + pageName + "__FAIL");
  plStop(true);
}

function plNextPage() {
  var doNextPage = false;
  if (pageIndex < pages.length-1) {
    pageIndex++;
    doNextPage = true;
  }

  if (doNextPage === true) {
    // Force cycle collection (like you do)
    var tccstart = new Date();
    window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
          .getInterface(Components.interfaces.nsIDOMWindowUtils)
          .garbageCollect();

    setTimeout(plLoadPage, delay);
  } else {
    plStop(false);
  }
}

function plRecordTime(start, end) {
  do_write_result(pageUrls[pageIndex], start, end);
}

// the onload handler
function plLoadHandler(evt) {
  // make sure we pick up the right load event
  if (evt.type != 'load' ||
       evt.originalTarget.defaultView.frameElement)
      return;

  content.removeEventListener('load', plLoadHandler, true);
  setTimeout(waitForPainted, 0);
}

// This is called after we have received a load event, now we wait for painted
function waitForPainted() {

  var utils = window.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
                   .getInterface(Components.interfaces.nsIDOMWindowUtils);

  if (!utils.isMozAfterPaintPending || !useMozAfterPaint) {
    _loadHandler();
    return;
  }

  if (gPaintListener === false)
    window.addEventListener("MozAfterPaint", plPainted, true);
  gPaintListener = true;
}

function plPainted() {
  window.removeEventListener("MozAfterPaint", plPainted, true);
  gPaintListener = false;
  _loadHandler();
}

function _loadHandler() {
  if (timeout > 0) {
    clearTimeout(timeoutEvent);
  }
  var docElem = content.contentDocument.documentElement;
  var width;
  if ("getBoundingClientRect" in docElem) {
    width = docElem.getBoundingClientRect().width;
  } else if ("offsetWidth" in docElem) {
    width = docElem.offsetWidth;
  }

  var end_time = Date.now();

  plRecordTime(start_time, end_time);

  plNextPage();
}

// the onload handler used for remote (e10s) browser
function plLoadHandlerMessage(message) {
  _loadHandlerMessage();
}

// the mozafterpaint handler for remote (e10s) browser
function plPaintHandler(message) {
  _loadHandlerMessage();
}

// the core handler for remote (e10s) browser
function _loadHandlerMessage() {
  if (timeout > 0) {
    clearTimeout(timeoutEvent);
  }

  var end_time = Date.now();

  if ((end_time - start_time) >= 0) {
    plRecordTime(start_time, end_time);

    plNextPage();
  }
}

// the record time handler used for remote (e10s) browser
function plRecordTimeMessage(message) {
  gTime = message.json.time;
  if (useMozAfterPaint) {
    gStartTime = message.json.startTime;
  }
  _loadHandlerMessage();
}

function plStop(force) {
  try {
    if (force === false) {
      pageIndex = 0;

      do_save_results(outputFile);
    }
  } catch (e) {
    dumpLine(e);
  }

  if (content) {
    content.removeEventListener('load', plLoadHandler, true);
    if (useMozAfterPaint)
      content.removeEventListener("MozAfterPaint", plPainted, true);

    if (content.getAttribute("remote") == "true") {
      content.messageManager.removeMessageListener('PageLoader:Load', plLoadHandlerMessage);
      content.messageManager.removeMessageListener('PageLoader:RecordTime', plRecordTimeMessage);
      if (useMozAfterPaint)
        content.messageManager.removeMessageListener('PageLoader:MozAfterPaint', plPaintHandler);

      content.messageManager.loadFrameScript("data:,removeEventListener('load', _contentLoadHandler, true);", false);
    }
  }

  goQuitApplication();
}

/* Returns array */
function plLoadURLsFromURI(manifestUri) {
  var fstream = Cc["@mozilla.org/network/file-input-stream;1"]
    .createInstance(Ci.nsIFileInputStream);
  var uriFile = manifestUri.QueryInterface(Ci.nsIFileURL);

  fstream.init(uriFile.file, -1, 0, 0);
  var istream = Cc["@mozilla.org/scriptableinputstream;1"]
      .createInstance(Ci.nsIScriptableInputStream);
  istream.init(fstream);

  var json = istream.read(istream.available());

  return JSON.parse(json);
}

function dumpLine(str) {
  dump(str);
  dump("\n");
}
