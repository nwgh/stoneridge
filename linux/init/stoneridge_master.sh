#!/bin/bash
#
# stoneridge_master	Stone Ridge master setup
# 
# chkconfig: 2345 98 09
# description: stoneridge_master is responsible for serving builds and \
#              uploading results to the graph server

### BEGIN INIT INFO
# Provides: stoneridge master
# Required-Start: $local_fs $network
# Required-Stop: $local_fs $network
# Default-Start: 2 3 4 5
# Default-Stop: 0 1 6
# Short-Description: Start and stop stoneridge master
# Description: stoneridge serves builds and uploads results
### END INIT INFO

### BEGIN CONFIGURATION SECTION
SRHOME=/home/hurley/srhome
CONFFILE=$SRHOME/stoneridge.ini
### END CONFIGURATION SECTION

SRROOT=$SRHOME/stoneridge
SRRUN=$SRROOT/srrun.py
MASTERPID=$SRHOME/srmaster.pid
MASTERLOG=$SRHOME/srmaster.log
REPORTERPID=$SRHOME/srreporter.pid
REPORTERLOG=$SRHOME/srreporter.log

start() {
    python $SRRUN $SRROOT/srmaster.py --config $CONFFILE --pidfile $MASTERPID --log $MASTERLOG
    python $SRRUN $SRROOT/srreporter.py --config $CONFFILE --pidfile $REPORTERPID --log $REPORTERLOG
}

stop() {
    kill $(cat $REPORTERPID)
    kill $(cat $MASTERPID)
}

case "$1" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  restart|force-reload|reload)
    stop
    start
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|reload|force-reload}"
    exit 2
esac
