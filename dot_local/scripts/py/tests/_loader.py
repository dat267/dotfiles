"""Load py/ scripts as modules despite the executable_ prefix and hyphens."""
import importlib.machinery
import importlib.util
import pathlib
import sys

PY_DIR = pathlib.Path(__file__).resolve().parent.parent

if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


def load(stem: str):
    """Import a script by name without the executable_ prefix (e.g. 'yazi-rename')."""
    if stem == "_shared":
        path = PY_DIR / "_shared.py"
    else:
        for name in (f"executable_{stem}.py", f"executable_{stem.replace('-', '_')}.py"):
            path = PY_DIR / name
            if path.exists():
                break
        else:
            path = PY_DIR / f"executable_{stem}"  # extensionless scripts (mpv)
    loader = importlib.machinery.SourceFileLoader(stem, str(path))
    spec = importlib.util.spec_from_loader(stem, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod
