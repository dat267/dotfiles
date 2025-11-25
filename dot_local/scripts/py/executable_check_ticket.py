#!/usr/bin/env python3
"""
check_ticket.py - Jira Support Ticket Checking & Content Parser Tool
Ports the PowerShell fetch_ticket.ps1 functionality directly into robust Python.
"""

import argparse
import json
import os
import sys

# Ensure Python directory is in path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import (
    COLORS,
    get_jira_comments,
    get_jira_config,
    parse_adf_text,
    search_jira_tickets,
    write_header,
    write_success,
)


def main():
    parser = argparse.ArgumentParser(
        description="Jira Support Ticket Checking & Content Parser Tool"
    )
    parser.add_argument("ticket_key", help="The Jira ticket key (e.g., ENGSUP-29406)")
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Save the raw parsed ticket JSON to the TEMP folder",
    )

    args = parser.parse_args()
    ticket_key = args.ticket_key.upper().strip()

    # 1. LOAD CONFIG
    try:
        config = get_jira_config()
    except Exception as e:
        print(
            f"{COLORS['Red']}CRITICAL ERROR: Failed to load Jira config: {e}{COLORS['Reset']}"
        )
        sys.exit(1)

    write_header(f"FETCHING JIRA TICKET: {ticket_key}", "Cyan")

    # 2. QUERY JIRA TICKET FIELDS
    fields = ["key", "summary", "status", "description", "created", "updated"]
    try:
        issues = search_jira_tickets(
            jira_domain=config["Domain"],
            jql_query=f"key = {ticket_key}",
            headers=config["Headers"],
            fields=fields,
        )
    except Exception as e:
        print(
            f"{COLORS['Red']}Failed to fetch ticket from Jira API: {e}{COLORS['Reset']}"
        )
        sys.exit(1)

    if not issues:
        print(
            f"{COLORS['Red']}ERROR: Ticket '{ticket_key}' not found.{COLORS['Reset']}"
        )
        sys.exit(1)

    issue = issues[0]
    summary = issue["fields"].get("summary", "N/A")
    status = issue["fields"]["status"].get("name", "N/A")
    description_node = issue["fields"].get("description")
    description = parse_adf_text(description_node).strip()

    print(f"  * Key     : {COLORS['Green']}{ticket_key}{COLORS['Reset']}")
    print(f"  * Summary : {COLORS['Green']}{summary}{COLORS['Reset']}")
    print(f"  * Status  : {COLORS['Yellow']}{status}{COLORS['Reset']}")

    # 3. PRINT DESCRIPTION
    write_header("TICKET DESCRIPTION", "DarkGray")
    if description:
        print(description)
    else:
        print(f"{COLORS['DarkGray']}(No description provided){COLORS['Reset']}")

    # 4. FETCH AND PARSE COMMENTS
    write_header("TICKET COMMENTS (LATEST 10)", "DarkGray")
    try:
        comments_list = get_jira_comments(
            jira_domain=config["Domain"],
            issue_key=ticket_key,
            headers=config["Headers"],
            max_results=10,
        )
    except Exception as e:
        print(
            f"{COLORS['Yellow']}WARNING: Failed to fetch comments: {e}{COLORS['Reset']}"
        )
        comments_list = []

    parsed_comments = []
    if comments_list:
        for idx, c in enumerate(comments_list, 1):
            author_name = (
                c["author"].get("displayName", "Unknown")
                if c.get("author")
                else "Unknown"
            )
            created_at = c.get("created", "N/A")
            comment_text = parse_adf_text(c.get("body")).strip()

            print(
                f"\n  {COLORS['Cyan']}[Comment #{idx}] By: {author_name} ({created_at}){COLORS['Reset']}"
            )
            print(f"  {'-'*60}")
            # Indent comment lines for visual clarity
            indented = "\n".join([f"    {line}" for line in comment_text.split("\n")])
            print(indented)

            parsed_comments.append(
                {"created": created_at, "author": author_name, "text": comment_text}
            )
    else:
        print(
            f"{COLORS['DarkGray']}(No comments found on this ticket){COLORS['Reset']}"
        )

    # 5. OPTIONAL SAVE TO JSON
    if args.save_json:
        ticket_data = {
            "Key": ticket_key,
            "Summary": summary,
            "Status": status,
            "Description": description,
            "Comments": parsed_comments,
        }

        temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))
        json_path = os.path.join(temp_dir, f"ticket_detail_{ticket_key.lower()}.json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(ticket_data, f, indent=4, ensure_ascii=False)
            print("")
            write_success(f"Parsed ticket details exported to JSON: {json_path}")
        except Exception as e:
            print(
                f"{COLORS['Yellow']}WARNING: Failed to save JSON backup: {e}{COLORS['Reset']}"
            )


if __name__ == "__main__":
    main()
