import csv
import os
import re
import shutil
import time
from typing import Any

# ANSI colors for beautiful terminal output
COLORS = {
    "Cyan": "\033[96m",
    "Green": "\033[92m",
    "Yellow": "\033[93m",
    "Red": "\033[91m",
    "DarkGray": "\033[90m",
    "Reset": "\033[0m",
}

# --- DIRECTORY & VAULT HELPERS ---


def delete_folder_contents(folder_path: str) -> None:
    """
    Deletes all files and subdirectories inside the given folder,
    but does not delete the folder itself.
    """
    if not os.path.exists(folder_path):
        print(f"Folder does not exist: {folder_path}")
        return

    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if os.path.isfile(item_path) or os.path.islink(item_path):
            os.remove(item_path)
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)

    print(f'All contents in "{folder_path}" deleted.')


def load_env() -> None:
    """Loads environment variables from .env in the same directory as the scripts."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # Strip quotes if present
                    if (val.startswith('"') and val.endswith('"')) or (
                        val.startswith("'") and val.endswith("'")
                    ):
                        val = val[1:-1]
                    os.environ[key] = val
    except Exception:
        pass


# Load environment variables on module import
load_env()

# --- TERMINAL UI & SAFETY HELPERS ---


def write_header(text: str, color: str = "Cyan") -> None:
    """Prints a styled section header in the terminal."""
    clr = COLORS.get(color, COLORS["Cyan"])
    reset = COLORS["Reset"]
    print(f"\n{clr}=== {text} ==={reset}")


def write_success(text: str) -> None:
    """Prints a green success message in the terminal."""
    green = COLORS["Green"]
    reset = COLORS["Reset"]
    print(f"{green}SUCCESS: {text}{reset}")


def confirm_execution(action_description: str = "Execute this change?") -> bool:
    """Safety confirmation dialog. Prompts user to proceed before altering state."""
    yellow = COLORS["Yellow"]
    reset = COLORS["Reset"]
    print(f"\n{yellow}[SAFETY CHECK] {action_description}{reset}")
    choice = input("Proceed? (y/n): ").strip().lower()
    if choice != "y":
        print(f"{COLORS['Red']}Operation cancelled by user.{reset}")
        return False
    return True


def export_backup(data: list[Any], table_name: str) -> str | None:
    """Exports raw dataset to a temporary CSV backup file."""
    if not data:
        print(
            f"{COLORS['Yellow']}No data provided for backup of {table_name}.{COLORS['Reset']}"
        )
        return None

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    clean_table_name = re.sub(r"[^a-zA-Z0-9_]", "_", table_name)
    temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))
    backup_path = os.path.join(temp_dir, f"{clean_table_name}_backup_{timestamp}.csv")

    first_item = data[0]
    if hasattr(first_item, "__dict__"):
        fieldnames = list(first_item.__dict__.keys())
    elif isinstance(first_item, dict):
        fieldnames = list(first_item.keys())
    else:
        fieldnames = ["Value"]

    try:
        with open(backup_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in data:
                if hasattr(item, "__dict__"):
                    writer.writerow(item.__dict__)
                elif isinstance(item, dict):
                    writer.writerow(item)
                else:
                    writer.writerow({"Value": item})

        print(f"{COLORS['Cyan']}BACKUP SAVED: {backup_path}{COLORS['Reset']}")
        return backup_path
    except Exception as e:
        print(f"{COLORS['Red']}Failed to save backup: {e}{COLORS['Reset']}")
        return None


def get_selection(data: list[Any], columns: list[str] | None = None) -> list[Any]:
    """
    Renders an interactive CLI table of the dataset and prompts the user
    to pick specific rows (via comma-separated indexes) or type 'all'.
    """
    if not data:
        return []

    first_item = data[0]
    if hasattr(first_item, "__dict__"):
        keys = list(first_item.__dict__.keys())
    elif isinstance(first_item, dict):
        keys = list(first_item.keys())
    else:
        keys = []

    view_cols = (
        columns
        if columns
        else [
            k
            for k in keys
            if not any(x in k.lower() for x in ("json", "payload", "query"))
        ][:5]
    )

    cyan = COLORS["Cyan"]
    reset = COLORS["Reset"]

    # Print table header
    header_str = f"\n{cyan}Index | " + " | ".join(view_cols) + reset
    print(header_str)
    print(cyan + "-" * len(header_str) + reset)

    mapping = {}
    for idx, item in enumerate(data, 1):
        mapping[idx] = item
        row_parts = []
        for col in view_cols:
            val = (
                getattr(item, col, None)
                if hasattr(item, "__dict__")
                else item.get(col, "")
            )
            row_parts.append(str(val))
        print(f"  {idx:<3} | " + " | ".join(row_parts))

    print(cyan + "-" * len(header_str) + reset)

    pick = input("Select numbers (comma-separated, e.g. 1,3,5) or 'all': ").strip()
    if not pick:
        return []

    if pick.lower() == "all":
        return data

    choices = [c.strip() for c in pick.split(",") if c.strip()]
    selected = []
    for c in choices:
        if c.isdigit() and int(c) in mapping:
            selected.append(mapping[int(c)])
    return selected
