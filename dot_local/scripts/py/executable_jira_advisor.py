#!/usr/bin/env python3
"""
jira_advisor.py - Fetch and display Jira ticket data as structured JSON for AI analysis.
Outputs key, summary, status, priority, assignee, description, and latest comments.
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import (
    COLORS,
    get_jira_comments,
    get_jira_config,
    parse_adf_text,
    search_jira_tickets,
)


def fetch_ticket_data(issue: dict, config: dict) -> dict:
    key = issue["key"]
    fields = issue["fields"]

    comments_raw = get_jira_comments(
        config["Domain"], key, config["Headers"], max_results=3
    )
    comments = [
        {
            "created": c.get("created"),
            "author": (c.get("author") or {}).get("displayName", "Unknown"),
            "authorId": (c.get("author") or {}).get("accountId"),
            "text": parse_adf_text(c.get("body")).strip(),
        }
        for c in comments_raw
    ]

    return {
        "Key": key,
        "Summary": fields.get("summary", ""),
        "Status": (fields.get("status") or {}).get("name", ""),
        "Priority": (fields.get("priority") or {}).get("name", ""),
        "Assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
        "AssigneeId": (fields.get("assignee") or {}).get("accountId"),
        "ReporterId": (fields.get("reporter") or {}).get("accountId"),
        "Description": parse_adf_text(fields.get("description")).strip(),
        "Comments": comments,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Jira ticket data as structured JSON"
    )
    parser.add_argument("jql", help="JQL query to select tickets")
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )
    args = parser.parse_args()

    try:
        config = get_jira_config()
    except Exception as e:
        print(f"{COLORS['Red']}CRITICAL: {e}{COLORS['Reset']}")
        sys.exit(1)

    fields = [
        "key",
        "summary",
        "status",
        "description",
        "assignee",
        "reporter",
        "priority",
    ]
    issues = search_jira_tickets(
        config["Domain"], args.jql, config["Headers"], fields=fields
    )

    if not issues:
        print("[]")
        return

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda i: fetch_ticket_data(i, config), issues))

    indent = 2 if args.pretty else None
    print(json.dumps(results, indent=indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
