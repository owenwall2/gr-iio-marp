"""
Embedded Python Blocks:

Each time this file is saved, GRC will instantiate the first class it finds
to get ports and parameters of your block. All of them are required to have default values!
"""

import numpy as np
from gnuradio import gr


class blk(gr.sync_block):
    """
    NPZ radar source

    Loads a .npz file once, then streams the selected array out as float32.
    Default expects:
        maps_pos -> shape (num_frames, num_rows, num_cols)
    """

    def __init__(self,
                 filename="/home/owen/marp/passive_radar/passive_radar_maps.npz",
                 array_name="maps_pos",
                 repeat=True,
                 scale=1.0):
        gr.sync_block.__init__(
            self,
            name='NPZ Radar Source',
            in_sig=[],              # zero inputs = source
            out_sig=[np.float32]    # stream of float32 values
        )

        self.repeat = repeat
        self.scale = float(scale)
        self._idx = 0

        with np.load(filename, allow_pickle=False) as z:
            if array_name not in z:
                raise KeyError(f"Array '{array_name}' not found in {filename}. "
                               f"Available keys: {list(z.keys())}")
            arr = np.asarray(z[array_name], dtype=np.float32)

        # Stream the whole archive as one flat float32 sequence
        self._flat = (arr * self.scale).ravel()
        self._n = len(self._flat)

        if self._n == 0:
            raise ValueError(f"No data loaded from {filename}:{array_name}")

    def work(self, input_items, output_items):
        out = output_items[0]
        nout = len(out)

        if self._idx >= self._n:
            if not self.repeat:
                return 0
            self._idx = 0

        nwrite = min(nout, self._n - self._idx)
        out[:nwrite] = self._flat[self._idx:self._idx + nwrite]
        self._idx += nwrite

        return nwrite
