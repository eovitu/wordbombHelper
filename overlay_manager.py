# Legacy shim — Tk overlay removed. Kept empty so stray imports fail silently if any remain.


def run_overlay(region_callback=None):
    _ = region_callback


def get_overlay():
    return None
