import json
import logging
import re
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from demetra.library.exceptions import OpenCodeCLIError
from demetra.library.models import SessionEnvironment, SessionExport, SessionHistory, TokenUsage
from demetra.services.llm.prompt import get_prompt
from demetra.services.persistence.database import record_agent_invocation
from demetra.services.runtime.subprocess import run_command, run_command_to_file
from demetra.services.runtime.tui import print_message
from demetra.services.runtime.utils import non_negative_int
from demetra.settings import OPENCODE


logger = logging.getLogger(__name__)

PLAN_HEADER_STRING = "## Implementation Plan"
PLAN_IS_READY_STRING = "Ready to proceed to build."
PLAN_HAS_QUESTIONS = "Please check my questions above."

RESEARCH_HEADER_STRING = "## Research Report"

# opencode 2.x moved `export <id>` under `session export <id>` and removed
# `run --dir`; both are handled by version-aware command construction.
OPENCODE_V2_MAJOR = 2

_VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_CLI_ARGS_PATTERN = re.compile(r"--[a-z][a-z-]+")

_MAJOR_VERSION_CACHE: dict[str, int | None] = {}
_CLI_VERIFIED = False


def reset_opencode_cli_state() -> None:
    """Clear the cached CLI version and the once-per-process smoke-test flag."""
    global _CLI_VERIFIED
    _MAJOR_VERSION_CACHE.clear()
    _CLI_VERIFIED = False


def _parse_major_version(text: str | None) -> int | None:
    """Extract the major version from ``opencode --version`` output."""
    if not text:
        return None
    match = _VERSION_PATTERN.search(text)
    if match is None:
        return None
    return int(match.group(1))


def _serialize_model(model: object) -> str | None:
    """Serialize an export ``info.model`` into the ``opencode run --model`` form.

    opencode 2.x exposes the model as a ``{providerID, id, variant}`` mapping;
    1.x exposes a string. A non-default variant is appended as ``#variant``.
    """
    if isinstance(model, str):
        return model or None
    if not isinstance(model, dict):
        return None
    provider_id = model.get("providerID")
    model_id = model.get("id")
    if not provider_id or not model_id:
        return None
    serialized = f"{provider_id}/{model_id}"
    variant = model.get("variant")
    if variant and variant != "default":
        serialized = f"{serialized}#{variant}"
    return serialized


def _message_role_and_tokens(message: dict) -> tuple[object, object]:
    """Return a message's role and token mapping across opencode shapes.

    1.x nests them under ``msg["info"]``; 2.x drops the wrapper and puts
    ``type``/``tokens`` on the message itself.
    """
    info = message.get("info")
    if isinstance(info, dict):
        return info.get("role"), info.get("tokens")
    return message.get("type"), message.get("tokens")


def _parse_token_usage(tokens: object) -> TokenUsage | None:
    """Build a cumulative :class:`TokenUsage` from an ``info.tokens`` mapping."""
    if not isinstance(tokens, dict):
        return None
    input_tokens = non_negative_int(tokens.get("input"))
    output_tokens = non_negative_int(tokens.get("output"))
    reasoning_tokens = non_negative_int(tokens.get("reasoning"))
    if input_tokens is None or output_tokens is None or reasoning_tokens is None:
        return None

    usage = TokenUsage(input=input_tokens, output=output_tokens, reasoning=reasoning_tokens)
    cache = tokens.get("cache")
    if isinstance(cache, dict):
        cache_read = non_negative_int(cache.get("read"))
        cache_write = non_negative_int(cache.get("write"))
        if cache_read is not None:
            usage.cache_read = cache_read
        if cache_write is not None:
            usage.cache_write = cache_write
    return usage


def _extract_context(messages: object) -> int | None:
    """Return the context window size from the last token-bearing assistant turn.

    The snapshot is the turn's ``input + cache.read``; it is consumed as a
    gauge (never as a delta). Non-assistant entries (``user``, ``idle``,
    ``system``, ``agent-switched``) are ignored.
    """
    if not isinstance(messages, list):
        return None

    latest_input: int | None = None
    latest_cache_read = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        role, tokens = _message_role_and_tokens(message)
        if role != "assistant":
            continue
        usage = _parse_token_usage(tokens)
        if usage is None:
            continue
        if usage.input > 0 or usage.output > 0:
            latest_input = usage.input
            latest_cache_read = usage.cache_read

    if latest_input is None:
        return None
    return latest_input + latest_cache_read


def _extract_ndjson_error(stdout: str) -> str | None:
    """Return the ``error.message`` from a ``--format json`` NDJSON stream.

    opencode 2.x moves agent errors from stderr to a structured stdout event
    under ``--format json``; this recovers a readable message from it.
    """
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(event, dict) or event.get("type") != "error":
            continue
        error = event.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
    return None


def format_agent_error(exit_code: int, stdout: str, stderr: str) -> str:
    """Build a readable agent-failure message from an opencode run's streams.

    Handles both the default format (error on stderr, empty stdout) and the json
    format (structured error event on stdout, empty stderr) so operators and
    Linear comments never receive a raw NDJSON blob or a bare "unknown error".
    """
    stderr_text = (stderr or "").strip()
    if stderr_text:
        return stderr_text

    stdout_text = (stdout or "").strip()
    if stdout_text:
        return _extract_ndjson_error(stdout_text) or stdout_text

    return f"opencode exited with code {exit_code} without output"


async def opencode_plan_agent(
    target_path: Path,
    task: str,
    task_title: str | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the opencode plan agent with plan-output formatting rules.

    Appends instructions to avoid markdown tables and to signal readiness or
    open questions with the terminal markers.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        task_title: Optional session title.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task += (
        f"\nIMPORTANT:"
        f"\n- Do NOT use markdown tables in the implementation plan. Use lists or paragraphs instead."
        f"\n- If you have some question about implementation, just print in the end `{PLAN_HAS_QUESTIONS}`"
        f"\n- If there are no questions, just print in the end `{PLAN_IS_READY_STRING}`"
    )

    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=environment.opencode_plan_model if environment is not None else OPENCODE["plan_model"],
        agent="plan-agent",
        project_id=project_id,
        environment=environment,
    )


async def opencode_build_agent(
    target_path: Path,
    task: str,
    session_id: str | None = None,
    task_title: str | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
    fork: bool = False,
) -> tuple[int, str, str]:
    """Run the opencode build agent, forbidding commits and pushes.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        session_id: Optional session id to continue.
        task_title: Optional session title.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.
        fork: Whether to fork the continued session before running.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task += "\nDO NOT commit or push any changes, just stage them"
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        session_id=session_id,
        task_title=task_title,
        model=environment.opencode_build_model if environment is not None else OPENCODE["build_model"],
        agent="build-agent",
        project_id=project_id,
        environment=environment,
        fork=fork,
    )


async def opencode_review_agent(
    target_path: Path,
    model: str,
    task_title: str | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the opencode review agent with the review prompt.

    Args:
        target_path: Directory to run the agent in.
        model: The model to use for the review.
        task_title: Optional unique session title so each review run's session
            can be attributed (one row per round and model).
        project_id: Optional project id used for OS env opt-in tokens.
        environment: The resolved session environment forwarded to the subprocess,
            including the derived LangSmith tracing vars.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task = await get_prompt(name="review_agent")
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=model,
        agent="review-agent",
        project_id=project_id,
        environment=environment,
    )


async def opencode_validate_agent(
    target_path: Path,
    build_plan: str,
    task_title: str | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the opencode validate agent with the validate prompt and build plan.

    The entire build plan is appended to the validate prompt and delivered via
    stdin, so no plan step is dropped for length.

    Args:
        target_path: Directory to run the agent in.
        build_plan: The finalized build plan to check coverage against.
        task_title: Optional session title.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task = await get_prompt(name="validate_agent")
    task += f"\n\nBuild Plan:\n{build_plan}"
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=environment.opencode_validate_model if environment is not None else OPENCODE["validate_model"],
        agent="validate-agent",
        project_id=project_id,
        environment=environment,
    )


async def opencode_review_fixes_agent(
    target_path: Path,
    task: str,
    task_title: str | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the opencode build-agent with the fix-review-findings skill.

    Feeds unresolved review threads via the task prompt and stages changes only
    (no commit/push), mirroring :func:`opencode_build_agent`.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt including unresolved review thread details.
        task_title: Optional unique session title used to attribute the run.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    task = f"Use the fix-review-findings skill to address all unresolved review findings.\n\n{task}"
    task += "\nDO NOT commit or push any changes, just stage them"
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=environment.opencode_build_model if environment is not None else OPENCODE["build_model"],
        agent="build-agent",
        project_id=project_id,
        environment=environment,
    )


async def opencode_merge_agent(
    target_path: Path,
    task: str,
    task_title: str | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the opencode merge agent to resolve merge conflicts.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        task_title: Optional unique session title used to attribute the run.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=environment.opencode_build_model if environment is not None else OPENCODE["build_model"],
        agent="merge-agent",
        project_id=project_id,
        environment=environment,
    )


async def opencode_rebase_agent(
    target_path: Path,
    task: str,
    task_title: str | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the opencode rebase agent to resolve rebase conflicts.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        task_title: Optional unique session title used to attribute the run.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=environment.opencode_build_model if environment is not None else OPENCODE["build_model"],
        agent="rebase-agent",
        project_id=project_id,
        environment=environment,
    )


async def opencode_resolve_agent(
    target_path: Path,
    task: str,
    task_title: str | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the opencode resolve agent to answer open plan questions.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        task_title: Optional session title.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    return await run_opencode_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        model=environment.opencode_resolve_model if environment is not None else OPENCODE["resolve_model"],
        agent="resolve-agent",
        project_id=project_id,
        environment=environment,
    )


async def opencode_research_agent(
    target_path: Path,
    task: str,
    task_title: str | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the opencode research agent to validate a ticket against wiki and web.

    Loads the research user prompt and appends the task before delegating to
    the ``research-agent``.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        task_title: Optional session title.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer overriding the model.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    prompt = await get_prompt(name="research_agent", task=task)
    return await run_opencode_agent(
        target_path=target_path,
        task=prompt,
        task_title=task_title,
        model=environment.opencode_research_model if environment is not None else OPENCODE["research_model"],
        agent="research-agent",
        project_id=project_id,
        environment=environment,
    )


async def run_opencode_agent(
    target_path: Path,
    task: str,
    model: str,
    agent: str,
    session_id: str | None = None,
    task_title: str | None = None,
    disable_stdio: bool = False,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
    fork: bool = False,
) -> tuple[int, str, str]:
    """Run an opencode agent with the given model, task and session options.

    The task prompt is delivered to the ``opencode run`` message slot via stdin,
    so arbitrarily long prompts (e.g. full build plans) reach the agent intact
    instead of being truncated to fit a command-line argument.

    The working directory is set through the subprocess ``cwd`` rather than
    ``--dir``: opencode 2.x removed the flag (the directory became a root
    positional), while the subprocess cwd is equivalent on both versions.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        model: The model to use.
        agent: The agent name, e.g. ``"plan-agent"``.
        session_id: Optional session id to continue.
        task_title: Optional session title.
        disable_stdio: Whether to suppress live subprocess output.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: Optional resolved env layer forwarding LangSmith tracing
            vars to the subprocess.
        fork: Whether to fork the continued session before running. Requires
            ``session_id``; used once for the build phase so later iterations
            resume the fork instead of re-forking the plan session.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    command = [str(OPENCODE["path"]), "run", "--model", model, "--agent", agent]

    if session_id is not None:
        command.extend(["--session", session_id])
        if fork:
            command.append("--fork")
    if task_title is not None:
        command.extend(["--title", task_title])

    return await run_command(
        command=command,
        target_path=target_path,
        disable_stdio=disable_stdio,
        environment=environment,
        input_text=task,
        project_id=project_id,
    )


async def get_opencode_sessions(
    target_path: Path, environment: SessionEnvironment | None = None
) -> list[dict[str, str]]:
    """List opencode sessions as JSON records.

    Args:
        target_path: Directory to run the opencode CLI in.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        list[dict[str, str]]: The parsed session list.
    """
    command = [str(OPENCODE["path"]), "session", "list", "--format", "json"]
    _, result, _ = await run_command(
        command=command, target_path=target_path, disable_stdio=True, environment=environment
    )
    return json.loads(result)


async def get_opencode_session_id(
    target_path: Path,
    task_title: str,
    environment: SessionEnvironment | None = None,
    *,
    include_forks: bool = False,
) -> str | None:
    """Find the opencode session id for a task title, preferring matching directory.

    Sessions are matched by title; among matches the newest one for the same
    working directory wins, with the newest overall session as a fallback. When
    ``include_forks`` is set, sessions whose title carries the ``(fork #N)``
    suffix opencode appends on ``--fork`` also match the base title, which is the
    only way to locate a fork in default output format.

    Args:
        target_path: Directory to run the opencode CLI in.
        task_title: The task title to match sessions on.
        environment: The resolved session environment forwarded to the subprocess.
        include_forks: Whether ``"<title> (fork #N)"`` sessions match too.

    Returns:
        str | None: The session id, or None when no matching session exists.
    """
    sessions = await get_opencode_sessions(target_path=target_path, environment=environment)

    def matches_title(session: dict[str, str]) -> bool:
        title = session.get("title", "")
        if title == task_title:
            return True
        return include_forks and title.startswith(f"{task_title} (fork")

    filtered_sessions = [session for session in sessions if matches_title(session)]
    if not filtered_sessions:
        print_message("Session not found", style="info")

    fallback_session_id = None
    target_directory = str(target_path).rstrip("/")
    for session in sorted(filtered_sessions, key=lambda x: x["updated"], reverse=True):
        if not fallback_session_id:
            fallback_session_id = session["id"]

        session_directory = session.get("directory", "").rstrip("/")
        if session_directory == target_directory:
            return session["id"]

    if fallback_session_id:
        print_message("Worktree mistmatch, using fallback session id", style="error")
    return fallback_session_id


async def capture_agent_session(
    *,
    task_id: str | None,
    step: str,
    target_path: Path,
    task_title: str | None = None,
    session_id: str | None = None,
    forked: bool = False,
    is_primary: bool = False,
    environment: SessionEnvironment | None = None,
) -> SessionHistory | None:
    """Attribute one agent invocation's exact token delta to a workflow step.

    Resolves the session id the run used or created (a continued session keeps
    its id; a fresh or forked run is located by its unique title), reads the
    session's cumulative usage through a file-backed export, and records the
    invocation delta. Failures are logged and swallowed so token accounting can
    never fail a workflow.

    Args:
        task_id: The Linear task identifier, or None to skip recording.
        step: The workflow step name.
        target_path: Directory the agent ran in.
        task_title: The unique session title used for the run.
        session_id: The continued session id, when one was passed to the run.
        forked: Whether the run forked ``session_id`` (so the session id changed).
        is_primary: Whether the resolved session becomes the task's primary.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        SessionHistory | None: The persisted invocation record, or None when
            no session could be attributed or persistence failed.
    """
    if not task_id:
        return None

    resolved = session_id
    if resolved is None or forked:
        if not task_title:
            return None
        resolved = await get_opencode_session_id(
            target_path=target_path,
            task_title=task_title,
            environment=environment,
            include_forks=forked,
        )
    if not resolved:
        return None

    export = await get_opencode_session_export(target_path=target_path, session_id=resolved, environment=environment)
    try:
        return await record_agent_invocation(
            task_id=task_id,
            step=step,
            session_id=resolved,
            usage=export.tokens if export is not None else None,
            agent=export.agent if export is not None else None,
            model=export.model if export is not None else None,
            cost=export.cost if export is not None else None,
            outcome=export.outcome if export is not None else None,
            fork_of=session_id if forked else None,
            is_primary=is_primary,
        )
    except (SQLAlchemyError, OSError):
        logger.exception("Failed to record agent invocation for %s (%s)", task_id, step)
        return None


async def get_opencode_major_version(target_path: Path, environment: SessionEnvironment | None = None) -> int | None:
    """Return the major version of the configured opencode CLI, cached per path.

    Args:
        target_path: Directory to run the version probe in.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        int | None: The major version (e.g. ``1`` or ``2``), or None when the
            version cannot be determined.
    """
    path = str(OPENCODE["path"])
    if path in _MAJOR_VERSION_CACHE:
        return _MAJOR_VERSION_CACHE[path]

    exit_code, stdout, stderr = await run_command(
        command=[path, "--version"], target_path=target_path, disable_stdio=True, environment=environment
    )
    major = _parse_major_version(stdout) if exit_code == 0 else None
    if major is None:
        major = _parse_major_version(stderr)

    _MAJOR_VERSION_CACHE[path] = major
    return major


def _export_command(major: int, session_id: str) -> list[str]:
    """Build the version-appropriate ``export`` command for a session."""
    if major >= OPENCODE_V2_MAJOR:
        return [str(OPENCODE["path"]), "session", "export", session_id]
    return [str(OPENCODE["path"]), "export", session_id]


async def get_opencode_session_export(
    target_path: Path, session_id: str, environment: SessionEnvironment | None = None
) -> SessionExport | None:
    """Read a session's cumulative usage and attribution via a file-backed export.

    The export is written to a temp file (never a pipe: ``session export``
    truncates to a 64KB multiple when stdout is a pipe) and parsed once. When
    the CLI major version is unknown both the 1.x and 2.x command forms are
    attempted so a failed version probe cannot silently disable accounting. A
    failed export is logged at error level so a broken CLI is distinguishable
    from a session with no tokens.

    Args:
        target_path: Directory to run the opencode CLI in.
        session_id: The opencode session id.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        SessionExport | None: The cumulative usage, or None when the export
            fails or the JSON shape is unusable.
    """
    major = await get_opencode_major_version(target_path=target_path, environment=environment)
    attempts = (
        [_export_command(major, session_id)]
        if major is not None
        else [
            _export_command(OPENCODE_V2_MAJOR, session_id),
            _export_command(1, session_id),
        ]
    )

    for command in attempts:
        exit_code, result, stderr = await run_command_to_file(
            command=command, target_path=target_path, disable_stdio=True, environment=environment
        )
        if exit_code != 0:
            logger.error(
                "opencode export failed (exit %s) for session %s via %s: %s",
                exit_code,
                session_id,
                " ".join(command[1:]),
                format_agent_error(exit_code=exit_code, stdout=result, stderr=stderr),
            )
            continue

        try:
            data = json.loads(result)
        except (json.JSONDecodeError, ValueError):
            logger.error("opencode export returned malformed JSON for session %s", session_id)
            continue

        export = _build_session_export(data)
        if export is not None:
            return export
        logger.error("opencode export returned an unusable shape for session %s", session_id)

    return None


def _build_session_export(data: object) -> SessionExport | None:
    """Build a :class:`SessionExport` from a parsed opencode export payload."""
    if not isinstance(data, dict):
        return None

    info = data.get("info")
    if not isinstance(info, dict):
        return None

    usage = _parse_token_usage(info.get("tokens"))
    if usage is None:
        return None

    usage.context = _extract_context(data.get("messages"))

    cost = info.get("cost")
    outcome = info.get("outcome")
    agent = info.get("agent")
    return SessionExport(
        tokens=usage,
        agent=str(agent) if isinstance(agent, str) and agent else None,
        model=_serialize_model(info.get("model")),
        cost=float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None,
        outcome=str(outcome) if isinstance(outcome, str) and outcome else None,
    )


async def get_opencode_session_tokens(
    target_path: Path, session_id: str, environment: SessionEnvironment | None = None
) -> TokenUsage | None:
    """Read the cumulative token usage of an opencode session via export.

    Args:
        target_path: Directory to run the opencode CLI in.
        session_id: The opencode session id.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        TokenUsage | None: The cumulative usage (with the context snapshot), or
            None when the export fails or the JSON is malformed.
    """
    export = await get_opencode_session_export(target_path=target_path, session_id=session_id, environment=environment)
    return export.tokens if export is not None else None


async def get_opencode_session_length(
    target_path: Path, session_id: str, environment: SessionEnvironment | None = None
) -> int | None:
    """Return the total token count used by an opencode session.

    Args:
        target_path: Directory to run the opencode CLI in.
        session_id: The opencode session id.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        int | None: The total token count, or None when unavailable.
    """
    usage = await get_opencode_session_tokens(target_path=target_path, session_id=session_id, environment=environment)
    return usage.total if usage is not None else None


async def opencode_supports_compaction(target_path: Path, environment: SessionEnvironment | None = None) -> bool:
    """Return whether the CLI exposes a command to compact a session.

    opencode 1.x runs slash commands through ``run --command``. opencode 2.x
    removed ``--command`` from ``run``, so there is no CLI compaction path and
    the fork-once build design becomes the only context bound.
    """
    major = await get_opencode_major_version(target_path=target_path, environment=environment)
    return major is None or major < OPENCODE_V2_MAJOR


async def opencode_compact_session(
    target_path: Path, session_id: str, environment: SessionEnvironment | None = None
) -> tuple[int, str, str]:
    """Compact an opencode session through ``run --command compact``.

    ``/compact`` must be invoked as a command, not as the message positional:
    passed as a message it is delivered to the agent as a prompt, which burns a
    full-context turn without shrinking anything. On opencode 2.x there is no
    ``run --command`` and this returns a non-zero exit arbitrarily so callers
    surface the unsupported path instead of a silent no-op.

    Args:
        target_path: Directory to run the opencode CLI in.
        session_id: The opencode session id to compact.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    if not await opencode_supports_compaction(target_path=target_path, environment=environment):
        return (1, "", "compaction is not supported by this opencode version (no 'run --command')")

    command = [str(OPENCODE["path"]), "run", "--session", session_id, "--command", "compact"]
    return await run_command(command=command, target_path=target_path, disable_stdio=False, environment=environment)


async def verify_opencode_cli(target_path: Path, environment: SessionEnvironment | None = None) -> str:
    """Assert once per process that the opencode CLI matches Demetra's assumptions.

    Logs the resolved version and verifies that ``run`` still accepts every flag
    Demetra passes and that the export subcommand exists, so the next silent CLI
    break fails at deploy time rather than during token accounting.

    Args:
        target_path: Directory to run the CLI probes in.
        environment: The resolved session environment forwarded to the subprocess.

    Returns:
        str: The version string reported by ``opencode --version``.

    Raises:
        OpenCodeCLIError: When ``--version``, ``run --help`` or the export
            subcommand is missing or malformed.
    """
    global _CLI_VERIFIED
    if _CLI_VERIFIED:
        return ""

    path = str(OPENCODE["path"])
    exit_code, stdout, stderr = await run_command(
        command=[path, "--version"], target_path=target_path, disable_stdio=True, environment=environment
    )
    version = (stdout or stderr).strip()
    if exit_code != 0 or not version:
        raise OpenCodeCLIError(f"opencode --version failed (exit {exit_code}): {stderr.strip() or 'no output'}")
    print_message(f"opencode version: {version}", style="info")

    major = _parse_major_version(version)
    run_exit, run_help, run_stderr = await run_command(
        command=[path, "run", "--help"], target_path=target_path, disable_stdio=True, environment=environment
    )
    if run_exit != 0:
        raise OpenCodeCLIError(f"opencode run --help failed (exit {run_exit}): {run_stderr.strip() or 'no output'}")

    supported_flags = set(_CLI_ARGS_PATTERN.findall(run_help))
    required_flags = {"--model", "--agent", "--session", "--fork", "--title"}
    missing = sorted(flag for flag in required_flags if flag not in supported_flags)
    if missing:
        raise OpenCodeCLIError(f"opencode run is missing flags Demetra passes: {', '.join(missing)}")

    if major is not None and major >= OPENCODE_V2_MAJOR:
        export_probe = [path, "session", "export", "--help"]
    else:
        export_probe = [path, "export", "--help"]
    export_exit, _, _ = await run_command(
        command=export_probe, target_path=target_path, disable_stdio=True, environment=environment
    )
    if export_exit != 0:
        raise OpenCodeCLIError(f"opencode export is unavailable (exit {export_exit})")

    _MAJOR_VERSION_CACHE[path] = major
    _CLI_VERIFIED = True
    return version


async def extract_plan(plan_output: str) -> str:
    """Slice the implementation plan section out of a plan agent output.

    Trims leading text before the plan header and strips any trailing
    readiness or question marker.

    Args:
        plan_output: The raw plan agent output.

    Returns:
        str: The extracted plan text.
    """
    if (start_index := plan_output.find(PLAN_HEADER_STRING)) != -1:
        plan_output = plan_output[start_index:]

    for end_string in (PLAN_IS_READY_STRING, PLAN_HAS_QUESTIONS):
        if (end_index := plan_output.find(end_string)) != -1:
            plan_output = plan_output[:end_index]
            break

    return plan_output.strip()


async def extract_research_report(research_output: str) -> str:
    """Slice the research report section out of a research agent output.

    Trims leading text before the research header.

    Args:
        research_output: The raw research agent output.

    Returns:
        str: The extracted report text.
    """
    if (start_index := research_output.find(RESEARCH_HEADER_STRING)) != -1:
        research_output = research_output[start_index:]

    return research_output.strip()
