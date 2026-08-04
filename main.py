import argparse
import asyncio
import logging.config
import sys

from rich.console import Console
from rich.table import Table
from sqlalchemy.exc import SQLAlchemyError

from demetra.library.exceptions import (
    AuthError,
    AutoCancelledError,
    DemetraError,
    InfiniteLoopError,
    UserCancelledError,
)
from demetra.services.allowlist import (
    add_entry,
    list_entries,
    load_seed_file,
    remove_entry,
    seed_existing_users,
)
from demetra.services.auth import reset_password
from demetra.services.database import init_db, mark_session_posted
from demetra.services.linear import post_comment, update_ticket_status
from demetra.services.tui import print_heading, print_message
from demetra.services.utils import setup_session_logging
from demetra.settings import (
    ALLOWLIST_SEED_FILE,
    DEFAULT_USER_ID,
    LINEAR,
    LOGGING,
    MAX_BUILD_ATTEMPTS,
)
from demetra.workflows.build import run_build_step
from demetra.workflows.cleanup import cleanup_workflow, commit_and_push
from demetra.workflows.plan import run_plan_step
from demetra.workflows.setup import setup_workflow


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(prog="demetra", description="Run implementation workflow.", add_help=True)
parser.add_argument("-p", "--project-name", help="Project name to run workflow on", type=str)
parser.add_argument("-t", "--task-id", help="Specific Linear task ID to run", type=str)
parser.add_argument(
    "--auto", help="Automatic mode - post questions and exit", action=argparse.BooleanOptionalAction, default=True
)
parser.add_argument(
    "--plan-loop",
    help="Loop between plan and resolve agents instead of posting questions to Linear",
    action=argparse.BooleanOptionalAction,
    default=False,
)
parser.add_argument(
    "--resetpass",
    help="Reset a user's password interactively",
    action="store_true",
)

parser.add_argument(
    "--allowlist",
    help="Allowlist management sub-action: add, remove, list, seed-existing",
    choices=["add", "remove", "list", "seed-existing"],
    default=None,
)
parser.add_argument("--type", help="Allowlist entry type (email or github_username)", default=None)
parser.add_argument("--value", help="Allowlist entry value", default=None)
parser.add_argument("--note", help="Optional note for the allowlist entry", default=None)
parser.add_argument("--dry-run", help="Report seed-existing counts without writing", action="store_true")


async def main(project_name: str, auto_mode: bool = True, plan_loop: bool = False, task_id: str | None = None):
    await init_db()
    await print_heading()

    print_message("Running workflow", style="heading")
    context = await setup_workflow(project_name=project_name, auto_mode=auto_mode, task_id=task_id)
    if not context:
        return

    context.plan_loop = plan_loop

    if not context.linear_task.user_id and DEFAULT_USER_ID:
        context.linear_task.user_id = DEFAULT_USER_ID

    await setup_session_logging(task_id=context.linear_task.id)

    is_success = False
    should_update_linear_status = True
    failure_step = "failed"
    try:
        await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR["states"]["in_progress"])

        if not context.session or not context.session.build_plan:
            if not await run_plan_step(context=context):
                return

        if not context.session:
            print_message("Empty session, exiting.", style="error")
            return

        if not context.session.build_plan:
            print_message("Empty build plan, exiting.", style="error")
            return

        if not context.session.posted_to_linear:
            if await post_comment(task_id=context.linear_task.id, body=context.session.build_plan):
                await mark_session_posted(task_id=context.linear_task.id)

        build_plan = context.session.build_plan
        commit_retries = MAX_BUILD_ATTEMPTS
        while commit_retries:
            await run_build_step(build_plan=build_plan, context=context)

            if await commit_and_push(context=context):
                break

            build_plan = (
                "The previous build attempt produced no staged changes. "
                "You MUST implement the required changes and stage them using `git add`.\n\n"
                f"Original plan:\n{build_plan}"
            )
            commit_retries -= 1
        else:
            raise InfiniteLoopError("Build agent repeatedly produced no changes")

        is_success = True

    except InfiniteLoopError:
        print_message("Infinite loop detected, exiting.", style="error")

    except UserCancelledError:
        print_message("User cancelled, exiting the workflow.", style="error")

    except AutoCancelledError:
        print_message("User cancelled, exiting the workflow.", style="error")
        should_update_linear_status = False
        failure_step = "awaiting_input"

    except ValueError as e:
        print_message(f"Configuration error: {e}", style="error")

    except DemetraError as e:
        print_message(f"Workflow error: {e}", style="error")

    except OSError as e:
        print_message(f"OS Error: {e}", style="error")

    except RuntimeError as e:
        print_message(f"Runtime Error: {e}", style="error")

    finally:
        # Only run cleanup if we successfully created a context (which means worktree was created)
        if context:
            await cleanup_workflow(
                context=context,
                is_success=is_success,
                should_update_linear_status=should_update_linear_status,
                failure_step=failure_step,
            )


async def reset_password_cli() -> int:
    import getpass

    email = input("Email: ").strip()
    password = getpass.getpass("New password: ")

    try:
        await init_db()
        await reset_password(email=email, password=password)
    except AuthError as e:
        print_message(str(e), style="error")
        return 1
    except SQLAlchemyError as e:
        print_message(f"Database error: {e}", style="error")
        return 1
    else:
        print_message("Password reset successfully", style="success")
        return 0


async def _allowlist_add(entry_type: str, value: str, note: str | None) -> int:
    await add_entry(entry_type=entry_type, value=value, note=note, added_by=None)
    print_message("Allowlist entry added", style="success")
    return 0


async def _allowlist_remove(entry_type: str, value: str) -> int:
    if await remove_entry(entry_type=entry_type, value=value):
        print_message("Allowlist entry removed", style="success")
    else:
        print_message("No allowlist entry to remove", style="info")
    return 0


async def _allowlist_list() -> int:
    entries = await list_entries()
    if not entries:
        print_message("No allowlist entries", style="info")
        return 0

    table = Table(title="Allowlist entries")
    for column in ("type", "value", "note", "added_by", "created_at"):
        table.add_column(column)
    for entry in entries:
        table.add_row(
            entry["entry_type"],
            entry["value"],
            entry["note"] or "",
            entry["added_by"] or "",
            entry["created_at"].isoformat(),
        )
    Console(width=200).print(table)
    return 0


async def _allowlist_seed_existing(dry_run: bool) -> int:
    if ALLOWLIST_SEED_FILE:
        try:
            seed_rows = load_seed_file(ALLOWLIST_SEED_FILE)
        except ValueError as e:
            print_message(str(e), style="error")
            return 1
        inserted = 0
        for row in seed_rows:
            try:
                await add_entry(
                    entry_type=row["entry_type"],
                    value=row["value"],
                    note=row.get("note"),
                    added_by=None,
                )
            except AuthError:
                continue
            inserted += 1
        print_message(f"Seeded {inserted} entries from {ALLOWLIST_SEED_FILE}", style="result")
        return 0

    counts = await seed_existing_users(dry_run=dry_run)
    prefix = "(dry-run) " if dry_run else ""
    print_message(
        f"{prefix}seed-existing: {counts['inserted']} inserted, "
        f"{counts['already_present']} already present, {counts['skipped']} skipped",
        style="result",
    )
    return 0


async def allowlist_cli(action: str, entry_type: str | None, value: str | None, note: str | None, dry_run: bool) -> int:
    """Run an allowlist management subcommand.

    Args:
        action: The sub-action: ``add``, ``remove``, ``list`` or ``seed-existing``.
        entry_type: Entry type for add/remove.
        value: Entry value for add/remove.
        note: Optional note for add.
        dry_run: Whether seed-existing should avoid writing.

    Returns:
        int: The process exit code.
    """
    try:
        await init_db()
    except SQLAlchemyError as e:
        print_message(f"Database error: {e}", style="error")
        return 1

    try:
        if action == "add":
            return await _allowlist_add(entry_type=entry_type or "", value=value or "", note=note)
        if action == "remove":
            return await _allowlist_remove(entry_type=entry_type or "", value=value or "")
        if action == "list":
            return await _allowlist_list()
        if action == "seed-existing":
            return await _allowlist_seed_existing(dry_run=dry_run)
        print_message(f"Unknown allowlist action: {action}", style="error")
        return 1
    except AuthError as e:
        print_message(str(e), style="error")
        return 1
    except ValueError as e:
        print_message(str(e), style="error")
        return 1
    except SQLAlchemyError as e:
        print_message(f"Database error: {e}", style="error")
        return 1


if __name__ == "__main__":
    args = parser.parse_args()

    if args.resetpass:
        sys.exit(asyncio.run(reset_password_cli()))
    elif args.allowlist:
        sys.exit(
            asyncio.run(
                allowlist_cli(
                    action=args.allowlist,
                    entry_type=args.type,
                    value=args.value,
                    note=args.note,
                    dry_run=args.dry_run,
                )
            )
        )
    else:
        asyncio.run(
            main(
                project_name=args.project_name,
                auto_mode=args.auto,
                plan_loop=args.plan_loop,
                task_id=args.task_id,
            )
        )
