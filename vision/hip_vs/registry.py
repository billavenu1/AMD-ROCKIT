# vision/hip_vs/registry.py

_stores = {}

def register(name: str, store):
    _stores[name] = store

def get(name: str):
    return _stores.get(name)

def evict_all():
    for store in _stores.values():
        if store.in_vram:
            store.evict()

def restore_all():
    for store in _stores.values():
        if not store.in_vram:
            store.restore()
