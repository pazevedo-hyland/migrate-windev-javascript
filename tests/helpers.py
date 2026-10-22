import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load(relative):
    """Load a dependency-free script as a module without installing it."""
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
