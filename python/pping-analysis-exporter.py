#!/usr/bin/python
# NOTE: THIS CODE IS DEPRECATED AND MAY BE REMOVED IN THE FUTURE
#
# To be used with pping running in machine-readable mode
# Pipe pping's output into this script
#   e.g. sudo ./pping -i p0 -f "tcp port 30731" -m | ./pping-analysis-exporter

# TODO: Fix bug where the last line gets cut off (occurs if the
#       buffer isn't large enough to fit all the lines. For example,
#       it could receive the following:
#
#   1567578632.260233 0.001452 0.001452 74 0 66 10.0.0.254:40622+100.200.3.38:9000
#   1567578632.277692 0.001130 0.001130 284 74 210 10.0.0.254:40622+100.200.3.38:9000
#   1567578632.280634 0.001233 0.001130 350 284 132 10.0.0.254:40622+100.200.3.38:90
#
#       The last line has the last two 0's cut off, but it belongs
#       to the same flow as the first two lines.
#
# TODO: Consider time-based vs sample based window?
#       e.g. Should we take median of last x samples, or take
#       the median over the last y seconds?

import os
import sys
import time
import gevent
from select import select

from netaddr import IPAddress, IPNetwork

from gevent import monkey; monkey.patch_all()
from gevent import pywsgi

from collections import deque

from prometheus_client import Gauge
from prometheus_client.core import REGISTRY
from prometheus_client.exposition import generate_latest

if len(sys.argv) != 2:
    print "ERROR: Expecting one parameter, container subnet in CIDR notation (e.g. 100.200.3.0/24)"
    sys.exit(1)
else:
    try:
        CONTAINER_SUBNET = IPNetwork(sys.argv[1])
    except:
        print "ERROR: Incorrect CIDR notation"
        sys.exit(1)

    if CONTAINER_SUBNET.netmask == IPAddress("255.255.255.255"):
        print "ERROR: Cannot use a /32 subnet"
        sys.exit(1)

# Define timeout (in seconds) for inactive flows to persist
FLOW_IDLE_TIMEOUT = 60 * 5 # 5 minutes

# Define flow as a string: "srcIP+dstIP:dstPort"
# Keep a running median (given a sample window size) per flow
WINDOW_SIZE = 20 # Currently use sample-based window

class FlowSamples(object):
    def __init__(self, flow):
        assert type(flow) in (str, unicode)
        self.flow = flow
        self.samples = deque(maxlen=WINDOW_SIZE)
        self.lastUpdated = None

    def append(self, value):
        assert type(value) in (int, long, float)
        self.samples.append(value)
        self.lastUpdated = time.time()

    def getMedian(self):
        # Calculate median
        sortedSamples = sorted(self.samples)
        length = len(sortedSamples)
        if length == 0:
            median = 0
        elif (length % 2) == 0:
            median = (sortedSamples[length / 2 - 1] + sortedSamples[length / 2]) / float(2)
        else:
            median = sortedSamples[length / 2]

        return median

# Maps flows to FlowSamples
flow2samples = {}

# Prometheus exporter
flowMedGauge = Gauge('pping_service_rtt',
                    'Per-flow running median RTT from source IP to a given destination IP/port',
                    ['srcIP', 'dstIP', 'dstPort'])

# Main loop for reading from stdin and calculating the median per flow
def StatsLoop():
    while True:
        rlist, _, _ = select([sys.stdin], [], [], 0)
        if sys.stdin in rlist:
            # When select returns, there may be multiple lines. Using either
            # raw_input() or sys.stdin.readline() would only get the first line,
            # and not the others, and then return to select to block.
            #
            # Workaround: Use os.read() with a large buffer size (e.g. 4 KB),
            # and hopefully that much data won't come in at once...
            #
            stdinData = os.read(0, 4096).strip() # 0 = stdin
                                                 # strip() to remove trailing spaces
            lineList = stdinData.split('\n')
        else:
            time.sleep(0.001) # Allow greenthread switch
            continue

        for line in lineList:
            #print "Received input: " + line
            lineItems = line.split()
            if len(lineItems) != 7:
                continue

            try:
                timestamp, rtt, minRtt, _, _, _, flow = lineItems
                rtt = float(rtt) * 1000; # s to ms

                src, dst = flow.split('+')
                srcIP = src.split(':')[0]
                dstIP = dst.split(':')[0]
                dstPort = dst.split(':')[1]

                # Ignore flows where source is a container
                if IPAddress(srcIP) in CONTAINER_SUBNET:
                    continue
                elif not dstPort: # (e.g. dst was '127.0.0.1:')
                    continue
            except:
                import traceback; traceback.print_exc()
                print "Line was:\n%s\n" % line
                continue

            flowKey = srcIP + "+" + dst # srcIP+dstIP:dstPort

            # Add new value to samples
            samples = flow2samples.setdefault(flowKey, FlowSamples(flowKey))
            samples.append(rtt)

            median = samples.getMedian()

            flowMedGauge.labels(srcIP, dstIP, dstPort).set(median)

            print "Flow %s median RTT: %s ms" % (flowKey, median)

        time.sleep(0.001) # Allow greenthread switch


# Remove flows from Prom gauge if they haven't been seen for some time
def FlowExpiryLoop():
    while True:
        for samples in flow2samples.values(): # Copies
            if samples.lastUpdated + FLOW_IDLE_TIMEOUT < time.time():
                print "Removing expired flow: %s" % samples.flow
                flow2samples.pop(samples.flow)

                srcIP, dst = samples.flow.split('+')
                dstIP, dstPort = dst.split(':')

                flowMedGauge.remove(srcIP, dstIP, dstPort)

        time.sleep(1) # Allow greenthread switch


# HTTP WSGI server handler
def handler(env, response):
    if env['PATH_INFO'] == '/metrics':
        response('200 OK', [('Content-Type', 'text/plain')])
        body = generate_latest(REGISTRY)
        return body
    else:
        response('404 Not Found', [('Content-Type', 'text/plain')])
        return b"Not Found\n"

server = pywsgi.WSGIServer(('0.0.0.0', 9876), handler)

# Start main stats loop in separate greenthread
statsLoopGreenlet = gevent.spawn(StatsLoop)

# Start flow expiry loop in seperate greenthread
flowExpiryGreenlet = gevent.spawn(FlowExpiryLoop)

# Start server
server.serve_forever()

# Wait until all greenthreads are gone
gevent.joinall([statsLoopGreenlet, flowExpiryGreenlet])

print "Exiting, bye!"

