#!/usr/bin/env python3
"""
jira_auto_respond.py - Auto-respond to Jira tickets with an active first-response SLA cycle.
"""

import argparse
import os
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import (
    COLORS,
    add_jira_comment,
    get_jira_config,
    write_header,
    write_success,
)


def needs_first_response(issue: dict) -> bool:
    """Check if any custom SLA field named 'Time to first response' has an ongoing cycle."""
    for val in issue.get("fields", {}).values():
        if isinstance(val, dict) and val.get("name") == "Time to first response":
            return bool(val.get("ongoingCycle", False))
    return False


def respond_ticket(ticket_key: str, reply_text: str, config: dict) -> str:
    add_jira_comment(config["Domain"], ticket_key, reply_text, config["Headers"])
    return ticket_key


def main():
    parser = argparse.ArgumentParser(
        description="Auto-respond to Jira tickets with active first-response SLA"
    )
    parser.add_argument("jql", help="JQL query to find candidate tickets")
    parser.add_argument("reply", help="Auto-reply text to post as a comment")
    args = parser.parse_args()

    try:
        config = get_jira_config()
    except Exception as e:
        print(f"{COLORS['Red']}CRITICAL: {e}{COLORS['Reset']}")
        sys.exit(1)

    write_header("JIRA AUTO-RESPONDER", "Cyan")
    print("Searching for tickets needing first response...")

    # Fetch all fields so we can inspect custom SLA fields dynamically
    url = f"https://{config['Domain']}/rest/api/3/search/jql?jql={urllib.parse.quote(args.jql)}&maxResults=50"
    resp = requests.get(url, headers=config["Headers"], timeout=30)
    resp.raise_for_status()
    issues = resp.json().get("issues", [])

    if not issues:
        print(f"{COLORS['Yellow']}No active support tickets found.{COLORS['Reset']}")
        return

    to_respond = [i for i in issues if needs_first_response(i)]

    if not to_respond:
        print(
            f"{COLORS['Yellow']}No tickets currently need first response.{COLORS['Reset']}"
        )
        return

    print(
        f"Found {COLORS['Green']}{len(to_respond)}{COLORS['Reset']} ticket(s) with active SLA. Responding concurrently..."
    )

    failures = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(respond_ticket, issue["key"], args.reply, config): issue["key"]
            for issue in to_respond
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                future.result()
                print(f"  [{COLORS['Green']}{key}{COLORS['Reset']}] Auto-responded.")
            except Exception as e:
                failures.append(key)
                print(f"  [{COLORS['Red']}{key}{COLORS['Reset']}] FAILED: {e}")

    if failures:
        print(
            f"\n{COLORS['Red']}{len(failures)} reply(ies) failed: {', '.join(failures)}{COLORS['Reset']}"
        )
    else:
        write_success("All auto-responders posted successfully.")


if __name__ == "__main__":
    main()
