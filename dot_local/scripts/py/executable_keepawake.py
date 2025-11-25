#!/usr/bin/env python3
import sys
import time
import platform
import subprocess
import random


def press_safe_key():
    key_choice = random.choice(["F15", "ScrollLock"])
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes
            vk = 0x7E if key_choice == "F15" else 0x91
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
            return key_choice
        elif system == "Darwin":
            key_code = 113 if key_choice == "F15" else 107
            cmd = f'tell application "System Events" to key code {key_code}'
            res = subprocess.run(["osascript", "-e", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                return key_choice
        else:  # Linux
            key_name = "F15" if key_choice == "F15" else "Scroll_Lock"
            try:
                res = subprocess.run(["xdotool", "key", key_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0:
                    return key_choice
            except FileNotFoundError:
                try:
                    res = subprocess.run(["wtype", "-k", key_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if res.returncode == 0:
                        return key_choice
                except FileNotFoundError:
                    pass
    except Exception:
        pass
    return None


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

    last_press_time = time.time()
    next_press_delay = random.randint(30, 60)
    last_key_sent = None
    last_key_sent_time = 0

    try:
        while True:
            current_time = time.time()
            if current_time - last_press_time >= next_press_delay:
                last_key_sent = press_safe_key()
                if last_key_sent:
                    last_key_sent_time = current_time
                last_press_time = current_time
                next_press_delay = random.randint(30, 60)

            elapsed = current_time - start_time
            hours, rem = divmod(elapsed, 3600)
            minutes, seconds = divmod(rem, 60)

            # Add temporary status for key press activity
            key_status = ""
            if last_key_sent and (current_time - last_key_sent_time < 5):
                key_status = f" (sent {last_key_sent})"

            # Print status line
            sys.stdout.write(
                f"\r\033[K[ {spinner[idx % len(spinner)]} ] Active{key_status} | Elapsed time: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
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
