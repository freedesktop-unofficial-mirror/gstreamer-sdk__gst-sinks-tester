# GstSinksTester - Interactive tests for GStreamer audio and video sinks
# Copyright (C) 2012 Andoni Morales Alastruey <ylatuya@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import copy

import pygst
pygst.require('0.10')
import gst


class BaseSinkTest(object):

    pipeline = '%(source)s ! capsfilter name=filter ! %(sink)s'
    source = ''
    nbuf = 25
    sink = ''

    def __init__(self, sink_name, test_results):
        self.sink_name = sink_name
        self.test_results = test_results
        sink = gst.element_factory_make(sink_name, 'sink')
        if not sink:
            raise Exception("Sink %s not found" % sink_name)
        self.find_supported_caps()
        self.parse_caps()

    def run(self):
        for caps in self.caps:
            pipeline = gst.parse_launch(self.format_pipeline(caps))
            caps_filter = pipeline.get_by_name('filter')
            caps_filter.set_property('caps', caps)
            pipeline.set_state(gst.STATE_PLAYING)
            state = pipeline.get_state()
            print "Running test for %s with caps %s" % (self.sink_name, caps)
            if state[0] == gst.STATE_CHANGE_FAILURE:
                self.test_results.add_test(self.sink_name, caps, False)
                print "Test failed"
                continue
            res = self.prompt("Is it working???:", ['y', 'n'])
            self.test_results.add_test(self.sink_name, caps, res=='y')
            pipeline.set_state(gst.STATE_NULL)

    def prompt(self, message, options=[]):
        ''' Prompts the user for input with the message and options '''
        if len(options) != 0:
            message = "%s [%s]" % (message, '/'.join(options))
        res = raw_input(message)
        while res not in [str(x) for x in options]:
            res = raw_input(message)
        return res

    def format_pipeline(self, caps):
        return self.pipeline % {'source':self.source, 'nbuf': self.nbuf,
                'caps':caps, 'sink': self.sink_name}

    def find_supported_caps(self):
        sink = gst.parse_launch('%s name=sink' % self.sink_name)
        sink.set_state(gst.STATE_READY)
        sink.get_state()
        self.sink_caps = []
        for pad in sink.sink_pads():
            self.sink_caps.append(pad.get_caps())
        sink.set_state(gst.STATE_NULL)

    def parse_caps(self):
        structs = []
        for caps in self.sink_caps:
            for struct in caps:
                structs.append(self.parse_structure(struct))
        combinations = []
        for s in structs:
            combinations.extend(self.find_combinations(s))
        self.caps = []
        for c in combinations:
            name = c['name']
            del c['name']
            caps = gst.Caps()
            struct = gst.Structure(name)
            for k, v in c.iteritems():
                struct.set_value(k, v)
            caps.append_structure(struct)
            self.caps.append(caps)

    def parse_structure(self, struct):
        parsed_struct = {}
        for i in range(struct.n_fields()):
            name = struct.nth_field_name(i)
            val = struct[name]
            if name == 'framerate':
                val = [gst.Fraction(25, 1)]
            elif hasattr(val, 'type'):
                if val.type == 'fourcc':
                    val = [val]
                elif val.type == 'intrange':
                    if name == 'width' or name == 'height':
                        val.low = max(val.low, 120)
                        val.high = min(val.high, 1280)
                    val = [val.low, val.low + (val.high - val.low) / 2,
                           val.high]
            elif not isinstance(val, list):
                val = [val]
            parsed_struct[name] = val
        parsed_struct['name'] = [struct.get_name()]
        return parsed_struct

    def find_combinations(self, fields):
        combinations = []
        i = 0
        for field in fields:
            if i == 0:
                for value in fields[field]:
                    d = {}
                    d[field] = value
                    for f in fields:
                        if f != field:
                            d[f] = fields[f][0]
                    combinations.append(d)
            else:
                tmp = copy.deepcopy(combinations)
                if len(fields[field]) > 1:
                    for value in fields[field][1:]:
                        for e in tmp:
                            e[field] = value
                    combinations.extend(tmp)
            i += 1
        return combinations


class AudioSinkTest(BaseSinkTest):
    source = 'audiotestsrc'


class VideoSinkTest(BaseSinkTest):
    source = 'videotestsrc'


class Test(object):

    def __new__(klass, sink_name, test_results):
        sink = gst.element_factory_find(sink_name)
        if not sink:
            raise Exception("Sink %s not found" % sink_name)
        if sink.get_klass() == 'Sink/Video':
            klass = VideoSinkTest
        elif sink.get_klass() == 'Sink/Audio':
            klass = AudioSinkTest
        else:
            raise Exception("Sink %s is not and audio or video sink" % sink_name)
        return klass(sink_name, test_results)


