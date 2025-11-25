#!/usr/bin/env python3
"""
check_nationality.py - Metis Worker Database and Cognito Country/Nationality Alignment Tool
Upfront read-only checks followed by a single All-In-One (AIO) update block.
"""

import argparse
import json
import os
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
    backup_path = os.path.join(
        temp_dir, f"cognito_user_{clean_id}_nationality_{timestamp}.json"
    )

    try:

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


def main():
    parser = argparse.ArgumentParser(
        description="Metis Worker Database and Cognito Country/Nationality Alignment Tool"
    )
    parser.add_argument("worker_id", help="Worker Unique ID (e.g. WRK-CRP-...)")
    parser.add_argument(
        "target_country",
        nargs="?",
        default="IND",
        help="Target 3-letter ISO country code (default: IND)",
    )
    parser.add_argument(
        "target_country_full",
        nargs="?",
        default="India",
        help="Target full country name (default: India)",
    )

    args = parser.parse_args()
    worker_id = args.worker_id
    target_country = args.target_country.upper().strip()
    target_country_full = args.target_country_full.strip()

    client = get_cognito_client()

    print("========================================================================")
    print("      WORKER NATIONALITY & COUNTRY ALIGNMENT CHECK (READ CHECKS)        ")
    print("========================================================================")
    print(f"Target Country ISO  : {target_country}")
    print(f"Target Country Full : {target_country_full}")

    # -------------------------------------------------------------------------
    # READ-ONLY CHECK 1: FETCH DATABASE WORKER RECORD
    # -------------------------------------------------------------------------
    write_header("1. DATABASE WORKER METADATA", "Cyan")
    sql_query = f"SELECT id, full_name, phone_no, country, kyc_info, cognito_username FROM metis.worker WHERE id = '{worker_id}'"
    worker_rows = run_redash("HUB", sql_query)

    if not worker_rows:
        print(
            f"{COLORS['Red']}CRITICAL ERROR: Worker not found in Metis database for ID: {worker_id}{COLORS['Reset']}"
        )
        sys.exit(1)

    worker = worker_rows[0]
    cognito_username = worker.get("cognito_username", "").strip()

    print(
        f"{COLORS['DarkGray']}Worker resolved successfully from HUB:{COLORS['Reset']}"
    )
    for k, v in worker.items():
        if k != "kyc_info":
            print(f"  {k:<18} : {v}")

    # Render KYC info
    kyc_country = None
    if worker.get("kyc_info"):
        try:
            # Handle Redash returning already parsed dict or string
            kyc_obj = (
                worker["kyc_info"]
                if isinstance(worker["kyc_info"], dict)
                else json.loads(worker["kyc_info"])
            )
            kyc_country = kyc_obj.get("country")
            print(f"  {'kyc_info.country':<18} : {kyc_country}")
            print(f"  {'kyc_info.natFull':<18} : {kyc_obj.get('nationalityFull')}")
        except Exception:
            print(f"  {'kyc_info (RAW)':<18} : {worker['kyc_info']}")

    # -------------------------------------------------------------------------
    # READ-ONLY CHECK 2: COGNITO RETRIEVAL & ATTRIBUTES Snapshot
    # -------------------------------------------------------------------------
    write_header("2. COGNITO DIRECTORY PROFILE", "Cyan")

    existing_attributes = []
    cognito_user_exists = False

    if not cognito_username:
        print(
            f"  {COLORS['Yellow']}- Cognito Link Status: NO COGNITO LINK FOUND (cognito_username field is empty){COLORS['Reset']}"
        )
    else:
        print(f"Retrieving user status for Cognito UUID '{cognito_username}'...")
        try:
            existing_user = client.admin_get_user(
                UserPoolId=USER_POOL_ID, Username=cognito_username
            )
            existing_attributes = existing_user.get("UserAttributes", [])
            cognito_user_exists = True

            print(
                f"  - Cognito UUID     : {COLORS['Green']}{cognito_username}{COLORS['Reset']}"
            )
            print(
                f"  - User Status      : {COLORS['Green']}{existing_user.get('UserStatus')}{COLORS['Reset']}"
            )

            # Save a local CA backup JSON
            backup_cognito_user(existing_user, cognito_username)
        except client.exceptions.UserNotFoundException:
            print(
                f"  {COLORS['Yellow']}- Cognito Status   : USER NOT FOUND IN COGNITO DIRECTORY{COLORS['Reset']}"
            )
        except ClientError as e:
            print(
                f"{COLORS['Red']}  - Cognito Error    : {e.response['Error']['Message']}{COLORS['Reset']}"
            )
            sys.exit(1)

    # -------------------------------------------------------------------------
    # READ-ONLY CHECK 3: PRINCIPAL METADATA DIFFERENCES (COGNITO)
    # -------------------------------------------------------------------------
    write_header("3. PRINCIPAL METADATA CORRECTION DIFF", "Cyan")

    old_principal_str = None
    new_principal_json = None
    principal_updated = False

    if cognito_user_exists:
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
                # Clone old principal and update country
                new_principal = old_principal.copy()
                new_principal["userCountry"] = target_country
                new_principal_json = json.dumps(new_principal, separators=(",", ":"))

                if old_principal.get("userCountry") != target_country:
                    print(
                        "Comparing current Cognito custom:principal vs new proposed metadata:"
                    )
                    for key in sorted(new_principal.keys()):
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
                    principal_updated = True
                else:
                    print(
                        f"{COLORS['Green']}Cognito principal already matches target country '{target_country}'.{COLORS['Reset']}"
                    )
            except Exception:
                print(f"  - Old Principal (RAW)  : {old_principal_str}")
        else:
            print(
                f"  {COLORS['Yellow']}- custom:principal  : NOT FOUND IN COGNITO ATTRIBUTES{COLORS['Reset']}"
            )
    else:
        print(
            f"  {COLORS['DarkGray']}- Cognito Principal  : Cognito account does not exist or link is missing. Skipping diff check.{COLORS['Reset']}"
        )

    # -------------------------------------------------------------------------
    # SAFETY PROMPT: ALL-IN-ONE (AIO) NATIONALITY UPDATE
    # -------------------------------------------------------------------------
    write_header("ALL-IN-ONE (AIO) UPDATE CONFIRMATION", "Yellow")
    print("This will execute the following mutations in sequence:")
    print("  [+] Back up metis.worker DB record.")
    print(f"  [+] Update DB country to '{target_country}' and merge KYC JSON fields.")
    if cognito_user_exists and principal_updated:
        print(
            f"  [+] Update Cognito custom:principal 'userCountry' to '{target_country}'."
        )
    else:
        print("  [ ] Cognito attributes are already in sync (Skipped).")
    print("------------------------------------------------------------------------")

    if not confirm_execution("Proceed with the All-In-One (AIO) nationality update?"):
        sys.exit(0)

    # -------------------------------------------------------------------------
    # MUTATION PHASE: AIO WORKFLOW
    # -------------------------------------------------------------------------
    write_header("EXECUTING MUTATION PHASE", "Magenta")

    # Step A: Capture Database Snapshot Backup
    print("Capturing database snapshot backup of metis.worker...")
    export_backup([worker], f"metis_worker_{worker_id}")

    # Step B: Apply Database Correction
    kyc_update = {
        "country": target_country,
        "countryFull": target_country_full,
        "nationality": target_country,
        "nationalityFull": target_country_full,
    }
    kyc_json = json.dumps(kyc_update, separators=(",", ":"))

    # Safe quote escaping for SQL query inclusion
    safe_kyc_json = kyc_json.replace("'", "''")
    db_update_sql = f"UPDATE metis.worker SET country = '{target_country}', kyc_info = kyc_info || '{safe_kyc_json}'::jsonb WHERE id = '{worker_id}' RETURNING id, country, kyc_info ->> 'country' as kyc_country;"

    print("Applying database correction query...")
    try:
        db_res = run_redash("HUB", db_update_sql)
        if db_res:
            write_success(
                f"Database updated successfully. New country: {db_res[0]['country']}, KYC country: {db_res[0]['kyc_country']}"
            )
        else:
            print(
                f"{COLORS['Red']}Failed to verify database update output.{COLORS['Reset']}"
            )
            sys.exit(1)
    except Exception as e:
        print(f"{COLORS['Red']}Failed to update database record: {e}{COLORS['Reset']}")
        sys.exit(1)

    # Step C: Apply Cognito Attribute Correction (if required)
    if cognito_user_exists and principal_updated and new_principal_json:
        print("Applying AWS Cognito attribute updates...")
        try:
            client.admin_update_user_attributes(
                UserPoolId=USER_POOL_ID,
                Username=cognito_username,
                UserAttributes=[
                    {"Name": "custom:principal", "Value": new_principal_json}
                ],
            )
            write_success("Cognito principal custom attribute successfully updated.")
        except ClientError as e:
            print(
                f"{COLORS['Red']}Failed to update Cognito custom attributes: {e.response['Error']['Message']}{COLORS['Reset']}"
            )
            sys.exit(1)

    # Step D: Final Verification Message
    write_header("POST-ALIGNMENT VERIFICATION", "Green")
    print(
        f"{COLORS['Cyan']}Please ask the worker to logout of their application and login again to refresh their token.{COLORS['Reset']}"
    )
    write_success("All-In-One (AIO) nationality alignment completed successfully.")


if __name__ == "__main__":
    main()
