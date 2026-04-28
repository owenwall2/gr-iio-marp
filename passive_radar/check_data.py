import os
import numpy as np

size_bytes = os.path.getsize("data/ref")
samples = size_bytes // np.dtype(np.complex64).itemsize
seconds = samples /12e6
print(samples, seconds)