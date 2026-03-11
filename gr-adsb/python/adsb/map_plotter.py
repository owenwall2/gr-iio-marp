#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 Mason Vari.
#
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#


import pmt
from gnuradio import gr
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

class map_plotter(gr.basic_block):
    """
    MARP Live 2D Aerial Map
    Receives ADS-B position messages and plots planes on a pyqtgraph map.
    Works perfectly with gr-adsb Decoder over xQuartz on Mac.
    """
    def __init__(self, home_lat=34.685, home_lon=-82.953):  # Default = Seneca, SC
        gr.basic_block.__init__(self, name="Aerial Map", in_sig=None, out_sig=None)

        # Register the message input port (this is what you connect in GRC)
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)

        self.home_lat = home_lat
        self.home_lon = home_lon
        self.planes = {}          # callsign -> (lat, lon, alt)

        # Create standalone pyqtgraph window (pops up via xQuartz)
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        self.win = pg.GraphicsLayoutWidget(title="MARP Plane Tracker - Live 2D Aerial Map")
        self.win.resize(900, 700)
        self.win.show()

        self.plot = self.win.addPlot(title="Live Planes Around Seneca, SC (1090 MHz ADS-B)")
        self.plot.setLabels(left="Latitude (°)", bottom="Longitude (°)")
        self.plot.setXRange(home_lon - 1.5, home_lon + 1.5)
        self.plot.setYRange(home_lat - 1.5, home_lat + 1.5)
        self.plot.showGrid(x=True, y=True)

        # Red dots for planes + home location
        self.scatter = pg.ScatterPlotItem(size=14, pen=pg.mkPen(None), brush=pg.mkBrush(255, 0, 0, 220))
        self.home_dot = pg.ScatterPlotItem(size=12, pen=pg.mkPen(None), brush=pg.mkBrush(0, 255, 0, 255))
        self.plot.addItem(self.scatter)
        self.plot.addItem(self.home_dot)
        self.home_dot.setData([home_lon], [home_lat])   # Green home dot

        # Timer for smooth live updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_map)
        self.timer.start(500)  # 2 Hz refresh

    def handle_msg(self, msg_pmt):
        """Called automatically every time ADS-B Decoder sends a message"""
        try:
            msg = pmt.to_python(msg_pmt)
            if isinstance(msg, dict):
                callsign = msg.get("callsign", "UNK-" + msg.get("icao", "????"))
                lat = msg.get("lat")
                lon = msg.get("lon")
                alt = msg.get("alt", 0)

                if lat is not None and lon is not None:
                    self.planes[callsign] = (lat, lon, alt)
                    # Optional debug print (remove later if you want)
                    # print(f"Plane: {callsign} @ {lat:.4f}, {lon:.4f}  Alt: {alt} ft")
        except Exception:
            pass  # Silently ignore malformed messages

    def update_map(self):
        """Redraw the scatter plot every 500 ms"""
        if not self.planes:
            return

        lons = [self.home_lon] + [pos[1] for pos in self.planes.values()]
        lats = [self.home_lat] + [pos[0] for pos in self.planes.values()]

        self.scatter.setData(lons, lats)

        # Optional: auto-zoom to keep all planes visible (uncomment if you like)
        # self.plot.enableAutoRange()