#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: ADS-B Receiver
# Author: Matt Hostetter
# GNU Radio version: 3.8.1.0

from distutils.version import StrictVersion

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print("Warning: failed to XInitThreads()")

from PyQt5 import Qt
from gnuradio import eng_notation
from gnuradio import analog
from gnuradio import blocks
from gnuradio import gr
from gnuradio.filter import firdes
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import zeromq
from gnuradio import qtgui

class app(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "ADS-B Receiver")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("ADS-B Receiver")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
            pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "app")

        try:
            if StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
                self.restoreGeometry(self.settings.value("geometry").toByteArray())
            else:
                self.restoreGeometry(self.settings.value("geometry"))
        except:
            pass

        ##################################################
        # Variables
        ##################################################
        self.threshold = threshold = 0.010
        self.select_index = select_index = 0
        self.gain = gain = 100
        self.fs = fs = int(2e6)
        self.fc = fc = int(88.1e6)

        ##################################################
        # Blocks
        ##################################################
        self.zeromq_pub_sink_2 = zeromq.pub_sink(gr.sizeof_gr_complex, 1, 'tcp://127.0.0.1:5004', 10, False, -1)
        self.zeromq_pub_sink_1 = zeromq.pub_sink(gr.sizeof_gr_complex, 1, 'tcp://127.0.0.1:5003', 10, False, -1)
        self._threshold_tool_bar = Qt.QToolBar(self)
        self._threshold_tool_bar.addWidget(Qt.QLabel('Detection Threshold' + ": "))
        self._threshold_line_edit = Qt.QLineEdit(str(self.threshold))
        self._threshold_tool_bar.addWidget(self._threshold_line_edit)
        self._threshold_line_edit.returnPressed.connect(
            lambda: self.set_threshold(eng_notation.str_to_num(str(self._threshold_line_edit.text()))))
        self.top_grid_layout.addWidget(self._threshold_tool_bar, 0, 1, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.blocks_throttle_1 = blocks.throttle(gr.sizeof_gr_complex*1, 32000,True)
        self.blocks_throttle_0 = blocks.throttle(gr.sizeof_gr_complex*1, 32000,True)
        self.blocks_delay_0 = blocks.delay(gr.sizeof_gr_complex*1, 512)
        self.blocks_add_xx_1 = blocks.add_vcc(1)
        self.blocks_add_xx_0 = blocks.add_vcc(1)
        self.analog_noise_source_x_1 = analog.noise_source_c(analog.GR_GAUSSIAN, 1, 0)
        self.analog_noise_source_x_0 = analog.noise_source_c(analog.GR_GAUSSIAN, 1, 0)



        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_noise_source_x_0, 0), (self.blocks_throttle_0, 0))
        self.connect((self.analog_noise_source_x_1, 0), (self.blocks_throttle_1, 0))
        self.connect((self.blocks_add_xx_0, 0), (self.zeromq_pub_sink_1, 0))
        self.connect((self.blocks_add_xx_1, 0), (self.zeromq_pub_sink_2, 0))
        self.connect((self.blocks_delay_0, 0), (self.blocks_add_xx_1, 0))
        self.connect((self.blocks_throttle_0, 0), (self.blocks_add_xx_0, 1))
        self.connect((self.blocks_throttle_0, 0), (self.blocks_add_xx_1, 1))
        self.connect((self.blocks_throttle_1, 0), (self.blocks_add_xx_0, 0))
        self.connect((self.blocks_throttle_1, 0), (self.blocks_delay_0, 0))

    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "app")
        self.settings.setValue("geometry", self.saveGeometry())
        event.accept()

    def get_threshold(self):
        return self.threshold

    def set_threshold(self, threshold):
        self.threshold = threshold
        Qt.QMetaObject.invokeMethod(self._threshold_line_edit, "setText", Qt.Q_ARG("QString", eng_notation.num_to_str(self.threshold)))

    def get_select_index(self):
        return self.select_index

    def set_select_index(self, select_index):
        self.select_index = select_index

    def get_gain(self):
        return self.gain

    def set_gain(self, gain):
        self.gain = gain

    def get_fs(self):
        return self.fs

    def set_fs(self, fs):
        self.fs = fs

    def get_fc(self):
        return self.fc

    def set_fc(self, fc):
        self.fc = fc



def main(top_block_cls=app, options=None):

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()
    tb.start()
    tb.show()

    def sig_handler(sig=None, frame=None):
        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    def quitting():
        tb.stop()
        tb.wait()
    qapp.aboutToQuit.connect(quitting)
    qapp.exec_()


if __name__ == '__main__':
    main()
