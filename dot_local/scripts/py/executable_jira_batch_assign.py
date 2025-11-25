#!/usr/bin/env python3
"""
jira_batch_assign.py - Batch re-assign Jira tickets matching a JQL filter to a target user.
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import (
    COLORS,
    get_jira_account_id,
    get_jira_config,
    search_jira_tickets,
    set_jira_assignee,
    write_header,
    write_success,
)


def main():
    parser = argparse.ArgumentParser(
        description="Batch re-assign Jira tickets to a target user"
    )
    parser.add_argument("jql", help="JQL query to select tickets")
    parser.add_argument("target_email", help="Email of the user to assign tickets to")
    args = parser.parse_args()

    try:
        config = get_jira_config()
    except Exception as e:
        print(f"{COLORS['Red']}CRITICAL: {e}{COLORS['Reset']}")
        sys.exit(1)

    write_header("JIRA BATCH ASSIGN", "Cyan")

    # Resolve target account ID
    target_account_id = get_jira_account_id(
        config["Domain"], args.target_email, config["Headers"]
    )
    if not target_account_id:
        print(
            f"{COLORS['Red']}Could not find accountId for: {args.target_email}{COLORS['Reset']}"
        )
        sys.exit(1)

    print(
        f"  Target : {COLORS['Green']}{args.target_email}{COLORS['Reset']} ({target_account_id})"
    )

    issues = search_jira_tickets(
        config["Domain"], args.jql, config["Headers"], fields=["key", "assignee"]
    )

    if not issues:
        print(f"{COLORS['Yellow']}No issues found matching JQL.{COLORS['Reset']}")
        return

    print(
        f"Re-assigning {COLORS['Green']}{len(issues)}{COLORS['Reset']} issue(s) concurrently..."
    )

    def assign(issue):
        key = issue["key"]
        current = (issue["fields"].get("assignee") or {}).get("accountId")
        if current == target_account_id:
            return key, "skipped"
        set_jira_assignee(config["Domain"], key, target_account_id, config["Headers"])
        return key, "assigned"

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(assign, issue): issue["key"] for issue in issues}
        for future in as_completed(futures):
            key = futures[future]
            try:
                _, status = future.result()
                color = COLORS["Green"] if status == "assigned" else COLORS["DarkGray"]
                print(f"  [{color}{key}{COLORS['Reset']}] {status.capitalize()}.")
            except Exception as e:
                print(f"  [{COLORS['Red']}{key}{COLORS['Reset']}] FAILED: {e}")

    write_success("Batch assign complete.")


if __name__ == "__main__":
    main()
