import threading
import json
import os

from shared.parsing import normalize_capture_region


class RegionStore:
    """In-memory store for the calibrated region with optional disk persistence.

    Saves the last region to a JSON file in the repository root so the
    ScreenReader can reload it between runs.
    """

    def __init__(self, store_file=None):
        self._ll_grid_region = None
        self._lock = threading.RLock()
        # default file next to project CWD
        self._store_file = store_file or os.path.join(os.getcwd(), "calibration_region.json")
        # try to load any existing region
        try:
            self._load_from_disk()
        except Exception:
            # ignore failures, keep in-memory None
            pass

    def get_region(self):
        with self._lock:
            normalized = normalize_capture_region(self._ll_grid_region)
            return normalized if normalized else self._ll_grid_region

    def set_region(self, region):
        normalized = normalize_capture_region(region)
        to_store = normalized if normalized else (region if isinstance(region, dict) else None)
        with self._lock:
            self._ll_grid_region = to_store
            try:
                with open(self._store_file, "w", encoding="utf-8") as fh:
                    json.dump(self._ll_grid_region, fh)
            except Exception:
                # best-effort persistence; don't raise to caller
                pass

    def _load_from_disk(self):
        if not os.path.exists(self._store_file):
            return
        try:
            with open(self._store_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            normalized = normalize_capture_region(data)
            self._ll_grid_region = normalized if normalized else None
        except Exception:
            # ignore parse/load errors
            self._ll_grid_region = None

    def clear_persistence(self):
        with self._lock:
            self._ll_grid_region = None
            try:
                if os.path.exists(self._store_file):
                    os.remove(self._store_file)
            except Exception:
                pass
