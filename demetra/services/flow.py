import asyncio

from demetra.services.tui import print_message


async def user_input(options: list[tuple[str, str]]) -> tuple[str, str | None]:
    print_message("How would you like to proceed?")

    choices = []
    choice_map = {}
    for index, option in options:
        choices.extend([index, option])
        choice_map[index] = option
        print_message(f"  [{index}] {option}{' - default' if index == '1' else ''}")

    loop = asyncio.get_event_loop()
    while True:
        action = await loop.run_in_executor(None, lambda: input("Action: ").strip().lower())
        if not action:
            action = choice_map.get("1", "")
        if action in choices:
            break
        print_message("Invalid choice. Please try again.")

    action = choice_map[action] if action in choice_map else action

    comment = None
    if action == "comment":
        while True:
            comment = input("Enter comment: ").strip()
            if comment:
                break

    return action, comment
