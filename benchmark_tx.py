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

from gnuradio import gr
from gnuradio import blocks
from gnuradio import eng_notation
from gnuradio import uhd  
from gnuradio import analog  
from gnuradio.eng_option import eng_option
from optparse import OptionParser

# From gr-digital
from gnuradio import digital

# from current dir
from transmit_path import transmit_path
from uhd_interface import uhd_transmitter

import time, struct
import socket
import random
#import os 
#print os.getpid()
#raw_input('Attach and press enter')

class my_top_block(gr.top_block):
    def __init__(self, modulator, options):
        gr.top_block.__init__(self)

        if(options.tx_freq is not None):
            # Work-around to get the modulation's bits_per_symbol
            args = modulator.extract_kwargs_from_options(options)
            symbol_rate = options.bitrate / modulator(**args).bits_per_symbol()

            self.sink = uhd_transmitter(options.args, symbol_rate,
                                        options.samples_per_symbol, options.tx_freq,
                                        options.lo_offset, options.tx_gain,
                                        options.spec, options.antenna,
                                        options.clock_source, options.verbose)
            options.samples_per_symbol = self.sink._sps
            
        elif(options.to_file is not None):
            sys.stderr.write(("Saving samples to '%s'.\n\n" % (options.to_file)))
            self.sink = blocks.file_sink(gr.sizeof_gr_complex, options.to_file)
        else:
            sys.stderr.write("No sink defined, dumping samples to null sink.\n\n")
            self.sink = blocks.null_sink(gr.sizeof_gr_complex)

        # do this after for any adjustments to the options that may
        # occur in the sinks (specifically the UHD sink)
        self.txpath = transmit_path(modulator, options)
        
        alpha = 0.001  
        thresh = 20  
        self.probe = analog.probe_avg_mag_sqrd_c(thresh,alpha)   
 
        self.source = uhd.usrp_source(  
            ",".join(("", "")),
            uhd.stream_args(
            cpu_format="fc32",
            channels=range(1),
            ),
	)
	self.source.set_samp_rate(self.sink._rate)  
	self.source.set_center_freq(uhd.tune_request(options.tx_freq,0))  
	self.source.set_gain(options.tx_gain)  
   
        self.connect(self.source, self.probe)       

	self.connect(self.txpath, self.sink)
        print >> sys.stderr, options

# /////////////////////////////////////////////////////////////////////////////
#                                   main
# /////////////////////////////////////////////////////////////////////////////

def main():
    
    random.seed(os.urandom(100))

    def send_pkt(payload='', eof=False):
        return tb.txpath.send_pkt(payload, eof)

    mods = digital.modulation_utils.type_1_mods()

    parser = OptionParser(option_class=eng_option, conflict_handler="resolve")
    expert_grp = parser.add_option_group("Expert")

    parser.add_option("-m", "--modulation", type="choice", choices=mods.keys(),
                      default='gmsk',
                      help="Select modulation from: %s [default=%%default]"
                            % (', '.join(mods.keys()),))

    parser.add_option("-s", "--size", type="eng_float", default=1500,
                      help="set packet size [default=%default]")
    parser.add_option("-M", "--megabytes", type="eng_float", default=1.0,
                      help="set megabytes to transmit [default=%default]")
    parser.add_option("","--discontinuous", action="store_true", default=False,
                      help="enable discontinous transmission (bursts of 5 packets)")
    parser.add_option("","--from-file", default=None,
                      help="use intput file for packet contents")
    parser.add_option("","--to-file", default=None,
                      help="Output file for modulated samples")
    parser.add_option("-E", "--exp-id", type="string", default="test",
                          help="specify the experiment ID")
    parser.add_option("-N", "--node-id", type="string", default="tx",
                          help="specify the experiment ID")
    parser.add_option("","--server", action="store_true", default=False,
                      help="To take data from the server")
    parser.add_option("", "--port", type="int", default=None,
                          help="specify the server port")

    transmit_path.add_options(parser, expert_grp)
    uhd_transmitter.add_options(parser)

    for mod in mods.values():
        mod.add_options(expert_grp)

    (options, args) = parser.parse_args ()


    omlDb = OMLBase("gnuradiorx",options.exp_id,options.node_id,"tcp:nitlab3.inf.uth.gr:3003")
    omlDb.addmp("packets", "type:string value:long")

    omlDb.start()


    if len(args) != 0:
        parser.print_help()
        sys.exit(1)
           
    if options.from_file is not None:
        source_file = open(options.from_file, 'r')

    # build the graph
    tb = my_top_block(mods[options.modulation], options)

    r = gr.enable_realtime_scheduling()
    if r != gr.RT_OK:
        print "Warning: failed to enable realtime scheduling"

    tb.start()                       # start flow graph
        
    # generate and send packets
    nbytes = int(1e6 * options.megabytes)
    n = 0
    pktno = 0
    pkt_size = int(options.size)

    # connect to server
    if options.server:
    	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#	server_address = ('10.0.1.200', 51000)
        server_address = ('10.0.1.200', options.port)
    	print >>sys.stderr, 'connecting to %s port %s' % server_address
    	sock.connect(server_address)
    	


    freq_list = [options.tx_freq, options.tx_freq+1000000.0, options.tx_freq-1000000.0]


    payload_buffer = []
    curr_freq = best_freq= options.tx_freq
    while pktno<1000:
	if options.server:
            data = "";
            while len(data) < pkt_size:
		if (pktno<1000):
                    data += sock.recv(pkt_size - len(data))
                if data == '':
                    # No more data received from server
                    sock.close()
                    break;
        elif options.from_file is None:
            data = (pkt_size - 2) * chr(pktno & 0xff)
        else:
            data = source_file.read(pkt_size - 2)
            if data == '':
                break;

        if pktno%200==0:
			time.sleep(0.7)
			tb.source.set_center_freq(uhd.tune_request(curr_freq,0))
			time.sleep(0.01)
			
			if(tb.probe.level()>0.15): #find best freq
				lowest=3
				i=0
				for i in range (len(freq_list)):
					#if freq_list[i]!=curr_freq:
					tb.source.set_center_freq(uhd.tune_request(freq_list[i],0))
					time.sleep(0.01)
					measurement = tb.probe.level()
					if measurement<lowest:
						lowest = measurement
						best_freq = freq_list[i]
				curr_freq = best_freq
				tb.sink.set_freq(best_freq,0)
				


        payload = struct.pack('!H', pktno & 0xffff) + data
        send_pkt(payload)
        payload_buffer.insert(pktno,payload)
        n += len(payload)
        sys.stderr.write('.')
        omlDb.inject("packets", ("sent", pktno))
        if options.discontinuous and pktno % 5 == 4:
            time.sleep(1)
        pktno += 1
        
    i=0
    while(1):
		if i==40 :#problematic packets
			for k in range(0,5):
				send_pkt(payload_buffer[k*200+199])
				send_pkt(payload_buffer[k*200])
				
				
		if i%200==0:
			time.sleep(0.7)
			tb.source.set_center_freq(uhd.tune_request(curr_freq,0))
			time.sleep(0.01)
			if(tb.probe.level()>0.15): #find best freq
				
				
				
				lowest=3
				for j in range (len(freq_list)):
					#if freq_list[j]!=curr_freq:
					tb.source.set_center_freq(uhd.tune_request(freq_list[j],0))
					time.sleep(0.01)
					measurement = tb.probe.level()
					if measurement<lowest:
						lowest = measurement
						best_freq = freq_list[j]
				curr_freq = best_freq
				tb.sink.set_freq(best_freq,0)
				
				

		send_pkt(payload_buffer[i%1000])
		i+=1

    send_pkt(eof=True)

    tb.wait()                       # wait for it to finish

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
