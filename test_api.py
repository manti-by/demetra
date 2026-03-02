#!/usr/bin/env python3
"""
Test script for the Demetra FastAPI ticket creation API.

This script demonstrates how to send a POST request to create a Linear ticket
from raw text input.
"""

import asyncio
import json

import aiohttp


async def test_create_ticket(api_url: str = "http://localhost:8000"):
    """Test creating a ticket via the API."""

    # Sample raw text that needs to be processed into a ticket
    sample_text = """
    We need to implement a user authentication system for our web application.

    The system should support email/password login, password reset functionality,
    and session management. Users should be able to register with email verification.

    We need JWT tokens for API authentication and proper logout functionality.
    The frontend should redirect unauthenticated users to login page.

    Security requirements: password hashing with bcrypt, rate limiting for login attempts,
    and secure session handling.
    """

    payload = {
        "text": sample_text,
        "project_id": None,  # Optional: add your Linear project ID here
        "priority": 2,  # High priority
    }

    try:
        async with aiohttp.ClientSession() as session:
            print(f"Sending request to {api_url}/create-ticket")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print("\n" + "=" * 50 + "\n")

            async with session.post(
                f"{api_url}/create-ticket", json=payload, headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()

                print(f"Response status: {response.status}")
                print(f"Response: {json.dumps(result, indent=2)}")

                if result.get("success"):
                    print(f"\n✅ Successfully created ticket: {result.get('ticket_identifier')}")
                    print(f"   Ticket ID: {result.get('ticket_id')}")
                else:
                    print(f"\n❌ Failed to create ticket: {result.get('error')}")

    except aiohttp.ClientError as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


async def test_health_check(api_url: str = "http://localhost:8000"):
    """Test the health check endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}/health") as response:
                result = await response.json()
                print(f"Health check: {result}")
                return response.status == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False


async def main():
    """Main test function."""
    api_url = "http://localhost:8000"

    print("🧪 Testing Demetra FastAPI Ticket Creation API\n")

    # Test health check first
    print("1. Testing health check...")
    healthy = await test_health_check(api_url)
    if not healthy:
        print("❌ API is not healthy. Make sure the server is running.")
        print("   Start the server with: python run_api.py")
        return

    print("✅ API is healthy\n")

    # Test ticket creation
    print("2. Testing ticket creation...")
    await test_create_ticket(api_url)


if __name__ == "__main__":
    asyncio.run(main())
