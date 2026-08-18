from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from demetra.library.models import Context, LinearTask, Project, Session
from demetra.services import wiki as service


def make_linear_task(identifier="MNT-147", title="Wiki processes", labels=None) -> LinearTask:
    resolved_labels = ["Feature", "Backend"] if labels is None else labels
    return LinearTask(
        id=f"issue-{identifier.lower()}",
        identifier=identifier,
        title=title,
        description="Automate wiki maintenance loops.",
        priority=1,
        created_at="2026-08-04T00:00:00Z",
        labels=resolved_labels,
        url=f"https://linear.app/mnt/issue/{identifier}",
    )


def make_context(tmp_path: Path, task: LinearTask | None = None, build_plan: str | None = None) -> Context:
    project = Project(
        id="project-1",
        user_id="user-1",
        linear_project_id=None,
        name="demetra",
        state="active",
        repository_url="https://github.com/manti-by/demetra.git",
        repository_name="demetra",
        repository_owner="manti-by",
        local_path=tmp_path,
        created_at="2026-08-04T00:00:00Z",
        updated_at="2026-08-04T00:00:00Z",
    )
    session = Session(
        task_id=make_linear_task().id,
        build_plan=build_plan or "Implementation plan steps.",
        posted_to_linear=True,
        created_at="2026-08-04T00:00:00Z",
        updated_at="2026-08-04T00:00:00Z",
        session_id="sess-123",
        pr_link="https://github.com/manti-by/demetra/pull/69",
    )
    return Context(
        project=project,
        auto_mode=True,
        linear_task=task or make_linear_task(),
        branch_name="mnt-147-wiki-processes",
        worktree_path=tmp_path,
        session=session,
    )


@pytest.fixture
def wiki_dirs(tmp_path, monkeypatch):
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    index_path = tmp_path / "INDEX.md"
    questions_path = tmp_path / "QUESTIONS.md"
    agents_path = tmp_path / "AGENTS.md"
    monkeypatch.setattr(service, "PAGES_ROOT", pages_dir)
    monkeypatch.setattr(service, "INDEX_PATH", index_path)
    monkeypatch.setattr(service, "QUESTIONS_PATH", questions_path)
    monkeypatch.setattr(service, "AGENTS_PATH", agents_path)
    return {"pages": pages_dir, "index": index_path, "questions": questions_path, "agents": agents_path}


FIXED_DIFF = {
    "files": ["demetra/services/wiki.py", "demetra/settings.py"],
    "numstat": [("demetra/services/wiki.py", "150", "10"), ("demetra/settings.py", "4", "0")],
    "changed_lines": 164,
    "stat_text": "2 files changed, 154 insertions(+), 10 deletions(-)",
}


class TestSessionFilename:
    def test_uses_ticket_key_and_slug(self):
        name = service.session_filename(ticket_identifier="MNT-147", title="Wiki processes")
        assert name == f"{service.today()}-mnt-147-wiki-processes.md"

    def test_normalizes_identifier_and_title(self):
        name = service.session_filename(ticket_identifier=" MNT-148 ", title="Email/Password Auth")
        assert name.endswith("-mnt-148-email-password-auth.md")


class TestParsePageFile:
    def test_valid_frontmatter(self, tmp_path):
        path = tmp_path / "page.md"
        path.write_text(
            "---\ntitle: Test Page\ntype: implementation\nservices: [wiki]\ntickets: [MNT-147]\n---\n\n# Body"
        )
        page = service.parse_page_file(path)
        assert page is not None
        assert page["meta"]["title"] == "Test Page"
        assert page["meta"]["tickets"] == ["MNT-147"]
        assert "# Body" in page["body"]

    def test_no_frontmatter(self, tmp_path):
        path = tmp_path / "plain.md"
        path.write_text("# Just a heading")
        page = service.parse_page_file(path)
        assert page is not None
        assert page["meta"] == {}

    def test_invalid_frontmatter_skipped(self, tmp_path):
        path = tmp_path / "broken.md"
        path.write_text("---\ntitle: [unclosed\n---\n\nBody")
        assert service.parse_page_file(path) is None


class TestExistingPageForTicket:
    def test_finds_page_referencing_ticket(self, wiki_dirs):
        (wiki_dirs["pages"] / "2026-08-04-mnt-147-wiki-processes.md").write_text(
            '---\ntitle: "MNT-147: Wiki processes"\ntickets: [MNT-147]\n---\n\nBody'
        )
        found = service.existing_page_for_ticket(ticket_identifier="MNT-147")
        assert found is not None
        assert found.name == "2026-08-04-mnt-147-wiki-processes.md"

    def test_returns_none_for_unknown_ticket(self, wiki_dirs):
        (wiki_dirs["pages"] / "2026-08-04-mnt-147-wiki-processes.md").write_text(
            "---\ntitle: MNT-147\ntickets: [MNT-147]\n---\n\nBody"
        )
        assert service.existing_page_for_ticket(ticket_identifier="MNT-999") is None

    def test_returns_none_when_pages_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(service, "PAGES_ROOT", tmp_path / "nowhere")
        assert service.existing_page_for_ticket(ticket_identifier="MNT-147") is None


class TestInferServices:
    def test_service_files_mapped_to_names(self):
        assert service.infer_services(["demetra/services/wiki.py", "demetra/settings.py"]) == ["wiki", "settings"]

    def test_other_demetra_modules_use_second_segment(self):
        assert service.infer_services(["demetra/workflows/merge.py"]) == ["workflows"]

    def test_top_level_files_use_first_segment(self):
        assert service.infer_services(["main.py"]) == ["main"]

    def test_deduplicated_and_ordered(self):
        assert service.infer_services(
            ["demetra/services/wiki.py", "demetra/services/groq.py", "demetra/services/openrouter.py"]
        ) == ["groq", "openrouter", "wiki"]


class TestInferTags:
    def test_slugs_labels_and_prepends_wiki(self):
        task = make_linear_task(labels=["Feature", "Backend Hardening"])
        assert service.infer_tags(linear_task=task) == ["wiki", "feature", "backend-hardening"]

    def test_empty_labels_keeps_wiki_tag(self):
        task = make_linear_task(labels=[])
        assert service.infer_tags(linear_task=task) == ["wiki"]


class TestBudgetExceeded:
    def test_under_budget_not_exceeded(self):
        facts = {"files": ["a.py", "b.py"], "changed_lines": 50}
        assert service.budget_exceeded(facts=facts) is False

    def test_too_many_files_exceeded(self, monkeypatch):
        monkeypatch.setattr(service, "WIKI_LLM_BUDGET_FILES", 8)
        facts = {"files": [f"f{i}.py" for i in range(9)], "changed_lines": 1}
        assert service.budget_exceeded(facts=facts) is True

    def test_too_many_lines_exceeded(self, monkeypatch):
        monkeypatch.setattr(service, "WIKI_LLM_BUDGET_LINES", 200)
        facts = {"files": ["a.py"], "changed_lines": 201}
        assert service.budget_exceeded(facts=facts) is True


class TestSessionLogTail:
    def test_returns_last_lines(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "sessions"
        log_dir.mkdir()
        log_path = log_dir / "MNT-147.log"
        log_path.write_text("\n".join(f"line {i}" for i in range(250)) + "\n")
        monkeypatch.setattr(service, "LOG_DIR", tmp_path)

        tail = service.session_log_tail(task_id="MNT-147")

        assert tail.splitlines()[0] == "line 50"
        assert tail.splitlines()[-1] == "line 249"
        assert len(tail.splitlines()) == service.LOG_TAIL_LINES

    def test_short_log_returns_whole_file(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "sessions"
        log_dir.mkdir()
        (log_dir / "MNT-147.log").write_text("only one line\n")
        monkeypatch.setattr(service, "LOG_DIR", tmp_path)

        assert service.session_log_tail(task_id="MNT-147") == "only one line"

    def test_missing_log_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(service, "LOG_DIR", tmp_path)
        assert service.session_log_tail(task_id="MNT-147") == ""

    def test_nested_sessions_dir(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "sessions"
        log_dir.mkdir()
        (log_dir / "MNT-147.log").write_text("hello\nworld\n")
        monkeypatch.setattr(service, "LOG_DIR", tmp_path / "sessions")
        assert service.session_log_tail(task_id="MNT-147") == "hello\nworld"


class TestGitDiffFacts:
    async def test_uses_resolved_default_branch(self, monkeypatch):
        commands = []

        async def fake_run_command(command, target_path, disable_stdio=False, env=None):
            commands.append(command)
            if "symbolic-ref" in command:
                return 0, "origin/main\n", ""
            if "--name-only" in command:
                return 0, "a.py\n", ""
            if "--numstat" in command:
                return 0, "1\t1\ta.py\n", ""
            return 0, "1 file changed\n", ""

        monkeypatch.setattr(service, "run_command", fake_run_command)
        facts = await service.git_diff_facts(target_path=Path("/tmp/repo"), env=None)
        assert facts["files"] == ["a.py"]
        assert any("origin/main..HEAD" in command for command in commands)
        assert not any("master..HEAD" in command for command in commands)

    async def test_numstat_ignores_blank_lines_from_run_command(self, monkeypatch):
        async def fake_run_command(command, target_path, disable_stdio=False, env=None):
            if "--name-only" in command:
                return 0, "a.py\n", ""
            if "--numstat" in command:
                return 0, "1\t1\ta.py\n\n2\t2\tb.py\n", ""
            return 0, "2 files changed\n", ""

        monkeypatch.setattr(service, "run_command", fake_run_command)
        facts = await service.git_diff_facts(target_path=Path("/tmp/repo"), env=None)
        assert facts["files"] == ["a.py"]
        assert facts["numstat"] == [("a.py", "1", "1"), ("b.py", "2", "2")]
        assert facts["changed_lines"] == 6

    async def test_falls_back_to_master_without_origin_head(self, monkeypatch):
        commands = []

        async def fake_run_command(command, target_path, disable_stdio=False, env=None):
            commands.append(command)
            if "symbolic-ref" in command:
                return 1, "", "fatal: not a symbolic ref"
            if "--name-only" in command:
                return 0, "", ""
            if "--numstat" in command:
                return 0, "", ""
            return 0, "", ""

        monkeypatch.setattr(service, "run_command", fake_run_command)
        facts = await service.git_diff_facts(target_path=Path("/tmp/repo"), env=None)
        assert facts["files"] == []
        assert any("origin/master..HEAD" in command for command in commands)

    async def test_errors_are_swallowed(self, monkeypatch):
        async def fake_run_command(command, target_path, disable_stdio=False, env=None):
            raise OSError("git missing")

        monkeypatch.setattr(service, "run_command", fake_run_command)
        facts = await service.git_diff_facts(target_path=Path("/tmp/repo"), env=None)
        assert facts == {"files": [], "numstat": [], "changed_lines": 0, "stat_text": ""}


class TestInsertPagesEntry:
    def test_inserts_into_empty_pages_section(self):
        contents = "# Index\n\n## Pages\n\n## By topic\n"
        entry = "- [New page](pages/2026-08-04-new.md) — New"
        updated = service.insert_pages_entry(contents=contents, entry=entry)
        assert entry in updated
        assert updated.index("## Pages") < updated.index(entry) < updated.index("## By topic")

    def test_inserts_before_existing_bullets(self):
        contents = "# Index\n\n## Pages\n\n- [Old page](pages/2026-08-01-old.md) — Old\n\n## By topic\n"
        entry = "- [New page](pages/2026-08-04-new.md) — New"
        updated = service.insert_pages_entry(contents=contents, entry=entry)
        assert updated.index("New page") < updated.index("Old page")

    def test_creates_section_when_pages_missing(self):
        contents = "# Index\n\n## By topic\n"
        entry = "- [New page](pages/2026-08-04-new.md) — New"
        updated = service.insert_pages_entry(contents=contents, entry=entry)
        assert "## Pages" in updated
        assert entry in updated

    def test_idempotent(self):
        contents = "# Index\n\n## Pages\n\n- [New page](pages/2026-08-04-new.md) — New\n"
        entry = "- [New page](pages/2026-08-04-new.md) — New"
        assert service.insert_pages_entry(contents=contents, entry=entry) == contents


class TestMergePageContent:
    def _page(self, name: str, title: str, date: str) -> str:
        return (
            f'---\ntitle: "{title}"\ndate: {date}\ntype: implementation\nstatus: resolved\n'
            f"services: [wiki]\nbranch: master\ntickets: [MNT-147]\ntags: [wiki]\nrelated: []\n---\n\n"
            f"# {title}\n\n## TL;DR\n\nImplementation session for {title} on branch `master`.\n"
        )

    def test_returns_false_when_survivor_write_fails(self, tmp_path, monkeypatch):
        survivor = tmp_path / "2026-08-04-survivor.md"
        loser = tmp_path / "2026-08-03-survivor.md"
        survivor.write_text(self._page("survivor", "Same page", "2026-08-04"))
        loser.write_text(self._page("loser", "Same page", "2026-08-03"))
        parsed = {
            survivor: service.parse_page_file(survivor),
            loser: service.parse_page_file(loser),
        }

        def boom(path, encoding=None, data=None):
            raise OSError("disk full")

        monkeypatch.setattr(Path, "write_text", boom)
        assert service.merge_page_content(survivor_path=survivor, loser_path=loser, parsed=parsed) is False

    def test_returns_true_when_write_succeeds(self, tmp_path):
        survivor = tmp_path / "2026-08-04-survivor.md"
        loser = tmp_path / "2026-08-03-survivor.md"
        survivor.write_text(self._page("survivor", "Same page", "2026-08-04"))
        loser.write_text(self._page("loser", "Same page", "2026-08-03"))
        parsed = {
            survivor: service.parse_page_file(survivor),
            loser: service.parse_page_file(loser),
        }
        assert service.merge_page_content(survivor_path=survivor, loser_path=loser, parsed=parsed) is True

    async def test_dedup_keeps_loser_when_merge_write_fails(self, tmp_path, wiki_dirs, monkeypatch):
        survivor = wiki_dirs["pages"] / "2026-08-04-dupe.md"
        loser = wiki_dirs["pages"] / "2026-08-03-dupe.md"
        survivor.write_text(self._page("survivor", "Same page", "2026-08-04"))
        loser.write_text(self._page("loser", "Same page", "2026-08-03"))

        def boom(path, encoding=None, data=None):
            raise OSError("disk full")

        monkeypatch.setattr(Path, "write_text", boom)
        merged, deleted = await service.dedup_pages()
        assert merged == 0
        assert deleted == 0
        assert survivor.is_file()
        assert loser.is_file()


class TestSessionLogTailSanitization:
    def test_path_traversal_task_id_does_not_escape_log_dir(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "sessions"
        log_dir.mkdir()
        (log_dir / "safe.log").write_text("expected\n")
        # a file one level above the session dir that must never be read
        (tmp_path / "secret.log").write_text("secret data\n")
        monkeypatch.setattr(service, "LOG_DIR", tmp_path)

        result = service.session_log_tail(task_id="../secret")
        assert "secret data" not in result


class TestCommitRevalidationScoped:
    async def test_commit_restricts_to_wiki_and_agents(self, monkeypatch):
        stats = {
            "pages_merged": 1,
            "pages_deleted": 0,
            "questions_resolved": 0,
            "clusters_rebuilt": 0,
            "agents_drift": [],
            "changed_files": ["AGENTS.md", "wiki/INDEX.md"],
        }
        commit_commands = []

        async def fake_run_command(command, target_path, disable_stdio=False, env=None):
            if command[1] == "add":
                return 0, "", ""
            if command[1:4] == ["diff", "--staged", "--name-only"]:
                return 0, "wiki/INDEX.md\nAGENTS.md", ""
            if command[1] == "commit":
                commit_commands.append(command)
                return 0, "", ""
            return 0, "abc123", ""

        monkeypatch.setattr(service, "run_command", fake_run_command)
        await service.commit_revalidation(stats=stats)
        assert commit_commands
        commit = commit_commands[0]
        assert "--" in commit
        assert commit[commit.index("--") + 1 :] == ["AGENTS.md", "wiki/INDEX.md"]


class TestPatchIndexWithoutTopicSection:
    async def test_regenerates_by_topic_when_missing(self, tmp_path, wiki_dirs):
        wiki_dirs["index"].write_text("# Index\n\n## Pages\n\n- [Old page](pages/2026-08-01-old.md) — Old\n")
        (wiki_dirs["pages"] / "2026-08-01-old.md").write_text(
            '---\ntitle: "Old page"\ndate: 2026-08-01\ntype: implementation\nstatus: resolved\n'
            "services: [auth]\nbranch: master\ntickets: []\ntags: [auth]\nrelated: []\n---\n\n# Old page\n"
        )
        meta = {
            "title": "MNT-147: Wiki processes",
            "date": "2026-08-04",
            "type": "implementation",
            "status": "resolved",
            "session_id": "sess-123",
            "services": ["wiki"],
            "branch": "mnt-147-wiki-processes",
            "tickets": ["MNT-147"],
            "tags": ["wiki", "feature"],
            "related": [],
        }

        await service.patch_index(meta=meta, filename="2026-08-04-mnt-147-wiki-processes.md")

        text = wiki_dirs["index"].read_text()
        assert "## By topic" in text
        assert "### " in text
        assert "[MNT-147: Wiki processes](pages/2026-08-04-mnt-147-wiki-processes.md)" in text


class TestRenderWikiPage:
    def _meta(self) -> dict:
        return {
            "title": "MNT-147: Wiki processes",
            "date": "2026-08-04",
            "type": "implementation",
            "status": "resolved",
            "session_id": "sess-123",
            "services": ["wiki"],
            "branch": "mnt-147-wiki-processes",
            "tickets": ["MNT-147"],
            "tags": ["wiki", "feature"],
            "related": [],
            "linear_url": "https://linear.app/mnt/issue/MNT-147",
        }

    def test_frontmatter_round_trips_through_parser(self, tmp_path):
        body = service.render_wiki_page(meta=self._meta(), facts=FIXED_DIFF)
        path = tmp_path / "page.md"
        path.write_text(body)
        page = service.parse_page_file(path)
        assert page is not None
        assert page["meta"]["title"] == "MNT-147: Wiki processes"
        assert page["meta"]["services"] == ["wiki"]
        assert page["meta"]["tickets"] == ["MNT-147"]
        assert page["meta"]["branch"] == "mnt-147-wiki-processes"

    def test_backslash_in_title_escaped_and_round_trips(self, tmp_path):
        meta = self._meta()
        meta["title"] = "MNT-147: Fix \\path issue"
        body = service.render_wiki_page(meta=meta, facts=FIXED_DIFF)
        assert "title: 'MNT-147: Fix \\path issue'" in body
        path = tmp_path / "page.md"
        path.write_text(body)
        page = service.parse_page_file(path)
        assert page is not None
        assert page["meta"]["title"] == "MNT-147: Fix \\path issue"

    def test_idempotent_render_produces_stable_content(self):
        first = service.render_wiki_page(meta=self._meta(), facts=FIXED_DIFF)
        second = service.render_wiki_page(meta=self._meta(), facts=FIXED_DIFF)
        assert first == second

    def test_polished_summary_replaces_tldr_and_overview(self):
        polished = {"tldr": "Polished TL;DR.", "overview": "Polished overview."}
        body = service.render_wiki_page(meta=self._meta(), facts=FIXED_DIFF, polished_summary=polished)
        assert "Polished TL;DR." in body
        assert "Polished overview." in body
        assert "Changed 2 file(s)" not in body

    def test_changed_files_and_stat_included(self):
        body = service.render_wiki_page(meta=self._meta(), facts=FIXED_DIFF)
        assert "`demetra/services/wiki.py` (150/10)" in body
        assert "154 insertions" in body


class TestWriteSessionWikiPage:
    async def test_writes_page_and_patches_index(self, tmp_path, wiki_dirs, monkeypatch):
        monkeypatch.setattr(service, "git_diff_facts", AsyncMock(return_value=FIXED_DIFF))
        monkeypatch.setattr(service, "today", lambda: "2026-08-04")
        wiki_dirs["index"].write_text(
            "# Demetra Wiki - Index\n\n## Pages\n\n- [Old page](pages/2026-08-01-old.md) — Old\n\n## By topic\n\n### Workflow orchestration & agents (1 page)\n\n- [Old page](pages/2026-08-01-old.md) — Old\n"
        )

        await service.write_session_wiki_page(context=make_context(tmp_path))

        page_path = wiki_dirs["pages"] / "2026-08-04-mnt-147-wiki-processes.md"
        assert page_path.is_file()
        index_text = wiki_dirs["index"].read_text()
        assert "[MNT-147: Wiki processes](pages/2026-08-04-mnt-147-wiki-processes.md)" in index_text
        # newest-first: new page above the old one
        assert index_text.index("2026-08-04-mnt-147") < index_text.index("2026-08-01-old.md")

    async def test_rerun_does_not_duplicate_index_entries(self, tmp_path, wiki_dirs, monkeypatch):
        monkeypatch.setattr(service, "git_diff_facts", AsyncMock(return_value=FIXED_DIFF))
        monkeypatch.setattr(service, "today", lambda: "2026-08-04")
        wiki_dirs["index"].write_text(
            "# Index\n\n## Pages\n\n## By topic\n\n### Workflow orchestration & agents (1 page)\n\n- [x](p.md) — x\n"
        )

        context = make_context(tmp_path)
        await service.write_session_wiki_page(context=context)
        await service.write_session_wiki_page(context=context)

        index_text = wiki_dirs["index"].read_text()
        # one entry in the Pages section and one in the By topic cluster, no duplicates across reruns
        pages_section, _, topic_section = index_text.partition("## By topic")
        assert pages_section.count("[MNT-147: Wiki processes](pages/2026-08-04-mnt-147-wiki-processes.md)") == 1
        assert topic_section.count("[MNT-147: Wiki processes](pages/2026-08-04-mnt-147-wiki-processes.md)") == 1

    async def test_update_keeps_related_clean(self, tmp_path, wiki_dirs, monkeypatch):
        monkeypatch.setattr(service, "git_diff_facts", AsyncMock(return_value=FIXED_DIFF))
        monkeypatch.setattr(service, "today", lambda: "2026-08-04")
        existing = wiki_dirs["pages"] / "2026-08-04-mnt-147-wiki-processes.md"
        existing.write_text(
            '---\ntitle: "MNT-147: Wiki processes"\ntickets: [MNT-147]\nrelated: [2026-08-01-other.md]\n---\n\nOld body'
        )
        wiki_dirs["index"].write_text("# Index\n\n## Pages\n\n## By topic\n")

        await service.write_session_wiki_page(context=make_context(tmp_path))

        page = service.parse_page_file(existing)
        assert page is not None
        assert page["meta"]["related"] == ["2026-08-01-other.md"]
        assert existing.name not in page["meta"]["related"]

    async def test_updates_existing_page_in_place(self, tmp_path, wiki_dirs, monkeypatch):
        monkeypatch.setattr(service, "git_diff_facts", AsyncMock(return_value=FIXED_DIFF))
        monkeypatch.setattr(service, "today", lambda: "2026-08-04")
        existing = wiki_dirs["pages"] / "2026-08-04-mnt-147-wiki-processes.md"
        existing.write_text("---\ntitle: MNT-147: Wiki processes\ntickets: [MNT-147]\n---\n\nOld body")
        wiki_dirs["index"].write_text("# Index\n\n## Pages\n\n## By topic\n")

        await service.write_session_wiki_page(context=make_context(tmp_path))

        assert existing.is_file()
        assert "Changed 2 file(s)" in existing.read_text()
        # no duplicate filename created
        assert len(list(wiki_dirs["pages"].glob("*.md"))) == 1

    async def test_failure_is_swallowed(self, tmp_path, wiki_dirs, monkeypatch):
        async def boom(target_path, env=None):
            raise OSError("git unavailable")

        monkeypatch.setattr(service, "git_diff_facts", boom)
        monkeypatch.setattr(service, "today", lambda: "2026-08-04")

        # must not raise
        await service.write_session_wiki_page(context=make_context(tmp_path))

    async def test_llm_polish_only_above_budget(self, tmp_path, wiki_dirs, monkeypatch):
        monkeypatch.setattr(service, "git_diff_facts", AsyncMock(return_value=FIXED_DIFF))
        monkeypatch.setattr(service, "today", lambda: "2026-08-04")
        monkeypatch.setattr(service, "WIKI_LLM_BUDGET_FILES", 1)
        monkeypatch.setattr(service, "WIKI_LLM_BUDGET_LINES", 10)
        wiki_dirs["index"].write_text("# Index\n\n## Pages\n\n## By topic\n")

        with patch(
            "demetra.services.wiki.summarize_session", new=AsyncMock(return_value={"tldr": "TLDR", "overview": "OV"})
        ) as mock:
            await service.write_session_wiki_page(context=make_context(tmp_path))
            mock.assert_awaited_once()
        page_text = (wiki_dirs["pages"] / "2026-08-04-mnt-147-wiki-processes.md").read_text()
        assert "TLDR" in page_text

    async def test_cheap_run_skips_llm(self, tmp_path, wiki_dirs, monkeypatch):
        monkeypatch.setattr(service, "git_diff_facts", AsyncMock(return_value=FIXED_DIFF))
        monkeypatch.setattr(service, "today", lambda: "2026-08-04")
        wiki_dirs["index"].write_text("# Index\n\n## Pages\n\n## By topic\n")

        with patch("demetra.services.wiki.summarize_session", new=AsyncMock()) as mock:
            await service.write_session_wiki_page(context=make_context(tmp_path))
            mock.assert_not_awaited()


class TestAnswerSweep:
    async def test_moves_answered_question_to_resolved(self, tmp_path, wiki_dirs):
        wiki_dirs["questions"].write_text(
            "# Questions\n\n## Open\n\n### Q-001 — Something\n\n- **Date:** 2026-08-04\n- **Answer:** it was the cache\n\n## Resolved\n\n"
        )
        count = await service.answer_sweep()
        assert count == 1
        text = wiki_dirs["questions"].read_text()
        assert "it was the cache" in text.partition("## Resolved")[2]
        assert "Q-001" not in text.partition("## Open")[2].partition("## Resolved")[0]

    async def test_unanswered_question_stays_open(self, tmp_path, wiki_dirs):
        wiki_dirs["questions"].write_text(
            "# Questions\n\n## Open\n\n### Q-001 — Something\n\n- **Date:** 2026-08-04\n- **Answer:** _(human writes here)_\n\n## Resolved\n\n"
        )
        count = await service.answer_sweep()
        assert count == 0
        assert "Q-001" in wiki_dirs["questions"].read_text().partition("## Open")[2]

    async def test_blank_answer_stays_open(self, tmp_path, wiki_dirs):
        wiki_dirs["questions"].write_text(
            "# Questions\n\n## Open\n\n### Q-001 — Something\n\n- **Date:** 2026-08-04\n- **Answer:**\n\n## Resolved\n\n"
        )
        count = await service.answer_sweep()
        assert count == 0
        assert "Q-001" in wiki_dirs["questions"].read_text().partition("## Open")[2]

    async def test_whitespace_answer_stays_open(self, tmp_path, wiki_dirs):
        wiki_dirs["questions"].write_text(
            "# Questions\n\n## Open\n\n### Q-001 — Something\n\n- **Date:** 2026-08-04\n- **Answer:**   \n\n## Resolved\n\n"
        )
        count = await service.answer_sweep()
        assert count == 0
        assert "Q-001" in wiki_dirs["questions"].read_text().partition("## Open")[2]

    async def test_missing_questions_file_is_noop(self, wiki_dirs):
        assert await service.answer_sweep() == 0


class TestDedupPages:
    def _page(self, name: str, title: str, date: str) -> str:
        return (
            f'---\ntitle: "{title}"\ndate: {date}\ntype: implementation\nstatus: resolved\n'
            f"services: [wiki]\nbranch: master\ntickets: [MNT-147]\ntags: [wiki]\nrelated: []\n---\n\n"
            f"# {title}\n\n## TL;DR\n\nImplementation session for {title} on branch `master`.\n"
        )

    async def test_merges_near_duplicate_pages(self, wiki_dirs):
        (wiki_dirs["pages"] / "2026-08-04-mnt-147-wiki-processes.md").write_text(
            self._page("2026-08-04-mnt-147-wiki-processes.md", "MNT-147: Wiki processes", "2026-08-04")
        )
        (wiki_dirs["pages"] / "2026-08-03-mnt-147-wiki-processes.md").write_text(
            self._page("2026-08-03-mnt-147-wiki-processes.md", "MNT-147: Wiki processes", "2026-08-03")
        )
        merged, deleted = await service.dedup_pages()
        assert merged == 1
        assert deleted == 1
        remaining = list(wiki_dirs["pages"].glob("*.md"))
        assert len(remaining) == 1
        assert remaining[0].name == "2026-08-04-mnt-147-wiki-processes.md"

    async def test_distinct_pages_kept(self, wiki_dirs):
        (wiki_dirs["pages"] / "2026-08-04-mnt-147-wiki-processes.md").write_text(
            self._page("2026-08-04-mnt-147-wiki-processes.md", "MNT-147: Wiki processes", "2026-08-04")
        )
        (wiki_dirs["pages"] / "2026-08-04-database-migration.md").write_text(
            self._page("2026-08-04-database-migration.md", "Database migration", "2026-08-04").replace(
                "MNT-147", "MNT-200"
            )
        )
        merged, deleted = await service.dedup_pages()
        assert merged == 0
        assert deleted == 0
        assert len(list(wiki_dirs["pages"].glob("*.md"))) == 2

    async def test_similar_pages_with_distinct_tickets_kept(self, wiki_dirs):
        def _auth_page(name: str, title: str, ticket: str, date: str) -> str:
            return (
                f'---\ntitle: "{title}"\ndate: {date}\ntype: implementation\nstatus: resolved\n'
                f"services: [auth]\nbranch: master\ntickets: [{ticket}]\ntags: [auth]\nrelated: []\n---\n\n"
                f"# {title}\n\n## TL;DR\n\nImplementation session for {title} tracking the authentication "
                f"registration flow on branch `master`. The change touches the allowlist service, the password "
                f"hashing module, the jwt token store, the login endpoint and the github callback handler before "
                f"being reviewed and merged.\n\n## Details\n\n- Linear ticket {ticket}\n"
                f"- Services: auth, allowlist, passwords\n- Status: resolved\n"
            )

        (wiki_dirs["pages"] / "2026-08-04-mnt-147-auth-session.md").write_text(
            _auth_page("2026-08-04-mnt-147-auth-session.md", "MNT-147: Auth session", "MNT-147", "2026-08-04")
        )
        (wiki_dirs["pages"] / "2026-08-03-mnt-200-auth-session.md").write_text(
            _auth_page("2026-08-03-mnt-200-auth-session.md", "MNT-200: Auth session", "MNT-200", "2026-08-03")
        )
        merged, deleted = await service.dedup_pages()
        assert merged == 0
        assert deleted == 0
        assert len(list(wiki_dirs["pages"].glob("*.md"))) == 2


class TestRegenerateByTopic:
    def _page(self, name: str, title: str, services: list[str], tags: list[str]) -> str:
        return (
            f"---\ntitle: {title}\ndate: 2026-08-04\ntype: implementation\nstatus: resolved\n"
            f"services: [{', '.join(services)}]\nbranch: master\ntickets: [MNT-147]\n"
            f"tags: [{', '.join(tags)}]\nrelated: []\n---\n\n# {title}\n"
        )

    async def test_rebuilds_clusters_from_frontmatter(self, wiki_dirs):
        (wiki_dirs["pages"] / "2026-08-04-mnt-147-wiki-processes.md").write_text(
            self._page("2026-08-04-mnt-147-wiki-processes.md", "Wiki processes", ["wiki"], ["wiki", "mcp"])
        )
        (wiki_dirs["pages"] / "2026-08-04-auth.md").write_text(
            self._page("2026-08-04-auth.md", "Auth", ["auth"], ["auth", "password"])
        )
        wiki_dirs["index"].write_text(
            "# Index\n\n## Pages\n\n- [x](p.md) — x\n\n## By topic\n\n### Old cluster (1 page)\n\n- [x](p.md) — x\n"
        )

        clusters = await service.regenerate_by_topic()
        assert clusters == 2
        text = wiki_dirs["index"].read_text()
        assert "### MCP / integrations" in text
        assert "### Authentication & API security" in text
        assert "Old cluster" not in text


class TestAgentsDrift:
    async def test_flags_missing_anchors(self, wiki_dirs):
        wiki_dirs["agents"].write_text("# AGENTS.md\n\nNo anchors here.\n")
        drift = await service.check_agents_drift()
        assert "demetra/services/wiki.py" in drift
        assert "Groq" in drift
        assert "OpenRouter" in drift

    async def test_anchors_present_pass(self, wiki_dirs):
        wiki_dirs["agents"].write_text(
            "demetra/services/wiki.py\ndemetra/tools/wiki.py\nuv.lock\nLinear GitHub Groq OpenRouter\nnever prefix with\n"
        )
        assert await service.check_agents_drift() == []


class TestRevalidateAndCommit:
    async def test_revalidate_wiki_and_agents_returns_stats(self, tmp_path, wiki_dirs, monkeypatch):
        monkeypatch.setattr(service, "QUESTIONS_PATH", wiki_dirs["questions"])
        monkeypatch.setattr(service, "AGENTS_PATH", wiki_dirs["agents"])
        wiki_dirs["questions"].write_text(
            "# Questions\n\n## Open\n\n### Q-001 — S\n\n- **Answer:** solved\n\n## Resolved\n\n"
        )
        wiki_dirs["agents"].write_text("# AGENTS.md\n")
        wiki_dirs["index"].write_text("# Index\n\n## Pages\n\n## By topic\n")
        (wiki_dirs["pages"] / "2026-08-04-a.md").write_text(
            "---\ntitle: A\ndate: 2026-08-04\ntype: implementation\nstatus: resolved\nservices: [wiki]\ntickets: []\ntags: []\nrelated: []\n---\n\n# A\n"
        )

        stats = await service.revalidate_wiki_and_agents()
        assert stats["questions_resolved"] == 1
        assert isinstance(stats["clusters_rebuilt"], int)
        assert isinstance(stats["agents_drift"], list)

    async def test_commit_revalidation_noop_without_changes(self, monkeypatch):
        stats = {
            "pages_merged": 0,
            "pages_deleted": 0,
            "questions_resolved": 0,
            "clusters_rebuilt": 0,
            "agents_drift": [],
            "changed_files": [],
        }
        monkeypatch.setattr(service, "run_command", AsyncMock())
        assert await service.commit_revalidation(stats=stats) is None

    async def test_commit_revalidation_stages_and_commits(self, monkeypatch):
        stats = {
            "pages_merged": 1,
            "pages_deleted": 0,
            "questions_resolved": 0,
            "clusters_rebuilt": 0,
            "agents_drift": [],
            "changed_files": ["wiki/INDEX.md", "AGENTS.md"],
        }
        add_calls = []
        calls = {
            "add": (0, "", ""),
            "staged": (0, "wiki/INDEX.md\nAGENTS.md", ""),
            "commit": (0, "", ""),
            "rev": (0, "abc123", ""),
        }

        async def fake_run_command(command, target_path, disable_stdio=False, env=None):
            if command[1] == "add":
                add_calls.append(command)
                return calls["add"]
            if command[1:4] == ["diff", "--staged", "--name-only"]:
                return calls["staged"]
            if command[1] == "commit":
                return calls["commit"]
            return calls["rev"]

        monkeypatch.setattr(service, "run_command", fake_run_command)
        sha = await service.commit_revalidation(stats=stats)
        assert sha == "abc123"
        assert add_calls == [[str(service.GIT["path"]), "add", "AGENTS.md", "wiki/INDEX.md"]]

    async def test_commit_revalidation_noop_without_changed_files(self, monkeypatch):
        stats = {
            "pages_merged": 1,
            "pages_deleted": 0,
            "questions_resolved": 0,
            "clusters_rebuilt": 0,
            "agents_drift": [],
            "changed_files": [],
        }
        monkeypatch.setattr(service, "run_command", AsyncMock())
        assert await service.commit_revalidation(stats=stats) is None

    async def test_revalidation_changed_files_parses_rename_and_spaces(self, monkeypatch):
        stdout = "R  wiki/pages/new.md\0wiki/pages/old.md\0?? wiki/pages/has space.md\0M  AGENTS.md\0"
        monkeypatch.setattr(service, "run_command", AsyncMock(return_value=(0, stdout, "")))
        changed = await service.revalidation_changed_files()
        assert changed == {"wiki/pages/new.md", "wiki/pages/has space.md", "AGENTS.md"}

    async def test_revalidation_changed_files_returns_empty_on_failure(self, monkeypatch):
        monkeypatch.setattr(service, "run_command", AsyncMock(return_value=(1, "", "boom")))
        assert await service.revalidation_changed_files() == set()
