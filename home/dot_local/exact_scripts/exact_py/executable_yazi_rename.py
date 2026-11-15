#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import subprocess
import tempfile


def fmt_path(p):
    if len(p) >= 2 and p[0] == p[-1] and p[0] in "'\"":
        p = p[1:-1]
    return p


def input_flush(prompt):
    print(prompt, end="", flush=True)
    return sys.stdin.readline().rstrip("\n")


def main():
    parser = argparse.ArgumentParser(description="Batch rename files via $EDITOR.")
    parser.add_argument('paths', nargs='+', help='Files to rename')
    args = parser.parse_args()

    paths = [fmt_path(p) for p in args.paths]

    dirs = set(os.path.dirname(p) for p in paths)
    if len(dirs) > 1:
        print("Error: files must be in the same directory", file=sys.stderr)
        input_flush("Press Enter to return to Yazi.")
        sys.exit(1)

    parent = os.path.dirname(paths[0])
    old = [os.path.basename(p) for p in paths]

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, dir=parent)
    tmpname = tmp.name
    for name in old:
        tmp.write(name + "\n")
    tmp.close()

    editor = os.environ.get("EDITOR")
    if not editor or not shutil.which(editor):
        for e in ["nvim", "vim", "helix", "hx"]:
            if shutil.which(e):
                editor = e
                break
        else:
            editor = "vi"
    subprocess.run([editor, tmpname])

    with open(tmpname) as f:
        new = [line.rstrip("\n") for line in f]
    os.remove(tmpname)

    changes = []
    targets = set()
    for a, b in zip(old, new):
        if a == b:
            continue
        if b in targets:
            print(f"Skip: two entries both rename to {b}", file=sys.stderr)
            continue
        targets.add(b)
        changes.append((a, b))

    if not changes:
        print("No changes", file=sys.stderr)
        return

    # Two passes through a unique staging name. Applying the final names directly
    # made a target that is also another entry's current name look like a
    # collision: a swap renamed nothing and a chain was half applied.
    moved = []
    for index, (a, b) in enumerate(changes):
        src = os.path.join(parent, a)
        staged = os.path.join(parent, f".yazi_rename_{os.getpid()}_{index}")
        try:
            os.rename(src, staged)
        except OSError as exc:
            print(f"Skip: cannot rename {a}: {exc}", file=sys.stderr)
            continue
        moved.append((staged, a, b))

    for staged, a, b in moved:
        dst = os.path.join(parent, b)
        if os.path.exists(dst):
            print(f"Skip: {b} already exists", file=sys.stderr)
            os.rename(staged, os.path.join(parent, a))
            continue
        os.rename(staged, dst)
        print(f"Renamed -> {b}", file=sys.stderr)

    input("Press Enter to return to Yazi.")

if __name__ == "__main__":
    main()
