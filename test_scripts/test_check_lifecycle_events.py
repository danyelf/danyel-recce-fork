#!/usr/bin/env python3
"""
ABOUTME: Test script for check lifecycle events (created, ran, approved)
ABOUTME: Exercises log_created_check, log_ran_check, log_approved_check with lifecycle tracking properties

This script creates, runs, and approves checks to verify that the event logging
properly captures check_id, check_type, and check_position for workflow analysis.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

def test_check_lifecycle():
    """Test the complete check lifecycle: create → run → approve"""
    print("\n" + "="*60)
    print("Testing Check Lifecycle Events")
    print("="*60)

    # Get existing checks first (triggers minimal API interaction)
    print("\n[1/5] Getting existing checks...")
    response = requests.get(f"{BASE_URL}/checks")
    if not response.ok:
        print(f"ERROR: Failed to get checks: {response.text}")
        return False

    initial_checks = response.json()
    print(f"Found {len(initial_checks)} existing checks")

    # Create first check
    print("\n[2/5] Creating Check #1 (query_diff)...")
    check1_payload = {
        "name": "Lifecycle Test Check 1",
        "type": "query_diff",
        "params": {
            "sql_template": "SELECT * FROM {{ ref('customers') }}"
        }
    }
    response = requests.post(f"{BASE_URL}/checks", json=check1_payload)
    if not response.ok:
        print(f"ERROR: Failed to create check 1: {response.text}")
        return False

    check1_data = response.json()
    check1_id = check1_data.get("check_id")
    print(f"✓ Created check 1 with ID: {check1_id}")
    print(f"  Event should have: check_id, check_type='query_diff', check_position=1")

    # Create second check
    print("\n[2b/5] Creating Check #2 (row_count_diff)...")
    check2_payload = {
        "name": "Lifecycle Test Check 2",
        "type": "row_count_diff",
        "params": {
            "model": "customers"
        }
    }
    response = requests.post(f"{BASE_URL}/checks", json=check2_payload)
    if not response.ok:
        print(f"ERROR: Failed to create check 2: {response.text}")
        return False

    check2_data = response.json()
    check2_id = check2_data.get("check_id")
    print(f"✓ Created check 2 with ID: {check2_id}")
    print(f"  Event should have: check_id, check_type='row_count_diff', check_position=2")

    time.sleep(1)

    # Run check 1
    print("\n[3/5] Running Check #1...")
    run1_payload = {
        "type": "query_diff",
        "params": {
            "sql_template": "SELECT * FROM {{ ref('customers') }}"
        },
        "check_id": str(check1_id),
        "nowait": True
    }
    response = requests.post(f"{BASE_URL}/runs", json=run1_payload)
    if not response.ok:
        print(f"ERROR: Failed to run check 1: {response.text}")
        return False

    run1_data = response.json()
    print(f"✓ Ran check 1 with run ID: {run1_data.get('run_id')}")
    print(f"  Event should have: check_id, check_type='query_diff', check_position=1")

    time.sleep(2)

    # Run check 2
    print("\n[3b/5] Running Check #2...")
    run2_payload = {
        "type": "row_count_diff",
        "params": {
            "model": "customers"
        },
        "check_id": str(check2_id),
        "nowait": True
    }
    response = requests.post(f"{BASE_URL}/runs", json=run2_payload)
    if not response.ok:
        print(f"ERROR: Failed to run check 2: {response.text}")
        return False

    run2_data = response.json()
    print(f"✓ Ran check 2 with run ID: {run2_data.get('run_id')}")
    print(f"  Event should have: check_id, check_type='schema_diff', check_position=2")

    time.sleep(1)

    # Approve check 1
    print("\n[4/5] Approving Check #1...")
    approve1_payload = {"is_checked": True}
    response = requests.patch(f"{BASE_URL}/checks/{check1_id}", json=approve1_payload)
    if not response.ok:
        print(f"ERROR: Failed to approve check 1: {response.text}")
        return False

    print(f"✓ Approved check 1")
    print(f"  Event should have: check_id, check_type='query_diff', check_position=1")

    # Approve check 2
    print("\n[4b/5] Approving Check #2...")
    approve2_payload = {"is_checked": True}
    response = requests.patch(f"{BASE_URL}/checks/{check2_id}", json=approve2_payload)
    if not response.ok:
        print(f"ERROR: Failed to approve check 2: {response.text}")
        return False

    print(f"✓ Approved check 2")
    print(f"  Event should have: check_id, check_type='schema_diff', check_position=2")

    time.sleep(1)

    print("\n[5/5] Test Complete!")
    print("\n" + "="*60)
    print("Expected events in RECCE_DEBUG output:")
    print("="*60)
    print("""
[RECCE_DEBUG] Logging event: [User] created_check {
  'check_id': '...',
  'check_type': 'query_diff',
  'check_position': 1
}

[RECCE_DEBUG] Logging event: [User] created_check {
  'check_id': '...',
  'check_type': 'row_count_diff',
  'check_position': 2
}

[RECCE_DEBUG] Logging event: [User] ran_check {
  'check_id': '...',
  'check_type': 'query_diff',
  'check_position': 1
}

[RECCE_DEBUG] Logging event: [User] ran_check {
  'check_id': '...',
  'check_type': 'row_count_diff',
  'check_position': 2
}

[RECCE_DEBUG] Logging event: [User] approved_check {
  'check_id': '...',
  'check_type': 'query_diff',
  'check_position': 1
}

[RECCE_DEBUG] Logging event: [User] approved_check {
  'check_id': '...',
  'check_type': 'row_count_diff',
  'check_position': 2
}
    """)

    return True

if __name__ == "__main__":
    try:
        success = test_check_lifecycle()
        if success:
            print("\n✓ All API calls completed successfully!")
            print("Check the server output for [RECCE_DEBUG] logging events")
        else:
            print("\n✗ Test failed")
            exit(1)
    except Exception as e:
        print(f"\n✗ Exception: {e}")
        exit(1)
