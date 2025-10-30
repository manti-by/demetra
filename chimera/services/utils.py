import shutil


async def print_message(message: str):
    COLOR, ENDC = "\x1b[2m", "\033[0m"
    size = shutil.get_terminal_size((80, 20))

    print(f"\n{message}\n")
    print(COLOR + "-" * size.columns + ENDC)


async def handle_interrupt(question: str) -> dict[str, str]:
    print("\n" + "=" * 50)
    print("🤖 ACTION REQUIRES APPROVAL")
    print("=" * 50)

    allowed_decisions = ("approve", "reject", "comment")

    print(f"Question: {question}")
    print(f"Allowed decisions: {', '.join(allowed_decisions)}")

    decision = await get_user_decision(allowed_decisions=allowed_decisions)

    print("=" * 50 + "\n")
    return decision


async def get_user_decision(allowed_decisions: tuple) -> dict[str, str]:
    print("How would you like to proceed with?")
    for i, decision in enumerate(allowed_decisions, 1):
        print(f"  [{i}] {decision}")

    while True:
        try:
            choice = input(f"Enter your choice (1-{len(allowed_decisions)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(allowed_decisions):
                decision_type = allowed_decisions[idx]
                break
        except (ValueError, IndexError):
            pass
        print("Invalid choice. Please try again.")

    if decision_type == "comment":
        print("\nEnter your comment:")
        comment = input(" ").strip()
        return {"type": "comment", "comment": comment}

    return {"type": decision_type}
