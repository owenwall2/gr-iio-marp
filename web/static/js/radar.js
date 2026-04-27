// ============================================================
// radar.js — Passive Radar module
//
// Expects server payload:
// {
//   map: [[...], [...], ...],      // [doppler][range]
//   range_axis: [...],
//   doppler_bins: [...],
//   transpose: true
// }
//
// This matches Python:
//   plt.imshow(maps_pos[k].T, aspect="auto", origin="lower", ...)
//
// So the display is:
//   X axis = Doppler bin
//   Y axis = Bistatic Path Difference (m)
// ============================================================

var Radar = (function () {
  var _canvas = null;
  var _ctx = null;

  var _globalMin = null;
  var _globalMax = null;
  var _frameCount = 0;

  function init() {
    _canvas = document.getElementById('rd-canvas');
    if (!_canvas) throw new Error('Radar.init(): #rd-canvas not found');

    _ctx = _canvas.getContext('2d');
    if (!_ctx) throw new Error('Radar.init(): 2D context unavailable');
  }

  function reset() {
    _globalMin = null;
    _globalMax = null;
    _frameCount = 0;

    if (_ctx && _canvas) {
      _ctx.clearRect(0, 0, _canvas.width, _canvas.height);
    }

    var ph = document.getElementById('rd-placeholder');
    if (ph) ph.style.display = 'block';

    var lbl = document.getElementById('radar-frame-label');
    if (lbl) lbl.textContent = 'FRAME 0';
  }

  function update(data) {
    if (!_canvas || !_ctx) init();
    if (!data || !data.map || !Array.isArray(data.map) || data.map.length === 0) return;

    var matrix = data.map;
    var rangeAxis = data.range_axis || null;
    var dopplerBins = data.doppler_bins || null;

    // The server sends [doppler][range].
    // We transpose for display so the browser matches plt.imshow(... .T)
    if (data.transpose !== false) {
      matrix = _transpose(matrix);
    }

    var mm = _minMax(matrix);
    if (_globalMin === null) {
      _globalMin = mm.min;
      _globalMax = mm.max;
    } else {
      _globalMin = Math.min(_globalMin, mm.min);
      _globalMax = Math.max(_globalMax, mm.max);
    }

    _frameCount++;

    var ph = document.getElementById('rd-placeholder');
    if (ph) ph.style.display = 'none';

    var lbl = document.getElementById('radar-frame-label');
    if (lbl) lbl.textContent = 'FRAME ' + _frameCount;

    _drawHeatmap(matrix, rangeAxis, dopplerBins);
  }

  function _transpose(matrix) {
    var rows = matrix.length;
    var cols = matrix[0].length;
    var out = new Array(cols);

    for (var c = 0; c < cols; c++) {
      out[c] = new Array(rows);
      for (var r = 0; r < rows; r++) {
        out[c][r] = matrix[r][c];
      }
    }
    return out;
  }

  function _minMax(matrix) {
    var min = Infinity;
    var max = -Infinity;

    for (var r = 0; r < matrix.length; r++) {
      for (var c = 0; c < matrix[r].length; c++) {
        var v = matrix[r][c];
        if (v < min) min = v;
        if (v > max) max = v;
      }
    }

    return { min: min, max: max };
  }

  function _drawHeatmap(matrix, rangeAxis, dopplerBins) {
    var cssW = _canvas.offsetWidth || 800;
    var cssH = _canvas.offsetHeight || 420;

    if (_canvas.width !== cssW || _canvas.height !== cssH) {
      _canvas.width = cssW;
      _canvas.height = cssH;
    }

    var W = _canvas.width;
    var H = _canvas.height;

    var numRows = matrix.length;      // range bins
    var numCols = matrix[0].length;   // doppler bins

    var vmin = -40;
    var vmax = 80;
    var vrange = vmax - vmin;
    if (!isFinite(vrange) || vrange === 0) vrange = 1;

    var ML = 58, MR = 52, MT = 12, MB = 38;
    var plotW = Math.max(1, W - ML - MR);
    var plotH = Math.max(1, H - MT - MB);

    _ctx.fillStyle = '#090d12';
    _ctx.fillRect(0, 0, W, H);

    var imgData = _ctx.createImageData(plotW, plotH);

    for (var py = 0; py < plotH; py++) {
      var rowIdx = Math.round(((plotH - 1 - py) / (plotH - 1)) * (numRows - 1));
      rowIdx = Math.max(0, Math.min(rowIdx, numRows - 1));

      for (var px = 0; px < plotW; px++) {
        var colIdx = Math.round((px / (plotW - 1)) * (numCols - 1));
        colIdx = Math.max(0, Math.min(colIdx, numCols - 1));

        var norm = (matrix[rowIdx][colIdx] - vmin) / vrange;
        if (norm < 0) norm = 0;
        if (norm > 1) norm = 1;

        var rgb = _viridis(norm);
        var idx = (py * plotW + px) * 4;
        imgData.data[idx] = rgb[0];
        imgData.data[idx + 1] = rgb[1];
        imgData.data[idx + 2] = rgb[2];
        imgData.data[idx + 3] = 255;
      }
    }

    var tmp = document.createElement('canvas');
    tmp.width = plotW;
    tmp.height = plotH;
    tmp.getContext('2d').putImageData(imgData, 0, 0);
    _ctx.drawImage(tmp, ML, MT);

    _ctx.strokeStyle = '#1a2d44';
    _ctx.lineWidth = 1;
    _ctx.strokeRect(ML, MT, plotW, plotH);

    // X axis: Doppler bin
    _ctx.font = '10px Share Tech Mono, monospace';
    _ctx.fillStyle = '#4a6a88';
    _ctx.textAlign = 'center';

    var xTicks = 8;
    for (var i = 0; i <= xTicks; i++) {
      var frac = i / xTicks;
      var xPx = ML + frac * plotW;

      _ctx.beginPath();
      _ctx.strokeStyle = '#4a6a88';
      _ctx.moveTo(xPx, MT + plotH);
      _ctx.lineTo(xPx, MT + plotH + 5);
      _ctx.stroke();

      var xLabel;
      if (dopplerBins && dopplerBins.length > 0) {
        var di = Math.round(frac * (dopplerBins.length - 1));
        xLabel = dopplerBins[di].toString();
      } else {
        xLabel = Math.round(frac * (numCols - 1)).toString();
      }

      _ctx.fillText(xLabel, xPx, MT + plotH + 18);
    }

    _ctx.fillStyle = '#c8ddef';
    _ctx.font = '11px Barlow Condensed, sans-serif';
    _ctx.fillText('Doppler bin', ML + plotW / 2, H - 4);

    // Y axis: Bistatic Path Difference (m)
    _ctx.font = '10px Share Tech Mono, monospace';
    var yTicks = 6;

    for (var j = 0; j <= yTicks; j++) {
      var fracY = j / yTicks;
      var yPx = MT + plotH - fracY * plotH;

      _ctx.beginPath();
      _ctx.strokeStyle = '#4a6a88';
      _ctx.moveTo(ML - 5, yPx);
      _ctx.lineTo(ML, yPx);
      _ctx.stroke();

      var yLabel;
      if (rangeAxis && rangeAxis.length > 0) {
        var ri = Math.round(fracY * (rangeAxis.length - 1));
        yLabel = Number(rangeAxis[ri]).toFixed(0);
      } else {
        yLabel = Math.round(fracY * (numRows - 1)).toString();
      }

      _ctx.textAlign = 'right';
      _ctx.fillStyle = '#4a6a88';
      _ctx.fillText(yLabel, ML - 8, yPx + 4);
    }

    _ctx.save();
    _ctx.translate(12, MT + plotH / 2);
    _ctx.rotate(-Math.PI / 2);
    _ctx.textAlign = 'center';
    _ctx.fillStyle = '#c8ddef';
    _ctx.font = '11px Barlow Condensed, sans-serif';
    _ctx.fillText('Bistatic Path Difference (m)', 0, 0);
    _ctx.restore();

    var cbX = ML + plotW + 8;
    _drawColourbar(cbX, MT, 12, plotH, vmin, vmax);
  }

  function _drawColourbar(x, y, w, h, vmin, vmax) {
    var grad = _ctx.createLinearGradient(x, y + h, x, y);
    grad.addColorStop(0, 'rgb(68,1,84)');
    grad.addColorStop(0.25, 'rgb(59,82,139)');
    grad.addColorStop(0.5, 'rgb(33,145,140)');
    grad.addColorStop(0.75, 'rgb(94,201,98)');
    grad.addColorStop(1, 'rgb(253,231,37)');

    _ctx.fillStyle = grad;
    _ctx.fillRect(x, y, w, h);
    _ctx.strokeStyle = '#1a2d44';
    _ctx.strokeRect(x, y, w, h);

    _ctx.font = '9px Share Tech Mono, monospace';
    _ctx.fillStyle = '#4a6a88';
    _ctx.textAlign = 'left';

    [0, 0.25, 0.5, 0.75, 1.0].forEach(function (t) {
      var labelY = y + h - t * h;
      var db = vmin + t * (vmax - vmin);
      _ctx.fillText(db.toFixed(0) + 'dB', x + w + 3, labelY + 3);
    });

    _ctx.fillText('dB', x, y - 3);
  }

  function _viridis(norm) {
    var r, g, b, t;

    if (norm < 0.25) {
      t = norm / 0.25;
      r = 68 + t * (59 - 68);
      g = 1 + t * (82 - 1);
      b = 84 + t * (139 - 84);
    } else if (norm < 0.5) {
      t = (norm - 0.25) / 0.25;
      r = 59 + t * (33 - 59);
      g = 82 + t * (145 - 82);
      b = 139 + t * (140 - 139);
    } else if (norm < 0.75) {
      t = (norm - 0.5) / 0.25;
      r = 33 + t * (94 - 33);
      g = 145 + t * (201 - 145);
      b = 140 + t * (98 - 140);
    } else {
      t = (norm - 0.75) / 0.25;
      r = 94 + t * (253 - 94);
      g = 201 + t * (231 - 201);
      b = 98 + t * (37 - 98);
    }

    return [
      Math.max(0, Math.min(255, Math.round(r))),
      Math.max(0, Math.min(255, Math.round(g))),
      Math.max(0, Math.min(255, Math.round(b)))
    ];
  }

  return {
    init: init,
    update: update,
    reset: reset
  };
})();