"""Minimal machine stub: SPI and pins accept writes and do nothing."""


class Pin:
    OUT = 1
    # Last Pin object per GPIO number, for checks on board setup.
    pins = {}

    def __init__(self, number, *args, **kwargs):
        self.state = 0
        Pin.pins[number] = self

    def value(self, state=None):
        if state is None:
            return self.state
        self.state = state


class SPI:
    def __init__(self, *args, **kwargs):
        pass

    def write(self, data):
        pass
