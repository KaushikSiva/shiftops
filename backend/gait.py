"""NumPy execution of the unchanged official 64-unit LSTM gait weights."""

import numpy as np


class NumpyGait:
    def __init__(self, path):
        self.w = dict(np.load(path, allow_pickle=False))
        self.reset_memory()

    def reset_memory(self):
        self.h = np.zeros(64, dtype=np.float32)
        self.c = np.zeros(64, dtype=np.float32)

    def __call__(self, x):
        w = self.w
        # Small matrix/vector contractions avoid platform BLAS floating-status
        # warnings and keep the exact frozen weights and LSTM equations.
        mv = lambda a, b: np.einsum("ij,j->i", a, b)
        gates = (
            mv(w["memory.weight_ih_l0"], x)
            + w["memory.bias_ih_l0"]
            + mv(w["memory.weight_hh_l0"], self.h)
            + w["memory.bias_hh_l0"]
        )
        i, f, g, o = np.split(gates, 4)
        sigmoid = lambda z: 1 / (1 + np.exp(-np.clip(z, -80, 80)))
        self.c = sigmoid(f) * self.c + sigmoid(i) * np.tanh(g)
        self.h = sigmoid(o) * np.tanh(self.c)
        a = mv(w["actor.0.weight"], self.h) + w["actor.0.bias"]
        a = np.where(a > 0, a, np.expm1(np.minimum(a, 0)))
        return mv(w["actor.2.weight"], a) + w["actor.2.bias"]
