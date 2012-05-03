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

import gst
import gtk


class BaseSinkTest(object):

    pipeline_tpl = '%(source)s ! capsfilter name=filter ! %(sink)s name=sink'
    source = ''
    nbuf = 25
    sink = ''

    def __init__(self, sink_name, test_results):
        self.sink_name = sink_name
        self.test_results = test_results
        sink = gst.element_factory_make(sink_name, 'sink')
        if not sink:
            raise Exception("Sink %s not found" % sink_name)
        self._find_supported_caps()
        self._parse_caps()
        self._create_window()

    def run(self):
        self.window.show_all()
        self.test_index = 0
        self._run_next_test()

    def _run_next_test(self):
        self.test_index += 1
        if self.test_index > len(self.caps):
            return self._quit()
        self.cur_caps = self.caps[self.test_index - 1]
        self.pipeline = gst.parse_launch(self._format_pipeline(self.cur_caps))
        caps_filter = self.pipeline.get_by_name('filter')
        caps_filter.set_property('caps', self.cur_caps)
        self._prepare_pipeline()
        self.pipeline.set_state(gst.STATE_PLAYING)
        state = self.pipeline.get_state()
        print "Running test for %s with caps %s" % (self.sink_name, self.cur_caps)
        if state[0] == gst.STATE_CHANGE_FAILURE:
            self.test_results.add_test(self.sink_name, self.cur_caps, False)
            self._button_clicked(self.nobutton, False)
        else:
            self._set_buttons_sensitive(True)

    def _prepare_pipeline(self):
        pass

    def _create_window(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event", self._delete_event)
        self.window.connect("destroy", self._destroy)

        # Create widgets
        vbox = gtk.VBox()
        self.video = gtk.DrawingArea()
        label = gtk.Label('Is it working?')
        buttonsbox = gtk.HBox()
        self.yesbutton = gtk.Button(stock='gtk-yes')
        self.nobutton = gtk.Button(stock='gtk-no')

        # Connect signals
        self.window.connect('delete_event', self._delete_event)
        self.window.connect('destroy', self._destroy)
        self.yesbutton.connect('clicked', self._button_clicked, True)
        self.nobutton.connect('clicked', self._button_clicked, False)

        # Pack
        buttonsbox.pack_start(self.yesbutton, expand=True, fill=True)
        buttonsbox.pack_start(self.nobutton, expand=True, fill=True)
        vbox.pack_start(self.video, expand=True, fill=True)
        vbox.pack_start(label, expand=False, fill=True)
        vbox.pack_start(buttonsbox, expand=False, fill=True)
        self.window.add(vbox)
        self.window.set_position(gtk.WIN_POS_CENTER)
        self.window.resize(320, 240)

    def _quit(self):
        self.test_results.save()
        gtk.mainquit()

    def _delete_event(self, widget, event, data=None):
        return gtk.FALSE

    def _destroy(self, widget, data=None):
        self._quit()

    def _button_clicked(self, widget, result):
        self.test_results.add_test(self.sink_name, self.cur_caps, result)
        self.pipeline.set_state(gst.STATE_NULL)
        self._set_buttons_sensitive(False)
        self._run_next_test()

    def _set_buttons_sensitive(self, sensitive):
        self.yesbutton.set_sensitive(sensitive)
        self.nobutton.set_sensitive(sensitive)

    def _format_pipeline(self, caps):
        return self.pipeline_tpl % {'source':self.source, 'nbuf': self.nbuf,
                'caps':caps, 'sink': self.sink_name}

    def _find_supported_caps(self):
        sink = gst.parse_launch('%s name=sink' % self.sink_name)
        sink.set_state(gst.STATE_READY)
        sink.get_state()
        self.sink_caps = []
        for pad in sink.sink_pads():
            self.sink_caps.append(pad.get_caps())
        sink.set_state(gst.STATE_NULL)

    def _parse_caps(self):
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
                if val.type == 'intrange':
                    if name == 'width' or name == 'height':
                        val.low = max(val.low, 120)
                        val.high = min(val.high, 1280)
                    elif name == 'rate':
                        val.low = max(val.low, 4000)
                        val.high = min(val.high, 96000)
                    val = [val.low, val.low + (val.high - val.low) / 2,
                           val.high]
                else:
                    val = [val]
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

    def _prepare_pipeline(self):
        bus = self.pipeline.get_bus()
        bus.set_sync_handler(self.bus_handler)

    def bus_handler(self, bus, message):
        if message.type == gst.MESSAGE_ELEMENT:
            if message.structure.get_name() == "prepare-xwindow-id":
                sink = message.src
                sink.set_property("force-aspect-ratio", True)
                self.set_xwindow_id(sink)
        return gst.BUS_PASS

    def _redraw(self):
        x, y, width, height = self.video.get_allocation()
        pixmap = gtk.gdk.Pixmap(self.video.window, width, height)
        pixmap.draw_rectangle(self.video.get_style().black_gc,
                              True, 0, 0, width, height)
        self.video.queue_draw_area(0, 0, width, height)

    def set_xwindow_id(self, sink):
        gtk.gdk.threads_enter()
        try:
            # Linux
            wid = self.video.window.xid
        except AttributeError:
            # Windows
            wid = self.video.window.handle
        sink.set_xwindow_id(wid)
        self._redraw()
        gtk.gdk.threads_leave()


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


