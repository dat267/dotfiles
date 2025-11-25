#!/usr/bin/env python3
import sys
import time
import platform
import subprocess


def keep_awake(display=True):
    system = platform.system()
    print(f"[*] Starting keep-awake (System: {system}, Display Keep-Alive: {display})")
    print("[*] Press Ctrl+C to stop and allow system to sleep normally.\n")

    if system == "Windows":
        import ctypes

        # ES_CONTINUOUS = 0x80000000
        # ES_SYSTEM_REQUIRED = 0x00000001
        # ES_DISPLAY_REQUIRED = 0x00000002
        flags = 0x80000001
        if display:
            flags |= 0x00000002

        # Set status
        result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
        if result == 0:
            print("[!] Warning: SetThreadExecutionState failed.")
            return None

        def restore():
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            print("[*] Power state restored.")

        return restore

    elif system == "Darwin":  # macOS
        # Use caffeinate. -d prevents display sleep, -i prevents system idle sleep.
        args = ["caffeinate", "-i"]
        if display:
            args.append("-d")

        try:
            proc = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            def restore():
                proc.terminate()
                proc.wait()
                print("[*] Power state restored.")

            return restore
        except FileNotFoundError:
            print("[!] Warning: caffeinate not found.")
            return None

    else:  # Linux and others
        # Try systemd-inhibit
        # --what=idle:sleep prevents both idle and sleep
        args = [
            "systemd-inhibit",
            "--what=idle:sleep",
            "--who=keepawake",
            "--why=User run keepawake",
            "sleep",
            "31536000",
        ]  # 1 year
        try:
            proc = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            def restore():
                proc.terminate()
                proc.wait()
                print("[*] Power state restored.")

            return restore
        except FileNotFoundError:
            pass

        print(
            "[!] Note: systemd-inhibit not found. Running in basic timer mode (system may sleep depending on OS settings)."
        )
        return lambda: None


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Keep the computer awake across Windows, macOS, and Linux without third-party dependencies."
    )
    parser.add_argument(
        "-s",
        "--system-only",
        action="store_true",
        help="Prevent system sleep but allow the display to turn off (Windows/macOS only).",
    )
    args = parser.parse_args()

    display = not args.system_only
    restore_fn = keep_awake(display=display)

    start_time = time.time()
    spinner = ["|", "/", "-", "\\"]
    idx = 0

    try:
        while True:
            elapsed = time.time() - start_time
            hours, rem = divmod(elapsed, 3600)
            minutes, seconds = divmod(rem, 60)

            # Print status line
            sys.stdout.write(
                f"\r\033[K[ {spinner[idx % len(spinner)]} ] Active | Elapsed time: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
            )
            sys.stdout.flush()
            idx += 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[*] Stopping keep-awake...")
    finally:
        if restore_fn:
            restore_fn()
        print("[*] Exited.")


if __name__ == "__main__":
    main()
