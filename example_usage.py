#!/usr/bin/env python3
"""
Example usage of the Demetra FastAPI ticket creation API.
"""

import asyncio
import os

from fastapi_app import process_text_with_groq


async def example_local_usage():
    """
    Example of using the functions directly (without HTTP API).
    This is useful for testing or integrating into other Python code.
    """

    # Example raw text
    raw_text = """
    Our mobile app needs a new feature for user notifications.

    Users should be able to enable/disable different types of notifications:
    - Push notifications for messages
    - Email notifications for important updates
    - In-app notifications for activities

    The settings should be saved per user and sync across devices.
    We need a clean UI in the settings screen with toggle switches.

    Technical considerations:
    - Use FCM for push notifications
    - Store preferences in the database
    - Add notification scheduling system
    - Handle notification permissions properly
    """

    print("🔄 Processing text with Groq...")
    print(f"Raw text: {raw_text[:100]}...")
    print()

    try:
        # Process the text
        structured_data = await process_text_with_groq(raw_text)

        print("✅ Groq processing complete!")
        print("📋 Structured ticket data:")
        print(f"   Title: {structured_data['title']}")
        print(f"   Description: {structured_data['description'][:100]}...")
        print(f"   Tech Requirements: {structured_data['technical_requirements'][:100]}...")
        print(f"   Acceptance Criteria: {structured_data['acceptance_criteria'][:100]}...")
        print()

        # Note: We're not actually creating a Linear ticket here to avoid
        # creating test tickets in your real Linear workspace
        print("ℹ️  Linear ticket creation skipped for demo purposes")
        print("   To create actual tickets, ensure environment variables are set:")
        print("   - LINEAR_API_KEY")
        print("   - LINEAR_TEAM_ID")
        print("   - GROQ_API_KEY")

    except Exception as e:
        print(f"❌ Error: {e}")


def check_environment():
    """Check if required environment variables are set."""
    required_vars = {
        "LINEAR_API_KEY": "Required for Linear integration",
        "LINEAR_TEAM_ID": "Required for Linear team identification",
        "GROQ_API_KEY": "Required for text processing with Groq",
    }

    print("🔍 Checking environment variables...")

    missing_vars = []
    for var, description in required_vars.items():
        if os.environ.get(var):
            print(f"   ✅ {var}: Set")
        else:
            print(f"   ❌ {var}: Missing - {description}")
            missing_vars.append(var)

    if missing_vars:
        print(f"\n⚠️  Missing {len(missing_vars)} required environment variable(s)")
        print("   Set them before running the API or using the functions")
    else:
        print("\n✅ All required environment variables are set")

    return len(missing_vars) == 0


async def main():
    """Main demonstration function."""
    print("🚀 Demetra FastAPI Ticket Creator - Example Usage\n")

    # Check environment
    env_ok = check_environment()
    print()

    if not env_ok:
        print("💡 To set environment variables:")
        print("   export LINEAR_API_KEY='your_key'")
        print("   export LINEAR_TEAM_ID='your_team_id'")
        print("   export GROQ_API_KEY='your_groq_key'")
        print()

    # Run example
    await example_local_usage()

    print("\n📚 Next steps:")
    print("   1. Set required environment variables")
    print("   2. Start the API server: make api")
    print("   3. Test with: make test-api")
    print("   4. View docs at: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(main())
