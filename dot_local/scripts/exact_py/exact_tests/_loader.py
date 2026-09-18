"""Load py/ scripts as modules despite the executable_ prefix and hyphens."""
import importlib.machinery
import importlib.util
import os
import pathlib
import sys
import tempfile


def _ensure_real_tempdir() -> None:
    """Pin TMPDIR to a real directory when tempfile would fall back to CWD.

    On Termux, /tmp and /var/tmp don't exist and TMPDIR is usually unset, so
    tempfile.gettempdir() returns the current working directory and every
    raw tempfile.mkdtemp() in the tests litters the repo. Redirect to
    ~/.cache/tmp before anything resolves the temp dir (the cache is invalidated
    after changing the env). On platforms with a working /tmp or TEMP this is a
    no-op.
    """
    if os.path.realpath(tempfile.gettempdir()) == os.path.realpath(os.getcwd()):
        fallback = os.path.join(os.path.expanduser("~"), ".cache", "tmp")
        os.makedirs(fallback, exist_ok=True)
        os.environ["TMPDIR"] = fallback
        tempfile.tempdir = None  # drop the cached cwd resolution


_ensure_real_tempdir()


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
