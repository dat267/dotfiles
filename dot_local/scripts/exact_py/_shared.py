import json
import os
import platform
import shutil
import sys
import tempfile
import tarfile
import urllib.request
import zipfile

DEFAULT_TIMEOUT = 60


def widen_output_encoding():
    """Stop non-ASCII log glyphs from crashing on a Windows console.

    Windows pipes default to the ANSI code page (cp1252), where the check
    marks and arrows in log() lines raise UnicodeEncodeError. Keep each
    stream's encoding and substitute what it cannot represent.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):
            pass


widen_output_encoding()


def fetch_json(url, timeout=5, opener=None):
    """GET url, return parsed JSON or None on failure.

    `opener` mirrors urllib.request.urlopen's own signature — (url, data=None,
    timeout=...) — so a double and the production opener are called the same
    way. Passing the timeout positionally would bind it to `data` instead,
    raising TypeError for the real urlopen; swallowing that into None is how a
    network failure came to be reported as a missing release asset.
    """
    open_url = opener or urllib.request.urlopen
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with open_url(req, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None


def github_latest_tag(repo, timeout=5, opener=None):
    """Resolve the latest GitHub release tag for `repo`. Strips leading 'v'."""
    data = fetch_json(f"https://api.github.com/repos/{repo}/releases/latest", timeout, opener)
    if data and "tag_name" in data:
        return data["tag_name"].lstrip("v")
    return None


def download(url, dest, headers=None, timeout=DEFAULT_TIMEOUT, opener=None, on_progress=None):
    """Stream `url` to `dest`, return the dest path.

    `opener(req, timeout=...)` is injectable for tests and mirrors
    urllib.request.urlopen; the timeout is a keyword for the same reason as in
    fetch_json. `on_progress(done_bytes, total_bytes)` is called per chunk when
    given; total_bytes is 0 when the server sends no content-length.
    """
    open_url = opener or urllib.request.urlopen
    req = urllib.request.Request(url, headers=headers or {})
    done = 0
    with open_url(req, timeout=timeout) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("content-length", 0)) if hasattr(resp, "headers") else 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if on_progress:
                on_progress(done, total)
    return dest


def is_termux():
    """True when running inside Termux (root path or TERMUX_VERSION marker)."""
    return os.path.exists("/data/data/com.termux") or "TERMUX_VERSION" in os.environ


def extract_archive(src, dest_dir):
    """Extract a .zip, .tar.gz or .tar.xz archive into dest_dir.

    The kind is sniffed rather than read off the filename: the same installer
    downloads a zip on Windows and a tar.gz on Linux, and it stages the
    payload under one fixed name (nvim.archive), which tarfile used to be
    handed as gzip — "not a gzip file". tarfile's "r:*" opens any of the
    compressed tar flavours, so only the zip case needs a branch.
    """
    os.makedirs(dest_dir, exist_ok=True)
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src, "r") as z:
            z.extractall(dest_dir)
        return
    with tarfile.open(src, "r:*") as t:
        t.extractall(path=dest_dir)


def install_release_binary(url, binary_names, dest_dir, *, extract=None, headers=None, opener=None, timeout=DEFAULT_TIMEOUT):
    """Install binary/binary list from a release URL: download → extract → chmod → atomic replace.

    binary_names is one name (returns the dest path) or a sequence of names
    (downloads and extracts ONCE, returns a list of dest paths). extract:
    None when url IS the binary; "zip" or "tar.gz" when it is an archive
    containing the binaries (found anywhere in the tree). headers, opener and
    timeout pass through to download(). Raises RuntimeError when a binary is
    missing from the archive; network errors propagate from download().
    """
    names = [binary_names] if isinstance(binary_names, str) else list(binary_names)
    dest_paths = [os.path.join(dest_dir, name) for name in names]
    os.makedirs(dest_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        src_root = os.path.join(temp_dir, "payload")
        if extract is None:
            staged = os.path.join(temp_dir, names[0])
            download(url, staged, headers=headers, timeout=timeout, opener=opener)
            src = {names[0]: staged}
        else:
            archive = os.path.join(temp_dir, f"payload.{ 'zip' if extract == 'zip' else 'tar.gz' }")
            download(url, archive, headers=headers, timeout=timeout, opener=opener)
            extract_archive(archive, src_root)
            src = {}
            remaining = set(names)
            for dirpath, _, filenames in os.walk(src_root):
                for name in list(remaining):
                    if name in filenames:
                        src[name] = os.path.join(dirpath, name)
                        remaining.discard(name)
            if remaining:
                raise RuntimeError(f"binary '{sorted(remaining)[0]}' not found in archive from {url}")

        if os.name != "nt":
            for path in src.values():
                os.chmod(path, 0o755)

        for name, dest_path in zip(names, dest_paths):
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception as e:
                log(f"Warning: Could not remove existing file {dest_path}: {e}", "yellow")

            shutil.move(src[name], dest_path)

    return dest_paths[0] if isinstance(binary_names, str) else dest_paths

COLORS = {
    "cyan": "\033[96m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "reset": "\033[0m",
}


def log(message, color=None):
    use_color = sys.stdout.isatty() and (os.name == "posix" or os.environ.get("TERM"))
    if color and use_color:
        print(f"{COLORS.get(color, '')}{message}{COLORS['reset']}")
    else:
        print(message)


def windows_home(*parts):
    """A path under the Windows user profile: windows_home("Apps", "pi").

    Not expanduser("~"): a POSIX-emulated Python on Windows (MSYS2, Cygwin)
    resolves that to the emulated home (C:\\msys64\\home\\me), while the PATH
    entries and the dotfiles on the machine are the Windows ones. On native
    Windows USERPROFILE is the home expanduser returns anyway.
    """
    return os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), *parts)


class Platform:
    """Detected platform plus the vocabulary install scripts keep re-deriving:
    executable/launcher extensions, venv bin dir, archive extensions, Termux
    prefix. Construct directly for tests; use detect() at runtime."""

    def __init__(self, os_name, arch, posix_python=None):
        self.os = os_name      # linux | windows | darwin | android
        self.arch = arch       # arm64 | x64
        # True for a POSIX-emulated Python on Windows (MSYS2, Cygwin): Windows
        # release assets and %USERPROFILE% install dirs, but venvs whose
        # launchers live in bin/ like any other.
        self.posix_python = posix_python if posix_python is not None else os_name != "windows"

    @classmethod
    def detect(cls):
        """Runtime detection: Termux marker remaps Linux to Android,
        MSYS2/Cygwin remap to Windows, machine is normalized to arm64/x64."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        arch = "arm64" if ("arm" in machine or "aarch64" in machine) else "x64"
        # Those Pythons report "MSYS_NT-10.0-19045" and "CYGWIN_NT-10.0-19045".
        # The machine is Windows, so a release has to be the Windows build: the
        # Linux tarballs would not even execute there.
        if system.startswith(("msys", "cygwin")):
            system = "windows"
            posix_python = True
        else:
            posix_python = None
        os_name = "android" if system == "linux" and is_termux() else system
        return cls(os_name, arch, posix_python)

    @property
    def is_windows(self):
        return self.os == "windows"

    @property
    def is_android(self):
        return self.os == "android"

    @property
    def exe_ext(self):
        return ".exe" if self.is_windows else ""

    @property
    def script_ext(self):
        return ".cmd" if self.is_windows else ""

    @property
    def venv_bin(self):
        # Keyed off the interpreter flavor, not the remapped os: a
        # POSIX-emulated Python on Windows installs venv launchers into bin/
        # like any other, even though it takes the Windows release assets.
        return "bin" if self.posix_python else "Scripts"

    @property
    def termux_prefix(self):
        return os.environ.get("PREFIX", "/data/data/com.termux/files/usr")

    def archive_ext(self, kind):
        """Extension for archive kind ("zip", "tar.gz", "gz") — Windows ships .zip."""
        if self.is_windows:
            return ".zip"
        return {"zip": ".tar.gz", "tar.gz": ".tar.gz", "gz": ".gz"}[kind]

    def vendor(self, os=None, arch=None):
        """(os_word, arch_word) in a vendor's download-URL vocabulary.

        os/arch map canonical values through a per-vendor dict (vendors
        disagree: amd64 vs x64 vs x86_64, darwin vs osx). A dict must be
        complete over the values it will see. Termux presents as android but
        runs Linux binaries, so an unmapped android speaks the vendor's
        "linux" word. Anything genuinely unsupported logs and exits — the
        same contract the per-script get_platform_info copies had.
        """
        if os is None:
            os_word = self.os
        elif self.os in os:
            os_word = os[self.os]
        elif self.os == "android" and "linux" in os:
            os_word = os["linux"]
        else:
            log(f"Error: OS '{self.os}' is not in the vendor vocabulary {sorted(os)}.", "red")
            sys.exit(1)
        if arch is None:
            arch_word = self.arch
        elif self.arch in arch:
            arch_word = arch[self.arch]
        else:
            log(f"Error: Architecture '{self.arch}' is not in the vendor vocabulary {sorted(arch)}.", "red")
            sys.exit(1)
        return os_word, arch_word
