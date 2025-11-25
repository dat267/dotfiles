import base64
import csv
import io
import os
import re
import shutil
import subprocess
import time
import urllib.parse
from typing import Any

import requests

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

# --- CONFIGURATION HELPERS ---


def get_jira_config(
    my_email: str | None = None, jira_domain: str | None = None
) -> dict[str, Any]:
    """Generates standard configurations and headers for Atlassian Jira API."""
    if not my_email:
        my_email = os.environ.get("JIRA_EMAIL", "user@yourcompany.com")
    if not jira_domain:
        jira_domain = os.environ.get("JIRA_DOMAIN", "yourcompany.atlassian.net")

    token = os.environ.get("ATLASSIAN_API_TOKEN")
    if not token:
        raise ValueError(
            "ATLASSIAN_API_TOKEN environment variable not set in system or .env file."
        )

    auth_str = f"{my_email}:{token}"
    base64_auth_info = base64.b64encode(auth_str.encode("ascii")).decode("ascii")

    return {
        "Domain": jira_domain,
        "Email": my_email,
        "Headers": {
            "Authorization": f"Basic {base64_auth_info}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    }


def get_redash_config(redash_url: str | None = None) -> dict[str, Any]:
    """Generates standard configurations for Redash database querying."""
    if not redash_url:
        redash_url = os.environ.get("REDASH_URL", "https://redash.yourcompany.com")

    api_key = os.environ.get("REDASH_API_KEY")
    if not api_key:
        raise ValueError(
            "REDASH_API_KEY environment variable not set in system or .env file."
        )

    return {
        "RedashUrl": redash_url,
        "ApiKey": api_key,
        "PlaceholderQueryId": 3,
        "Timeout": 0,
    }


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


# --- REDASH ENGINE WITH RETRY & SAFETY ---


def run_redash_query(
    query: str,
    api_key: str,
    database_type: str = "HUB",
    redash_url: str | None = None,
    query_id: int = 3,
    timeout: int = 120,
) -> list[dict[str, str]]:
    """
    Executes a database query via Redash placeholder API.
    - Idempotent metadata updates (POST api/queries/id) are retried on transient 500 errors.
    - Non-idempotent query executions are run strictly ONCE to prevent duplicate executions.
    """
    if not redash_url:
        redash_url = os.environ.get("REDASH_URL", "https://redash.yourcompany.com")
    data_source_map = {
        "HUB": 4,
        "CBFT": 101,
        "EWA": 102,
        "HUB_DATABASE": 4,
        "CBFT_DATABASE": 101,
        "EWA_FUNDS_DATABASE": 102,
    }

    db_key = str(database_type).upper().strip()
    data_source_id = data_source_map.get(db_key)
    if not data_source_id:
        if db_key.isdigit():
            data_source_id = int(db_key)
        else:
            raise ValueError(
                f"Unknown Redash database connection type: {database_type}"
            )

    headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}

    # Step 1: Update the query with robust idempotent retries
    edit_payload = {"query": query, "data_source_id": data_source_id}
    max_retries = 3
    retry_count = 0
    updated = False
    last_error = None

    while retry_count < max_retries and not updated:
        try:
            resp = requests.post(
                f"{redash_url}/api/queries/{query_id}",
                headers=headers,
                json=edit_payload,
                timeout=30,
            )
            resp.raise_for_status()
            updated = True
        except Exception as e:
            retry_count += 1
            last_error = e
            if retry_count < max_retries:
                print(
                    f"{COLORS['Yellow']}WARNING: Failed to update Redash placeholder query {query_id} (Attempt {retry_count}/{max_retries}): {e}. Retrying in 1s...{COLORS['Reset']}"
                )
                time.sleep(1)

    if not updated:
        raise RuntimeError(
            f"Failed to update Redash placeholder query {query_id} after {max_retries} attempts: {last_error}"
        )

    # Step 2: Trigger execution EXACTLY ONCE for safety (No retries to prevent double database executions)
    payload = {"max_age": 0}
    try:
        resp = requests.post(
            f"{redash_url}/api/queries/{query_id}/results",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Failed to trigger Redash query execution: {e}")

    resp_json = resp.json()

    # Step 3: Poll for async job completion
    result_id = None
    if "job" in resp_json:
        job_id = resp_json["job"]["id"]
        poll_url = f"{redash_url}/api/jobs/{job_id}"
        elapsed = 0
        while True:
            job_resp = requests.get(poll_url, headers=headers, timeout=15)
            job_resp.raise_for_status()
            job_data = job_resp.json()["job"]
            status = job_data["status"]
            if status == 3:  # Success
                result_id = job_data["query_result_id"]
                break
            elif status in (4, 5):  # Failed/Cancelled
                raise RuntimeError(
                    f"Redash Query job failed/cancelled: {job_data.get('error')}"
                )
            time.sleep(2)
            elapsed += 2
            if timeout > 0 and elapsed > timeout:
                raise TimeoutError("Timeout waiting for Redash job to complete.")
    elif "query_result" in resp_json:
        result_id = resp_json["query_result"]["id"]
    else:
        raise RuntimeError(f"Unexpected response structure from Redash: {resp_json}")

    # Step 4: Download CSV and parse
    csv_url = f"{redash_url}/api/query_results/{result_id}.csv?api_key={api_key}"
    csv_resp = requests.get(csv_url, timeout=30)
    csv_resp.raise_for_status()
    csv_file = io.StringIO(csv_resp.text)
    reader = csv.DictReader(csv_file)
    result = list(reader)

    # Step 5: Clean up / blank placeholder query
    blank_payload = {"query": "-- cleared --", "data_source_id": data_source_id}
    try:
        requests.post(
            f"{redash_url}/api/queries/{query_id}",
            headers=headers,
            json=blank_payload,
            timeout=10,
        )
    except Exception:
        pass  # Failure to blank does not break the query results return

    return result


def run_redash(connection: str, query_string: str) -> list[dict[str, str]]:
    """Convenience wrapper for run_redash_query using standard connection aliases (HUB, CBFT, EWA)."""
    config = get_redash_config()
    return run_redash_query(
        query=query_string,
        api_key=config["ApiKey"],
        database_type=connection,
        redash_url=config["RedashUrl"],
        query_id=config["PlaceholderQueryId"],
        timeout=config["Timeout"],
    )


# --- JIRA UTILITIES ---


def get_jira_filter_jql(
    jira_domain: str, filter_id: str, headers: dict[str, str]
) -> str:
    """Retrieves the raw JQL query string associated with a specific Jira Filter ID."""
    url = f"https://{jira_domain}/rest/api/3/filter/{filter_id}"
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json().get("jql", "")


def get_jira_account_id(
    jira_domain: str, user_email: str, headers: dict[str, str]
) -> str | None:
    """Retrieves the unique Jira accountId string for a given user email address."""
    encoded_email = urllib.parse.quote(user_email)
    url = f"https://{jira_domain}/rest/api/3/user/search?query={encoded_email}"
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    users = resp.json()

    matched = [
        u
        for u in users
        if u.get("emailAddress") == user_email and u.get("accountType") == "atlassian"
    ]
    if matched:
        return matched[0].get("accountId")
    else:
        print(
            f"{COLORS['Yellow']}WARNING: No Jira account found for email: {user_email}{COLORS['Reset']}"
        )
        return None


def search_jira_tickets(
    jira_domain: str,
    jql_query: str,
    headers: dict[str, str],
    fields: list[str] | None = None,
    max_results: int = 50,
) -> list[dict]:
    """Searches Jira tickets using pagination and handles nextPageToken recursively."""
    if fields is None:
        fields = ["key", "status", "assignee", "summary"]

    all_issues = []
    next_page_token = None
    fields_param = ",".join(fields)
    encoded_jql = urllib.parse.quote(jql_query)

    while True:
        search_url = f"https://{jira_domain}/rest/api/3/search/jql?jql={encoded_jql}&fields={fields_param}&maxResults={max_results}"
        if next_page_token:
            search_url += f"&nextPageToken={urllib.parse.quote(next_page_token)}"

        resp = requests.get(search_url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        issues = data.get("issues", [])
        all_issues.extend(issues)

        next_page_token = data.get("nextPageToken")
        is_last = data.get("isLast", True)
        if is_last or not next_page_token:
            break

    return all_issues


def set_jira_assignee(
    jira_domain: str, issue_key: str, account_id: str, headers: dict[str, str]
) -> None:
    """Sets the assignee of a specific Jira ticket using accountId."""
    url = f"https://{jira_domain}/rest/api/3/issue/{issue_key}/assignee"
    body = {"accountId": account_id}
    resp = requests.put(url, headers=headers, json=body, timeout=15)
    resp.raise_for_status()


def test_jira_first_response_needed(
    jira_domain: str, issue_key: str, headers: dict[str, str]
) -> bool:
    """Checks the 'Time to first response' SLA cycle on a ticket."""
    url = f"https://{jira_domain}/rest/api/3/issue/{issue_key}"
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    fields = resp.json().get("fields", {})

    # Iterate dynamically to locate custom SLA fields
    for k, val in fields.items():
        if isinstance(val, dict) and val.get("name") == "Time to first response":
            return bool(val.get("ongoingCycle", False))

    print(
        f"{COLORS['Yellow']}WARNING: SLA field 'Time to first response' not found on issue {issue_key}.{COLORS['Reset']}"
    )
    return False


def add_jira_comment(
    jira_domain: str, issue_key: str, comment: str, headers: dict[str, str]
) -> None:
    """Adds a comment to a specific Jira ticket in the required Atlassian Document Format (ADF) v3."""
    url = f"https://{jira_domain}/rest/api/3/issue/{issue_key}/comment"
    comment_body = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": comment}]}
            ],
        }
    }
    resp = requests.post(url, headers=headers, json=comment_body, timeout=15)
    resp.raise_for_status()


def get_jira_comments(
    jira_domain: str, issue_key: str, headers: dict[str, str], max_results: int = 5
) -> list[dict]:
    """Retrieves comments for a specific Jira ticket sorted by newest first."""
    url = f"https://{jira_domain}/rest/api/3/issue/{issue_key}/comment?maxResults={max_results}&orderBy=-created"
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code != 200:
        print(
            f"{COLORS['Yellow']}WARNING: Failed to fetch comments for {issue_key}: {resp.text}{COLORS['Reset']}"
        )
        return []
    return resp.json().get("comments", [])


def transition_jira_issue(
    jira_domain: str, issue_key: str, transition_id: str, headers: dict[str, str]
) -> None:
    """Transitions a Jira ticket state using specific standard Transition ID."""
    url = f"https://{jira_domain}/rest/api/3/issue/{issue_key}/transitions"
    body = {"transition": {"id": transition_id}}
    resp = requests.post(url, headers=headers, json=body, timeout=15)
    resp.raise_for_status()


def parse_adf_text(node: Any) -> str:
    """Recursively parses Atlassian Document Format (ADF) node trees into simple raw text."""
    if not node:
        return ""
    if isinstance(node, dict):
        if "text" in node:
            return node["text"]
        if "content" in node:
            parts = [parse_adf_text(c) for c in node["content"]]
            sep = "\n" if node.get("type") == "paragraph" else ""
            return "".join(parts) + sep
    return ""


def new_jira_issue(
    jira_domain: str,
    headers: dict[str, str],
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Support",
    custom_fields: dict[str, Any] | None = None,
) -> dict:
    """Creates a new Jira ticket with ADF v3 description and support for custom fields."""
    issue_obj = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            },
        }
    }

    if custom_fields:
        for k, v in custom_fields.items():
            issue_obj["fields"][k] = v

    url = f"https://{jira_domain}/rest/api/3/issue"
    resp = requests.post(url, headers=headers, json=issue_obj, timeout=15)
    resp.raise_for_status()
    return resp.json()


# --- AWS CLOUDWATCH LOGS UTILITIES ---


def invoke_logs_insights_query(
    query_string: str,
    log_group_name: str,
    start_time: int,
    end_time: int,
    region: str,
    profile_name: str,
) -> dict:
    """
    Triggers an AWS CloudWatch Logs Insights query and polls for results
    using standard AWS CLI in the background.
    """
    if not profile_name:
        profile_name = os.environ.get("AWS_PROFILE", "prod-support")
    import json

    start_cmd = [
        "aws",
        "logs",
        "start-query",
        "--log-group-name",
        log_group_name,
        "--start-time",
        str(start_time),
        "--end-time",
        str(end_time),
        "--query-string",
        query_string,
        "--profile",
        profile_name,
        "--region",
        region,
    ]

    r = subprocess.run(
        start_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if r.returncode != 0:
        raise RuntimeError(f"AWS Logs start-query failed: {r.stderr.strip()}")

    start_json = json.loads(r.stdout.strip())
    query_id = start_json["queryId"]

    get_cmd = [
        "aws",
        "logs",
        "get-query-results",
        "--query-id",
        query_id,
        "--profile",
        profile_name,
        "--region",
        region,
    ]

    while True:
        time.sleep(2)
        r_get = subprocess.run(
            get_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if r_get.returncode != 0:
            raise RuntimeError(
                f"AWS Logs get-query-results failed: {r_get.stderr.strip()}"
            )

        res_json = json.loads(r_get.stdout.strip())
        status = res_json.get("status", "")
        if status in ("Complete", "Failed", "Cancelled"):
            return res_json


def convert_logs_to_dict(results_json: dict) -> list[dict[str, str]]:
    """Converts raw CloudWatch Insights log records lists into standard Python dictionaries."""
    records = []
    for row in results_json.get("results", []):
        obj = {}
        for field in row:
            obj[field["field"]] = field["value"]
        records.append(obj)
    return records
