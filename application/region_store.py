import threading


class RegionStore:
    def __init__(self):
        self._ll_grid_region = None
        self._lock = threading.RLock()

    def get_region(self):
        with self._lock:
            return self._ll_grid_region

    def set_region(self, region):
        with self._lock:
            self._ll_grid_region = region
