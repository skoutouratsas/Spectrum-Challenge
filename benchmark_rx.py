#!/usr/bin/env python
#
# Copyright 2010,2011,2013 Free Software Foundation, Inc.
# 
# This file is part of GNU Radio
# 
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 
from oml4py import OMLBase

import sys, os

path = os.path.dirname(sys.argv[0]).split("share")[0] + "lib/python2.7/dist-packages"
sys.path.append(path)

os.environ['SHELL'] = "/bin/bash"
os.environ['LC_ALL'] = 'C'
os.environ['LANG'] = 'C'
os.environ['PYTHONPATH'] = os.path.dirname(sys.argv[0]).split("share")[0] +'lib/python2.7/dist-packages'
os.environ['PKG_CONFIG_PATH'] = os.path.dirname(sys.argv[0]).split("share")[0] +'lib/pkgconfig'

from gnuradio import gr, gru
from gnuradio import blocks
from gnuradio import eng_notation
from gnuradio.eng_option import eng_option
from optparse import OptionParser
from gnuradio import analog  
# From gr-digital
from gnuradio import digital
from gnuradio import uhd
# from current dir
from receive_path import receive_path
from uhd_interface import uhd_receiver
import time
import struct
import socket
import random
#import os
#print os.getpid()
#raw_input('Attach and press enter: ')

class my_top_block(gr.top_block):
    def __init__(self, demodulator, rx_callback, options):
        gr.top_block.__init__(self)

        if(options.rx_freq is not None):


#	    new_freq=random.choice([1804500000.0, 1803000000.0, 1801500000.0])
           # sys.stderr.write(("Receiver FREQ '%s'.\n\n" % (new_freq)))
            # Work-around to get the modulation's bits_per_symbol
            args = demodulator.extract_kwargs_from_options(options)
            symbol_rate = options.bitrate / demodulator(**args).bits_per_symbol()

            self.source = uhd_receiver(options.args, symbol_rate,
                                       options.samples_per_symbol,options.rx_freq, 
                                       options.lo_offset, options.rx_gain,
                                       options.spec, options.antenna,
                                       options.clock_source, options.verbose)
            options.samples_per_symbol = self.source._sps

        elif(options.from_file is not None):
            sys.stderr.write(("Reading samples from '%s'.\n\n" % (options.from_file)))
            self.source = blocks.file_source(gr.sizeof_gr_complex, options.from_file)
        else:
            sys.stderr.write("No source defined, pulling samples from null source.\n\n")
            self.source = blocks.null_source(gr.sizeof_gr_complex)

        # Set up receive path
        # do this after for any adjustments to the options that may
        # occur in the sinks (specifically the UHD sink)
        self.rxpath = receive_path(demodulator, rx_callback, options) 

        self.connect(self.source, self.rxpath)
        print >> sys.stderr, options




        #alpha = 0.001  
	#thresh = 30  	
	#self.probe = analog.probe_avg_mag_sqrd_c(thresh,alpha)   


	#self.source1 = uhd.usrp_source(  
            #",".join(("", "")),
            #uhd.stream_args(
            #cpu_format="fc32",
            #channels=range(1),
            #),
	#)
	#self.source1.set_samp_rate(symbol_rate) 
	#self.source1.set_gain(47.0)
	#self.source1.set_center_freq(uhd.tune_request(new_freq, 0))  
        #self.source1.set_antenna("TX/RX")

	#self.connect(self.source1, self.probe)  
# /////////////////////////////////////////////////////////////////////////////
#                                   main
# /////////////////////////////////////////////////////////////////////////////

global n_rcvd, n_right ,nopkt,start

def main():
    global n_rcvd, n_right,nopkt,start

    random.seed(os.urandom(100))

    n_rcvd = 0
    n_right = 0
    nopkt = 1
    
    def rx_callback(ok, payload):
        global n_rcvd, n_right,start,nopkt
        (pktno,) = struct.unpack('!H', payload[0:2])
        data = payload[2:]
        n_rcvd += 1
        
        if ok:
            nopkt = 0
            n_right += 1
            if options.server:
                sock.sendall(data)
#                if n_right == 1000:
#					print "JSHABJKWHBEWJQKBEHWQKJWQEJWQRKBKJWQRBOJWRQB\n"
#					sock.close()
        start = time.time()
        #print "ok = %5s  pktno = %4d  n_rcvd = %4d  n_right = %4d" % (
            #ok, pktno, n_rcvd, n_right)
        omlDb.inject("packets", ("received", n_rcvd))
        omlDb.inject("packets", ("correct", n_right))

    demods = digital.modulation_utils.type_1_demods()

    # Create Options Parser:
    parser = OptionParser (option_class=eng_option, conflict_handler="resolve")
    expert_grp = parser.add_option_group("Expert")

    parser.add_option("-m", "--modulation", type="choice", choices=demods.keys(), 
                      default='gmsk',
                      help="Select modulation from: %s [default=%%default]"
                            % (', '.join(demods.keys()),))
    parser.add_option("","--from-file", default=None,
                      help="input file of samples to demod")
    parser.add_option("-E", "--exp-id", type="string", default="test",
                          help="specify the experiment ID")
    parser.add_option("-N", "--node-id", type="string", default="rx",
                          help="specify the experiment ID")
    parser.add_option("","--server", action="store_true", default=False,
                      help="To take data from the server")
    parser.add_option("", "--port", type="int", default=None,
                          help="specify the server port")

    receive_path.add_options(parser, expert_grp)
    uhd_receiver.add_options(parser)

    for mod in demods.values():
        mod.add_options(expert_grp)

    (options, args) = parser.parse_args ()


    omlDb = OMLBase("gnuradiorx",options.exp_id,options.node_id,"tcp:nitlab3.inf.uth.gr:3003")
    omlDb.addmp("packets", "type:string value:long")

    omlDb.start()


    if len(args) != 0:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if options.from_file is None:
        if options.rx_freq is None:
            sys.stderr.write("You must specify -f FREQ or --freq FREQ\n")
            parser.print_help(sys.stderr)
            sys.exit(1)

    # connect to server
    if options.server:
    	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#    	server_address = ('10.0.1.200', 51001)
        server_address = ('10.0.1.200', options.port)
    	print >>sys.stderr, 'connecting to %s port %s' % server_address
    	sock.connect(server_address)

    # build the graph
    tb = my_top_block(demods[options.modulation], rx_callback, options)

    r = gr.enable_realtime_scheduling()
    if r != gr.RT_OK:
        print "Warning: Failed to enable realtime scheduling."

    tb.start()        # start flow graph
#    tb.wait()         # wait for it to finish

    freq_list = [options.rx_freq, options.rx_freq+1000000.0, options.rx_freq-1000000.0]
    i=0
    nopkt=1
    while 1:
#		pwr= tb.rxpath.probe.level()
		while (nopkt):
			tb.source.set_freq(freq_list[i%3], 0)
			i+=1
			time.sleep(0.05)
		
		if(time.time()-start > 0.5):
			nopkt=1
		
    if options.server:
    	sock.close()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
