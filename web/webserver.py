#!/usr/bin/env python3
"""
MARP — Multi-Application Radio Platform
webserver.py — Unified Flask/SocketIO server supporting ADS-B, FM, and Passive Radar
"""

from gevent import monkey
monkey.patch_all()

import time
import os
import json
from flask import Flask, request, send_from_directory, jsonify
from flask_socketio import SocketIO
from threading import Thread
import zmq.green as zmq

try:
    import pmt
    HAS_PMT = True
except ImportError:
    print("WARNING: pmt not available, ZMQ messages will be raw bytes")
    HAS_PMT = False

# ── Network config ────────────────────────────────────────────
HTTP_ADDRESS = "0.0.0.0"
HTTP_PORT    = 5000
ZMQ_ADDRESS  = "127.0.0.1"

# One ZMQ port per application (GNU Radio flowgraph ZMQ PUB sinks)
ZMQ_PORTS = {
    "adsb":  5001,
    "fm":    5002,
    "radar": 5003,
}

# Reverse channel: server → GNU Radio (ZMQ PUB, GR ZMQ SUB Message Source)
ZMQ_CONTROL_PORT = 5010

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# ── App state ─────────────────────────────────────────────────
state = {
    "mode":          "adsb",   # active application
    "zmq_connected": False,    # at least one ZMQ message received recently
    "params": {
        "adsb":  {"center_freq": 1090e6, "gain": 50},
        "fm":    {"center_freq":  96.7e6, "gain": 40, "volume": 80},
        "radar": {"center_freq":  95.0e6, "gain": 50, "integration_time": 1.0},
    }
}

# ── Flask / SocketIO ──────────────────────────────────────────
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.config["SECRET_KEY"] = "marp-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# ── ZMQ control socket (server → GNU Radio) ───────────────────
_ctrl_context = zmq.Context()
_ctrl_socket  = _ctrl_context.socket(zmq.PUB)
_ctrl_socket.bind("tcp://0.0.0.0:{:d}".format(ZMQ_CONTROL_PORT))
print("ZMQ control socket bound on port {}".format(ZMQ_CONTROL_PORT))


def send_control_message(app_name, params):
    """Send a parameter update to GNU Radio via ZMQ PUB → GR ZMQ SUB."""
    if not HAS_PMT:
        print("Cannot send control: pmt not available")
        return
    try:
        payload = dict(params)
        payload["app"] = app_name
        meta      = pmt.to_pmt(payload)
        pdu       = pmt.cons(meta, pmt.make_u8vector(0, 0))
        _ctrl_socket.send(pmt.serialize_str(pdu))
        print("Control message sent for app={} params={}".format(app_name, params))
    except Exception as e:
        print("Control send error:", e)


def make_zmq_thread(app_name, port):
    def _thread():
        context = zmq.Context()
        socket  = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        socket.connect("tcp://{}:{:d}".format(ZMQ_ADDRESS, port))
        print("ZMQ listener [{:6s}] connected to tcp://{}:{}".format(app_name.upper(), ZMQ_ADDRESS, port))

        while True:
            try:
                pdu_bin = socket.recv()
                state["zmq_connected"] = True
                socketio.emit("serverStatus", {"zmq_connected": True})

                if HAS_PMT:
                    pdu  = pmt.deserialize_str(pdu_bin)
                    data = pmt.to_python(pmt.car(pdu))
                else:
                    data = {"raw": pdu_bin.hex(), "app": app_name}

                if state["mode"] == app_name:
                    if app_name == "adsb":
                        socketio.emit("updatePlane", data)
                    elif app_name == "radar":
                        socketio.emit("updateRadar", data)

                print("[{}] {}".format(app_name.upper(), data))

            except Exception as e:
                print("ZMQ error [{}]: {}".format(app_name, e))
                time.sleep(1)

    return _thread


def make_fm_zmq_thread(port):
    def _thread():
        import numpy as np
        import base64

        context = zmq.Context()
        socket  = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        socket.connect("tcp://{}:{:d}".format(ZMQ_ADDRESS, port))
        print("ZMQ listener [FM    ] connected to tcp://{}:{}".format(ZMQ_ADDRESS, port))

        spectrum_counter = 0

        while True:
            try:
                raw = socket.recv()          # raw float32 bytes from ZMQ PUB Sink
                state["zmq_connected"] = True
                socketio.emit("serverStatus", {"zmq_connected": True})

                if state["mode"] != "fm":
                    continue                 # still drain the socket, just don't emit

                samples = np.frombuffer(raw, dtype=np.float32)

                # Signal power
                power_db = float(10 * np.log10(np.mean(samples**2) + 1e-12))

                # Spectrum — only compute every 4th chunk to save CPU
                spectrum = None
                spectrum_counter += 1
                if spectrum_counter % 4 == 0:
                    window   = np.hanning(len(samples))
                    fft_vals = np.fft.rfft(samples * window)
                    spectrum = (20 * np.log10(np.abs(fft_vals) / len(samples) + 1e-12)).tolist()
                    spectrum = spectrum[::4]  # decimate for display

                # Audio — base64 encode raw float32 PCM for Web Audio API
                audio_b64 = base64.b64encode(raw).decode("ascii")

                socketio.emit("updateFM", {
                    "audio":      audio_b64,
                    "signal_db":  power_db,
                    "spectrum":   spectrum,   # None on skipped frames, frontend handles it
                    "center_freq": state["params"]["fm"]["center_freq"],
                })

            except Exception as e:
                print("ZMQ error [FM]: {}".format(e))
                time.sleep(0.1)   # short sleep — audio is time-sensitive

    return _thread

# ── REST API ──────────────────────────────────────────────────

@app.route("/api/mode", methods=["GET"])
def get_mode():
    return jsonify({"mode": state["mode"]})


@app.route("/api/mode", methods=["POST"])
def set_mode():
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "").lower()
    if mode not in ZMQ_PORTS:
        return jsonify({"error": "Unknown mode. Choose: {}".format(list(ZMQ_PORTS.keys()))}), 400
    state["mode"] = mode
    print("Mode switched to:", mode)
    socketio.emit("modeChanged", {"mode": mode})
    return jsonify({"mode": mode, "ok": True})


@app.route("/api/params", methods=["GET"])
def get_params():
    return jsonify({"params": state["params"], "mode": state["mode"]})


@app.route("/api/params", methods=["POST"])
def set_params():
    body = request.get_json(silent=True) or {}
    app_name = body.get("app", state["mode"]).lower()
    params   = body.get("params", {})

    if app_name not in state["params"]:
        return jsonify({"error": "Unknown app"}), 400

    # Merge incoming params
    state["params"][app_name].update(params)

    # Forward to GNU Radio
    send_control_message(app_name, state["params"][app_name])

    return jsonify({"ok": True, "app": app_name, "params": state["params"][app_name]})


@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({
        "mode":          state["mode"],
        "zmq_connected": state["zmq_connected"],
        "zmq_ports":     ZMQ_PORTS,
        "control_port":  ZMQ_CONTROL_PORT,
    })


# ── Static file serving ───────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:filename>")
def static_fallback(filename):
    return send_from_directory(STATIC_DIR, filename)


# ── SocketIO events ───────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    print("Client connected:", request.sid)
    # Send current state to newly connected client
    socketio.emit("serverStatus", {"zmq_connected": state["zmq_connected"]}, room=request.sid)
    socketio.emit("modeChanged",  {"mode": state["mode"]},                   room=request.sid)


@socketio.on("disconnect")
def on_disconnect():
    print("Client disconnected:", request.sid)


# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Static dir:", STATIC_DIR)
    print("Starting MARP server on {}:{}".format(HTTP_ADDRESS, HTTP_PORT))

    # ADS-B and Radar use the PMT message thread
    for app_name in ["adsb", "radar"]:
        t = Thread(target=make_zmq_thread(app_name, ZMQ_PORTS[app_name]))
        t.daemon = True
        t.start()

    # FM uses the raw float32 stream thread
    t = Thread(target=make_fm_zmq_thread(ZMQ_PORTS["fm"]))
    t.daemon = True
    t.start()

    socketio.run(app, host=HTTP_ADDRESS, port=HTTP_PORT,
                 debug=True, use_reloader=False)