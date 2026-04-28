#!/usr/bin/env python3
"""Test moving emails to folders."""

from dotenv import load_dotenv
load_dotenv()

from providers.gmail import GmailProvider
from config import get_config

# Test email IDs (10 promotional emails)
TEST_EMAIL_IDS = [
    "19dc52862a6e4638",
    "19dc4b9ebdfb72b8",
    "19dc55cd9a4cc163",
    "19dc0b17c4953e02",
    "19dc011e1b4c48d0",
    "19dc083a9d98e472",
    "19dc0815ead509d6",
    "19dbfd535da1d2fe",
    "19dc0004a39dbb87",
    "19dbf80658e1e269",
]

def create_label_if_not_exists(gmail, label_name):
    """Create a Gmail label if it doesn't exist. Returns label ID."""
    labels = gmail.list_labels()

    for label in labels:
        if label['name'] == label_name:
            print(f"Label '{label_name}' already exists (ID: {label['id']})")
            return label['id']

    result = gmail.service.users().labels().create(
        userId='me',
        body={
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
    ).execute()

    print(f"Created label '{label_name}' (ID: {result['id']})")
    return result['id']

def main():
    config = get_config('atanas')  # Use atanas profile

    print("Connecting to Gmail...")
    gmail = GmailProvider(config['gmail'])
    gmail.connect()

    # Create test folder
    label_name = "AI/Test-Promotional"
    label_id = create_label_if_not_exists(gmail, label_name)

    print(f"\nMoving 10 promotional emails to '{label_name}'...")

    success = 0
    failed = 0

    for email_id in TEST_EMAIL_IDS:
        try:
            result = gmail.move_email(email_id, add_labels=[label_id])
            if result:
                print(f"  ✓ Moved {email_id}")
                success += 1
            else:
                print(f"  ✗ Failed to move {email_id}")
                failed += 1
        except Exception as e:
            print(f"  ✗ Error moving {email_id}: {e}")
            failed += 1

    print(f"\nDone! Success: {success}, Failed: {failed}")
    print(f"Check your Gmail for the '{label_name}' folder")

    gmail.disconnect()

if __name__ == "__main__":
    main()
