#!/usr/bin/env python3
"""
jira_resolve_noise.py - Auto-resolve noisy Jira tickets matching a JQL filter.
Adds a comment and transitions each matched ticket concurrently.
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import (
    COLORS,
    add_jira_comment,
    get_jira_config,
    search_jira_tickets,
    transition_jira_issue,
    write_header,
    write_success,
)


def resolve_ticket(
    ticket_key: str, comment: str, transition_id: str, config: dict
) -> str:
    add_jira_comment(config["Domain"], ticket_key, comment, config["Headers"])
    transition_jira_issue(
        config["Domain"], ticket_key, transition_id, config["Headers"]
    )
    return ticket_key


def main():
    parser = argparse.ArgumentParser(
        description="Auto-resolve noisy Jira tickets by JQL"
    )
    parser.add_argument("jql", help="JQL query to find noise tickets")
    parser.add_argument("comment", help="Comment to add before resolving")
    parser.add_argument(
        "transition_id", help="Jira transition ID (e.g. 111 for Resolved)"
    )
    args = parser.parse_args()

    try:
        config = get_jira_config()
    except Exception as e:
        print(f"{COLORS['Red']}CRITICAL: {e}{COLORS['Reset']}")
        sys.exit(1)

    write_header("JIRA AUTO-RESOLVE NOISE", "Cyan")
    print(f"  JQL: {COLORS['Yellow']}{args.jql}{COLORS['Reset']}")

    try:
        issues = search_jira_tickets(
            config["Domain"], args.jql, config["Headers"], fields=["key"]
        )
    except Exception as e:
        print(f"{COLORS['Red']}Failed to search tickets: {e}{COLORS['Reset']}")
        sys.exit(1)

    if not issues:
        print(f"{COLORS['Yellow']}No noise tickets found.{COLORS['Reset']}")
        return

    print(
        f"Found {COLORS['Green']}{len(issues)}{COLORS['Reset']} tickets. Processing concurrently..."
    )

    failures = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(
                resolve_ticket, issue["key"], args.comment, args.transition_id, config
            ): issue["key"]
            for issue in issues
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                future.result()
                print(f"  [{COLORS['Green']}{key}{COLORS['Reset']}] Resolved.")
            except Exception as e:
                failures.append(key)
                print(f"  [{COLORS['Red']}{key}{COLORS['Reset']}] FAILED: {e}")

    if failures:
        print(
            f"\n{COLORS['Red']}{len(failures)} ticket(s) failed: {', '.join(failures)}{COLORS['Reset']}"
        )
    else:
        write_success("All noise tickets resolved successfully.")


if __name__ == "__main__":
    main()
