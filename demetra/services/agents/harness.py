import asyncio
from pathlib import Path

from demetra.library.constants import (
    PLAN_HAS_QUESTIONS,
    PLAN_HEADER_STRING,
    PLAN_IS_READY_STRING,
    RESEARCH_HEADER_STRING,
)
from demetra.library.models import SessionEnvironment, TokenUsage
from demetra.services.agents import claude as claude_agents
from demetra.services.agents import opencode as opencode_agents


def _resolve_environment(environment: SessionEnvironment | None) -> SessionEnvironment:
    """Return a usable environment, defaulting to bare settings when None.

    Mirrors the OpenCode wrappers' prior contract, where an omitted
    ``environment`` meant "use the settings defaults, no project/user
    override" instead of requiring every caller (including tests) to
    construct a full :class:`SessionEnvironment`.

    Args:
        environment: The caller-supplied environment, or None.

    Returns:
        SessionEnvironment: The environment to dispatch on.
    """
    if environment is not None:
        return environment
    return SessionEnvironment(project_environment={}, user_environment={})


async def plan_agent(
    target_path: Path,
    task: str,
    session_id: str | None = None,
    task_title: str | None = None,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the plan agent under the active harness.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        session_id: Optional pre-generated session id (Claude only; see
            :func:`new_session_id`).
        task_title: Optional session title (OpenCode only).
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: The resolved env layer selecting the harness and model;
            defaults to bare settings when omitted.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return await claude_agents.claude_plan_agent(
            target_path=target_path,
            task=task,
            session_id=session_id,
            env=env,
            project_id=project_id,
            environment=environment,
        )
    return await opencode_agents.opencode_plan_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        env=env,
        project_id=project_id,
        environment=environment,
    )


async def build_agent(
    target_path: Path,
    task: str,
    session_id: str | None = None,
    task_title: str | None = None,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the build agent under the active harness.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        session_id: Optional session id to continue.
        task_title: Optional session title (OpenCode only).
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: The resolved env layer selecting the harness and model;
            defaults to bare settings when omitted.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return await claude_agents.claude_build_agent(
            target_path=target_path,
            task=task,
            session_id=session_id,
            env=env,
            project_id=project_id,
            environment=environment,
        )
    return await opencode_agents.opencode_build_agent(
        target_path=target_path,
        task=task,
        session_id=session_id,
        task_title=task_title,
        env=env,
        project_id=project_id,
        environment=environment,
    )


async def validate_agent(
    target_path: Path,
    build_plan: str,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the validate agent under the active harness.

    Args:
        target_path: Directory to run the agent in.
        build_plan: The finalized build plan to check coverage against.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: The resolved env layer selecting the harness and model;
            defaults to bare settings when omitted.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return await claude_agents.claude_validate_agent(
            target_path=target_path,
            build_plan=build_plan,
            env=env,
            project_id=project_id,
            environment=environment,
        )
    return await opencode_agents.opencode_validate_agent(
        target_path=target_path,
        build_plan=build_plan,
        env=env,
        project_id=project_id,
        environment=environment,
    )


async def review_agents(
    target_path: Path,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> list[tuple[int, str, str]]:
    """Run every configured review model concurrently under the active harness.

    Args:
        target_path: Directory to run the reviews in.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: The resolved env layer selecting the harness, models and
            (Claude only) per-model effort; defaults to bare settings when
            omitted.

    Returns:
        list[tuple[int, str, str]]: One (exit_code, stdout, stderr) per model.
    """
    environment = _resolve_environment(environment)
    harness_name = environment.agent_harness
    runs = []
    for review_model in environment.review_models:
        if harness_name == "claude":
            runs.append(
                claude_agents.claude_review_agent(
                    target_path=target_path,
                    model=review_model.model,
                    effort=review_model.effort,
                    max_budget_usd=environment.claude_max_budget_usd("review"),
                    env=env,
                    project_id=project_id,
                    environment=environment,
                )
            )
        else:
            runs.append(
                opencode_agents.opencode_review_agent(
                    target_path=target_path,
                    model=review_model.model,
                    env=env,
                    project_id=project_id,
                    environment=environment,
                )
            )
    return list(await asyncio.gather(*runs))


async def review_fixes_agent(
    target_path: Path,
    task: str,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the review-fixes agent under the active harness.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt including unresolved review thread details.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: The resolved env layer selecting the harness and model;
            defaults to bare settings when omitted.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return await claude_agents.claude_review_fixes_agent(
            target_path=target_path,
            task=task,
            env=env,
            project_id=project_id,
            environment=environment,
        )
    return await opencode_agents.opencode_review_fixes_agent(
        target_path=target_path,
        task=task,
        env=env,
        project_id=project_id,
        environment=environment,
    )


async def merge_agent(
    target_path: Path,
    task: str,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the merge agent under the active harness.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: The resolved env layer selecting the harness and model;
            defaults to bare settings when omitted.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return await claude_agents.claude_merge_agent(
            target_path=target_path, task=task, env=env, project_id=project_id, environment=environment
        )
    return await opencode_agents.opencode_merge_agent(
        target_path=target_path, task=task, env=env, project_id=project_id, environment=environment
    )


async def rebase_agent(
    target_path: Path,
    task: str,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the rebase agent under the active harness.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: The resolved env layer selecting the harness and model;
            defaults to bare settings when omitted.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return await claude_agents.claude_rebase_agent(
            target_path=target_path, task=task, env=env, project_id=project_id, environment=environment
        )
    return await opencode_agents.opencode_rebase_agent(
        target_path=target_path, task=task, env=env, project_id=project_id, environment=environment
    )


async def resolve_agent(
    target_path: Path,
    task: str,
    task_title: str | None = None,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the resolve agent under the active harness.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        task_title: Optional session title (OpenCode only).
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: The resolved env layer selecting the harness and model;
            defaults to bare settings when omitted.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return await claude_agents.claude_resolve_agent(
            target_path=target_path,
            task=task,
            env=env,
            project_id=project_id,
            environment=environment,
        )
    return await opencode_agents.opencode_resolve_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        env=env,
        project_id=project_id,
        environment=environment,
    )


async def research_agent(
    target_path: Path,
    task: str,
    task_title: str | None = None,
    env: dict[str, str] | None = None,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Run the research agent under the active harness.

    Args:
        target_path: Directory to run the agent in.
        task: The task prompt for the agent.
        task_title: Optional session title (OpenCode only).
        env: Optional environment overrides for the subprocess.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: The resolved env layer selecting the harness and model;
            defaults to bare settings when omitted.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr of the run.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return await claude_agents.claude_research_agent(
            target_path=target_path,
            task=task,
            env=env,
            project_id=project_id,
            environment=environment,
        )
    return await opencode_agents.opencode_research_agent(
        target_path=target_path,
        task=task,
        task_title=task_title,
        env=env,
        project_id=project_id,
        environment=environment,
    )


def new_session_id(environment: SessionEnvironment | None = None) -> str | None:
    """Return a freshly generated session id when the harness needs one upfront.

    Claude requires a session id before the first run (``--session-id``);
    OpenCode discovers its session id after the run by title, so this returns
    None for OpenCode.

    Args:
        environment: The resolved env layer selecting the harness; defaults
            to bare settings when omitted.

    Returns:
        str | None: A fresh session id for Claude, otherwise None.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return claude_agents.new_claude_session_id()
    return None


async def get_session_id(
    target_path: Path,
    task_title: str,
    pregenerated_session_id: str | None = None,
    env: dict[str, str] | None = None,
    environment: SessionEnvironment | None = None,
) -> str | None:
    """Resolve the session id to persist after a plan run.

    On Claude the session id was generated before the run (see
    :func:`new_session_id`) and is returned as-is; on OpenCode it is looked up
    afterwards by matching the session title.

    Args:
        target_path: Directory the agent ran in.
        task_title: The task title to match OpenCode sessions on.
        pregenerated_session_id: The id generated before the run, for Claude.
        env: Optional environment overrides for the subprocess.
        environment: The resolved env layer selecting the harness; defaults
            to bare settings when omitted.

    Returns:
        str | None: The session id, or None when it could not be resolved.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return pregenerated_session_id
    return await opencode_agents.get_opencode_session_id(target_path=target_path, task_title=task_title, env=env)


async def get_session_tokens(
    target_path: Path,
    session_id: str,
    env: dict[str, str] | None = None,
    environment: SessionEnvironment | None = None,
) -> TokenUsage | None:
    """Read a session's token usage breakdown under the active harness.

    Args:
        target_path: Directory the agent ran in.
        session_id: The session id.
        env: Optional environment overrides for the subprocess (OpenCode only).
        environment: The resolved env layer selecting the harness; defaults
            to bare settings when omitted.

    Returns:
        TokenUsage | None: The token usage, or None when unavailable.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return await claude_agents.get_claude_session_tokens(target_path=target_path, session_id=session_id)
    return await opencode_agents.get_opencode_session_tokens(target_path=target_path, session_id=session_id, env=env)


async def compact_session(
    target_path: Path,
    session_id: str,
    env: dict[str, str] | None = None,
    environment: SessionEnvironment | None = None,
) -> tuple[int, str, str]:
    """Compact a session's context under the active harness, when supported.

    Args:
        target_path: Directory the agent ran in.
        session_id: The session id to compact.
        env: Optional environment overrides for the subprocess (OpenCode only).
        environment: The resolved env layer selecting the harness; defaults
            to bare settings when omitted.

    Returns:
        tuple[int, str, str]: Exit code, stdout and stderr; always ``(0, "",
            "")`` on Claude, which auto-compacts on its own.
    """
    environment = _resolve_environment(environment)
    if environment.agent_harness == "claude":
        return await claude_agents.claude_compact_session(target_path=target_path, session_id=session_id, env=env)
    return await opencode_agents.opencode_compact_session(target_path=target_path, session_id=session_id, env=env)


async def extract_plan(plan_output: str) -> str:
    """Slice the implementation plan section out of a plan agent output.

    Harness-neutral: both agent prompts emit the same ``## Implementation
    Plan`` marker (see ``PLAN_HEADER_STRING``).

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

    Harness-neutral: both agent prompts emit the same ``## Research Report``
    marker (see ``RESEARCH_HEADER_STRING``).

    Args:
        research_output: The raw research agent output.

    Returns:
        str: The extracted report text.
    """
    if (start_index := research_output.find(RESEARCH_HEADER_STRING)) != -1:
        research_output = research_output[start_index:]

    return research_output.strip()
