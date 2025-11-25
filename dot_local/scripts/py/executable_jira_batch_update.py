#!/usr/bin/env python3
"""
jira_batch_update.py - Assign tickets to self and post a comment, concurrently.
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import (
    COLORS,
    add_jira_comment,
    get_jira_account_id,
    get_jira_config,
    search_jira_tickets,
    set_jira_assignee,
    write_header,
    write_success,
)


def main():
    parser = argparse.ArgumentParser(
        description="Assign tickets to self and add a comment"
    )
    parser.add_argument("jql", help="JQL query to select tickets")
    parser.add_argument("message", help="Comment message to post on each ticket")
    args = parser.parse_args()

    try:
        config = get_jira_config()
    except Exception as e:
        print(f"{COLORS['Red']}CRITICAL: {e}{COLORS['Reset']}")
        sys.exit(1)

    write_header("JIRA BATCH UPDATE", "Cyan")

    # Resolve self account ID
    self_account_id = get_jira_account_id(
        config["Domain"], config["Email"], config["Headers"]
    )
    if not self_account_id:
        print(
            f"{COLORS['Red']}Could not resolve own accountId for: {config['Email']}{COLORS['Reset']}"
        )
        sys.exit(1)

    issues = search_jira_tickets(
        config["Domain"], args.jql, config["Headers"], fields=["key", "assignee"]
    )

    if not issues:
        print(f"{COLORS['Yellow']}No issues found matching JQL.{COLORS['Reset']}")
        return

    print(
        f"Processing {COLORS['Green']}{len(issues)}{COLORS['Reset']} issue(s) concurrently..."
    )

    def update(issue):
        key = issue["key"]
        current_assignee = (issue["fields"].get("assignee") or {}).get("accountId")
        if current_assignee != self_account_id:
            set_jira_assignee(config["Domain"], key, self_account_id, config["Headers"])
        add_jira_comment(config["Domain"], key, args.message, config["Headers"])
        return key

    failures = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(update, issue): issue["key"] for issue in issues}
        for future in as_completed(futures):
            key = futures[future]
            try:
                future.result()
                print(f"  [{COLORS['Green']}{key}{COLORS['Reset']}] Updated.")
            except Exception as e:
                failures.append(key)
                print(f"  [{COLORS['Red']}{key}{COLORS['Reset']}] FAILED: {e}")

    if failures:
        print(
            f"\n{COLORS['Red']}{len(failures)} failure(s): {', '.join(failures)}{COLORS['Reset']}"
        )
    else:
        write_success("Batch update complete.")


if __name__ == "__main__":
    main()
