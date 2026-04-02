// ============================================================
//  radar.js — Passive Radar module
//  Range-Doppler map + Doppler slice + target table
//  Exposes: Radar.init(), Radar.update(data)
// ============================================================

var Radar = (function () {

  function init() {
    // Nothing to set up at load time — canvases are ready in the DOM
  }

  function update(data) {
    if (data.rd_matrix && Array.isArray(data.rd_matrix)) {
      _drawRDMap(data.rd_matrix);
      _drawDopplerSlice(data.rd_matrix);
      document.getElementById('rd-placeholder').style.display      = 'none';
      document.getElementById('doppler-placeholder').style.display = 'none';
      if (data.cpi_index !== undefined) {
        document.getElementById('radar-cpi-label').textContent = 'CPI #' + data.cpi_index;
      }
    }
    if (data.targets && Array.isArray(data.targets)) {
      _renderTargetTable(data.targets);
    }
  }

  function _drawRDMap(matrix) {
    var canvas = document.getElementById('rd-canvas');
    canvas.width  = canvas.offsetWidth  || 400;
    canvas.height = canvas.offsetHeight || 300;
    var ctx = canvas.getContext('2d');
    var rows = matrix.length, cols = matrix[0].length;
    var imgData = ctx.createImageData(canvas.width, canvas.height);

    var flat = [].concat.apply([], matrix);
    var minV = Math.min.apply(null, flat);
    var maxV = Math.max.apply(null, flat);
    var rng  = maxV - minV || 1;

    for (var py = 0; py < canvas.height; py++) {
      for (var px = 0; px < canvas.width; px++) {
        var ri  = Math.floor((py / canvas.height) * rows);
        var ci  = Math.floor((px / canvas.width)  * cols);
        var v   = (matrix[ri][ci] - minV) / rng;
        // Inferno-ish: black → purple → red → yellow
        var r = Math.floor(255 * Math.min(1, v * 2));
        var g = Math.floor(255 * Math.max(0, v * 2 - 0.5));
        var b = Math.floor(255 * Math.max(0, 1 - v * 2));
        var idx = (py * canvas.width + px) * 4;
        imgData.data[idx]     = r;
        imgData.data[idx + 1] = g;
        imgData.data[idx + 2] = b;
        imgData.data[idx + 3] = 255;
      }
    }
    ctx.putImageData(imgData, 0, 0);

    // Axis labels
    ctx.fillStyle = 'rgba(13,21,32,0.75)';
    ctx.fillRect(0, canvas.height - 18, canvas.width, 18);
    ctx.fillStyle = '#4a6a88';
    ctx.font = '9px Share Tech Mono, monospace';
    ctx.textAlign = 'left';
    ctx.fillText('Doppler →', 4, canvas.height - 5);
    ctx.textAlign = 'right';
    ctx.fillText('← Range', canvas.width - 4, canvas.height - 5);
  }

  function _drawDopplerSlice(matrix) {
    // Find range bin with highest peak power
    var peakRow = 0, peakVal = -Infinity;
    matrix.forEach(function (row, i) {
      var rowMax = Math.max.apply(null, row);
      if (rowMax > peakVal) { peakVal = rowMax; peakRow = i; }
    });
    var slice = matrix[peakRow];

    var canvas = document.getElementById('doppler-canvas');
    canvas.width  = canvas.offsetWidth  || 400;
    canvas.height = canvas.offsetHeight || 300;
    var ctx = canvas.getContext('2d');
    var w = canvas.width, h = canvas.height;
    var minV = Math.min.apply(null, slice);
    var maxV = Math.max.apply(null, slice);
    var rng  = maxV - minV || 1;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#0d1520';
    ctx.fillRect(0, 0, w, h);

    // Grid
    ctx.strokeStyle = '#1a2d44'; ctx.lineWidth = 1;
    for (var i = 0; i <= 4; i++) {
      var gy = (i / 4) * h;
      ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(w, gy); ctx.stroke();
    }

    // Trace
    ctx.strokeStyle = '#39ff14'; ctx.lineWidth = 1.5;
    ctx.beginPath();
    slice.forEach(function (v, i) {
      var x    = (i / (slice.length - 1)) * w;
      var norm = (v - minV) / rng;
      var y    = h - norm * h * 0.9 - h * 0.05;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.fillStyle = '#4a6a88';
    ctx.font = '9px Share Tech Mono, monospace';
    ctx.textAlign = 'left';
    ctx.fillText('Peak range bin: ' + peakRow, 6, 14);
  }

  function _renderTargetTable(targets) {
    var el = document.getElementById('radar-target-body');
    if (!targets.length) {
      el.innerHTML = '<div class="radar-placeholder">No targets detected</div>';
      return;
    }
    var html = '<table id="radar-target-table"><thead><tr>' +
      '<th>#</th><th>Range (km)</th><th>Doppler (m/s)</th><th>Power (dB)</th><th>Confidence</th>' +
      '</tr></thead><tbody>';
    targets.forEach(function (t, i) {
      html += '<tr>' +
        '<td>' + (i + 1) + '</td>' +
        '<td>' + (t.range_km    !== undefined ? t.range_km.toFixed(1)        : '--') + '</td>' +
        '<td>' + (t.doppler_mps !== undefined ? t.doppler_mps.toFixed(1)     : '--') + '</td>' +
        '<td>' + (t.power_db    !== undefined ? t.power_db.toFixed(1)        : '--') + '</td>' +
        '<td>' + (t.confidence  !== undefined ? (t.confidence*100).toFixed(0)+'%' : '--') + '</td>' +
        '</tr>';
    });
    html += '</tbody></table>';
    el.innerHTML = html;
  }

  return { init: init, update: update };

})();