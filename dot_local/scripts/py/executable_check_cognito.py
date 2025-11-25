#!/usr/bin/env python3
"""
check_cognito.py - AWS Cognito and Metis Worker Maintenance & Alignment Tool
Upfront read-only status checks followed by a single All-In-One (AIO) alignment mutation block.
"""

import argparse
import json
import os
import random
import string
import sys
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Ensure Python directory is in path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import (
    COLORS,
    confirm_execution,
    export_backup,
    run_redash,
    write_header,
    write_success,
)

# 1. INITIALIZE CONFIG
USER_POOL_ID = os.environ.get("COGNITO_WORKER_POOL_ID", "")
AWS_PROFILE = os.environ.get("AWS_PROFILE", "prod-support")
AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")


def get_cognito_client():
    """Initializes and returns boto3 Cognito client using prod profile."""
    try:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        return session.client("cognito-idp")
    except Exception as e:
        print(f"{COLORS['Red']}Failed to initialize AWS session: {e}{COLORS['Reset']}")
        sys.exit(1)


def backup_cognito_user(user_data: dict[str, Any], identifier: str) -> None:
    """Saves a JSON snapshot of the Cognito user attributes into the TEMP folder."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    clean_id = "".join([c if c.isalnum() else "_" for c in identifier])
    temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))
    backup_path = os.path.join(temp_dir, f"cognito_user_{clean_id}_{timestamp}.json")

    try:
        # Convert datetime objects to string for JSON serialization
        def json_serial(obj):
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            raise TypeError("Type not serializable")

        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(user_data, f, default=json_serial, indent=4)
        write_success(f"Cognito user backup saved to: {backup_path}")
    except Exception as e:
        print(
            f"{COLORS['Yellow']}WARNING: Failed to save Cognito backup: {e}{COLORS['Reset']}"
        )


def generate_random_password(length: int = 8) -> str:
    """Generates a random digits password matching standard support reset format."""
    return "".join(random.choices(string.digits, k=length))


def main():
    parser = argparse.ArgumentParser(
        description="AWS Cognito and Metis Worker Maintenance & Alignment Tool"
    )
    parser.add_argument("identifier", help="Worker email address or mobile number")
    parser.add_argument(
        "device_key", nargs="?", default="", help="Optional worker device key"
    )
    parser.add_argument(
        "--delete", action="store_true", help="Permanently delete the user from Cognito"
    )

    args = parser.parse_args()
    identifier = args.identifier
    device_key = args.device_key

    client = get_cognito_client()

    # -------------------------------------------------------------------------
    # ACTION: DELETE USER
    # -------------------------------------------------------------------------
    if args.delete:
        write_header("DELETE COGNITO USER", "Red")
        if confirm_execution(
            f"Are you sure you want to PERMANENTLY DELETE Cognito user '{identifier}'?"
        ):
            try:
                client.admin_delete_user(UserPoolId=USER_POOL_ID, Username=identifier)
                write_success(f"User '{identifier}' successfully deleted from Cognito.")
            except client.exceptions.UserNotFoundException:
                print(
                    f"{COLORS['Yellow']}WARNING: User '{identifier}' not found in Cognito.{COLORS['Reset']}"
                )
            except ClientError as e:
                print(
                    f"{COLORS['Red']}Cognito API Error: {e.response['Error']['Message']}{COLORS['Reset']}"
                )
        sys.exit(0)

    print("========================================================================")
    print("      AWS COGNITO & DATABASE ALIGNMENT CHECK (READ-ONLY CHECKS)        ")
    print("========================================================================")

    # -------------------------------------------------------------------------
    # READ-ONLY CHECK 1: FETCH WORKER DATABASE METADATA
    # -------------------------------------------------------------------------
    write_header("1. DATABASE WORKER METADATA", "Cyan")
    sql_query = f"SELECT id, country, phone_no, email, cognito_username FROM metis.worker WHERE email = '{identifier}' OR phone_no = '{identifier}' LIMIT 1"
    worker_rows = run_redash("HUB", sql_query)

    if not worker_rows:
        print(
            f"{COLORS['Red']}CRITICAL ERROR: No worker found in Metis database for: {identifier}{COLORS['Reset']}"
        )
        sys.exit(1)

    worker = worker_rows[0]
    print(
        f"{COLORS['DarkGray']}Worker resolved successfully from HUB:{COLORS['Reset']}"
    )
    for k, v in worker.items():
        print(f"  {k:<18} : {v}")

    # -------------------------------------------------------------------------
    # READ-ONLY CHECK 2: COGNITO STATUS RETRIEVAL & BACKUP
    # -------------------------------------------------------------------------
    write_header("2. COGNITO USER DIRECTORY STATUS", "Cyan")
    print(f"Retrieving user status for '{identifier}' from AWS pool...")

    cognito_uuid = None
    user_status = None
    existing_attributes = []
    user_exists = False

    try:
        existing_user = client.admin_get_user(
            UserPoolId=USER_POOL_ID, Username=identifier
        )
        cognito_uuid = existing_user["Username"]
        user_status = existing_user.get("UserStatus")
        existing_attributes = existing_user.get("UserAttributes", [])
        user_exists = True

        print(f"  - User Status      : {COLORS['Green']}{user_status}{COLORS['Reset']}")
        print(
            f"  - Cognito UUID     : {COLORS['Green']}{cognito_uuid}{COLORS['Reset']}"
        )
        print("  - Attributes:")
        for attr in existing_attributes:
            print(f"    * {attr['Name']:<20} : {attr['Value']}")

        backup_cognito_user(existing_user, identifier)
    except client.exceptions.UserNotFoundException:
        print(
            f"  - Cognito Status   : {COLORS['Yellow']}USER NOT FOUND (Needs Creation){COLORS['Reset']}"
        )
    except ClientError as e:
        print(
            f"{COLORS['Red']}  - Cognito Error    : {e.response['Error']['Message']}{COLORS['Reset']}"
        )
        sys.exit(1)

    # -------------------------------------------------------------------------
    # READ-ONLY CHECK 3: PRINCIPAL COMPARISON & METADATA DIFF
    # -------------------------------------------------------------------------
    write_header("3. PRINCIPAL METADATA DIFFERENCES", "Cyan")
    is_email = "@" in identifier

    # Construct candidate principal object
    new_principal = {
        "userId": worker["id"],
        "username": cognito_uuid if cognito_uuid else "--WILL BE GENERATED--",
        "userCountry": worker["country"],
        "corporateCountry": "ARE",
        "userType": "WORKER",
        "poolId": USER_POOL_ID,
        "onboardType": "EMAIL" if is_email else "PHONE",
    }

    if device_key:
        new_principal["deviceKey"] = device_key

    if is_email:
        new_principal["email"] = worker["email"]
    else:
        new_principal["phoneNumber"] = worker["phone_no"]

    new_principal_json = json.dumps(new_principal, separators=(",", ":"))

    old_principal_str = next(
        (
            attr["Value"]
            for attr in existing_attributes
            if attr["Name"] == "custom:principal"
        ),
        None,
    )
    if old_principal_str:
        try:
            old_principal = json.loads(old_principal_str)
            print(
                "Comparing current Cognito custom:principal vs new proposed metadata:"
            )
            all_keys = set(list(old_principal.keys()) + list(new_principal.keys()))
            for key in sorted(all_keys):
                old_val = old_principal.get(key)
                new_val = new_principal.get(key)
                if old_val != new_val:
                    print(
                        f"  {COLORS['Yellow']}[DIFF] {key:<18} : {old_val} -> {new_val}{COLORS['Reset']}"
                    )
                else:
                    print(
                        f"  {COLORS['DarkGray']}[SAME] {key:<18} : {old_val}{COLORS['Reset']}"
                    )
        except Exception:
            print(f"  - Old Principal (RAW)  : {old_principal_str}")
            print(f"  - New Principal Target : {new_principal_json}")
    else:
        print(
            f"  - Cognito Custom Principal: {COLORS['Yellow']}Not initialized in Cognito.{COLORS['Reset']}"
        )
        print(f"  - Proposed Principal Json : {new_principal_json}")

    # -------------------------------------------------------------------------
    # SAFETY PROMPT: ALL-IN-ONE (AIO) MUTATION BLOCK
    # -------------------------------------------------------------------------
    write_header("ALL-IN-ONE (AIO) UPDATE CONFIRMATION", "Yellow")
    print("This will execute the following mutations in sequence:")
    if not user_exists:
        print(f"  [+] Create user '{identifier}' in Cognito.")
    if not user_exists or user_status == "FORCE_CHANGE_PASSWORD":
        print("  [+] Generate and set permanent numeric password.")
    print("  [+] Update Cognito custom:principal attribute.")
    print("  [+] Back up metis.worker DB record.")
    print("  [+] Align Metis database cognito_username field.")
    print("------------------------------------------------------------------------")

    if not confirm_execution("Proceed with the All-In-One (AIO) update alignment?"):
        sys.exit(0)

    # -------------------------------------------------------------------------
    # MUTATION PHASE: AIO WORKFLOW
    # -------------------------------------------------------------------------
    write_header("EXECUTING MUTATION PHASE", "Magenta")

    # Step A: Ensure Cognito user exists
    if not user_exists:
        print("Creating user in Cognito...")
        user_attrs = []
        if is_email:
            user_attrs = [
                {"Name": "email", "Value": identifier},
                {"Name": "email_verified", "Value": "true"},
            ]
        else:
            user_attrs = [
                {"Name": "phone_number", "Value": identifier},
                {"Name": "phone_number_verified", "Value": "true"},
            ]

        try:
            create_res = client.admin_create_user(
                UserPoolId=USER_POOL_ID,
                Username=identifier,
                UserAttributes=user_attrs,
                MessageAction="SUPPRESS",
            )
            cognito_uuid = create_res["User"]["Username"]
            user_status = create_res["User"].get("UserStatus")
            # Update username in principal object since it's now resolved
            new_principal["username"] = cognito_uuid
            new_principal_json = json.dumps(new_principal, separators=(",", ":"))
            write_success(f"Cognito user successfully created (UUID: {cognito_uuid}).")
        except ClientError as e:
            print(
                f"{COLORS['Red']}Failed to create Cognito user: {e.response['Error']['Message']}{COLORS['Reset']}"
            )
            sys.exit(1)

    # Step B: Password Reset Compliance
    if not user_exists or user_status == "FORCE_CHANGE_PASSWORD":
        print("Setting permanent user password...")
        final_password = generate_random_password()
        try:
            client.admin_set_user_password(
                UserPoolId=USER_POOL_ID,
                Username=cognito_uuid,
                Password=final_password,
                Permanent=True,
            )
            write_success(
                f"Password successfully updated to: {final_password} (Permanent)"
            )
        except ClientError as e:
            print(
                f"{COLORS['Red']}Failed to set password: {e.response['Error']['Message']}{COLORS['Reset']}"
            )
            sys.exit(1)

    # Step C: Update Cognito custom:principal
    print("Updating Cognito custom:principal attribute...")
    try:
        client.admin_update_user_attributes(
            UserPoolId=USER_POOL_ID,
            Username=cognito_uuid,
            UserAttributes=[{"Name": "custom:principal", "Value": new_principal_json}],
        )
        write_success("Cognito custom:principal successfully updated.")
    except ClientError as e:
        print(
            f"{COLORS['Red']}Failed to update Cognito attributes: {e.response['Error']['Message']}{COLORS['Reset']}"
        )
        sys.exit(1)

    # Step D: Capture DB Snapshot Backup
    print("Capturing database snapshot backup of metis.worker...")
    db_backup_query = f"SELECT * FROM metis.worker WHERE id = '{worker['id']}';"
    db_backup_data = run_redash("HUB", db_backup_query)
    export_backup(db_backup_data, "metis.worker")

    # Step E: Apply Metis Database Update
    db_update_sql = f"UPDATE metis.worker SET cognito_username = '{cognito_uuid}' WHERE id = '{worker['id']}' RETURNING id, email, phone_no, cognito_username;"
    print("Applying database update query...")
    try:
        update_result = run_redash("HUB", db_update_sql)
        if update_result:
            write_header("POST-CHECK VERIFICATION", "Green")
            res_row = update_result[0]
            print(f"{COLORS['Cyan']}Database Record Updated Fields:")
            for k, v in res_row.items():
                print(f"  {k:<18} : {v}")
            print(COLORS["Reset"])
            write_success(
                "All-In-One (AIO) Cognito alignment and database update completed successfully."
            )
        else:
            print(
                f"{COLORS['Red']}Database Update returned empty results. Verify metis.worker manually.{COLORS['Reset']}"
            )
            sys.exit(1)
    except Exception as e:
        print(f"{COLORS['Red']}Database Update SQL failed: {e}{COLORS['Reset']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
