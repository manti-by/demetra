"""
Check how different LLMs + output parsers extract questions from a markdown file.

Usage:
    uv run scripts/check_llm_parsers.py
    uv run scripts/check_llm_parsers.py --text input/text.md --prompt input/prompt.md --models input/models.txt
    uv run scripts/check_llm_parsers.py --output-dir /tmp/results

Input files (all relative to scripts/ unless absolute paths are given):
    input/text.md    - Markdown text to extract questions from
    input/prompt.md  - System prompt for the LLM
    input/models.txt - One Groq model name per line

Output:
    output/<model-name>_<parser>.md  for every (model, parser) combination
"""

import argparse
import asyncio
import re
from pathlib import Path
from typing import Protocol

from langchain_core.output_parsers import BaseOutputParser, CommaSeparatedListOutputParser, JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table


SCRIPTS_DIR = Path(__file__).resolve().parent
console = Console()


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


class NumberedListOutputParser(BaseOutputParser[list[str]]):
    """Parse a numbered list (1. item / 1) item) into a Python list."""

    def parse(self, text: str) -> list[str]:
        text = re.sub(r"(?s)```.*?```", "", text)
        text = re.sub(r"(?s)<think>.*?</think>", "", text)
        lines = text.strip().splitlines()
        results: list[str] = []
        for line in lines:
            if not re.match(r"^\s*\d+[.)]\s", line):
                continue
            cleaned = re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
            if cleaned:
                results.append(cleaned)
        return results

    @property
    def _type(self) -> str:
        return "numbered_list"


class Questions(BaseModel):
    questions: list[str] = Field(description="List of questions extracted from the text")


class ParserSpec(Protocol):
    name: str
    parser: BaseOutputParser
    format_instructions: str


# Registry of (name, parser, extra format instructions for the prompt)
def build_parsers() -> list[tuple[str, BaseOutputParser, str]]:
    csv = CommaSeparatedListOutputParser()
    numbered = NumberedListOutputParser()
    json_parser = JsonOutputParser(pydantic_object=Questions)

    return [
        ("csv", csv, csv.get_format_instructions()),
        ("numbered_list", numbered, "Return a numbered list, one question per line (e.g. 1. Question text)."),
        ("json", json_parser, json_parser.get_format_instructions()),
    ]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


async def run_single(
    model: str,
    system_prompt: str,
    text: str,
    parser_name: str,
    parser: BaseOutputParser,
    format_instructions: str,
) -> list[str]:
    llm = ChatGroq(model=model, temperature=0.1, max_tokens=1024, max_retries=2)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt + "\n\n{format_instructions}"),
            ("human", "Text:\n\n{input_text}"),
        ]
    )

    chain = prompt | llm | parser
    result = await chain.ainvoke({"input_text": text, "format_instructions": format_instructions})

    # JsonOutputParser returns a dict; unwrap the questions list
    if isinstance(result, dict):
        result = result.get("questions", [])

    return result


def questions_to_markdown(model: str, parser_name: str, questions: list[str]) -> str:
    lines = [
        "# Extracted Questions",
        "",
        f"**Model:** `{model}`  ",
        f"**Parser:** `{parser_name}`  ",
        f"**Count:** {len(questions)}",
        "",
        "---",
        "",
    ]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q}")
    return "\n".join(lines) + "\n"


def safe_filename(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", model)


async def process_all(
    text: str,
    system_prompt: str,
    models: list[str],
    output_dir: Path,
) -> None:
    parsers = build_parsers()
    output_dir.mkdir(parents=True, exist_ok=True)

    table = Table(title="LLM x Parser Results", show_lines=True)
    table.add_column("Model", style="cyan")
    table.add_column("Parser", style="magenta")
    table.add_column("Questions", justify="right")
    table.add_column("Output file", style="green")

    tasks: list[tuple[str, str, BaseOutputParser, str]] = [
        (model, name, parser, fmt) for model in models for name, parser, fmt in parsers
    ]

    async def run_task(model: str, parser_name: str, parser: BaseOutputParser, fmt: str):
        try:
            questions = await run_single(model, system_prompt, text, parser_name, parser, fmt)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]ERROR[/red] {model} / {parser_name}: {exc}")
            return model, parser_name, None

        filename = f"{safe_filename(model)}_{parser_name}.md"
        out_path = output_dir / filename
        out_path.write_text(questions_to_markdown(model, parser_name, questions), encoding="utf-8")
        return model, parser_name, (questions, out_path)

    results = await asyncio.gather(*[run_task(m, n, p, f) for m, n, p, f in tasks])

    for model, parser_name, payload in results:
        if payload is None:
            table.add_row(model, parser_name, "[red]ERROR[/red]", "-")
        else:
            questions, out_path = payload
            try:
                display = str(out_path.relative_to(SCRIPTS_DIR))
            except ValueError:
                display = str(out_path)
            table.add_row(model, parser_name, str(len(questions)), display)

    console.print(table)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--text", default="input/text.md", help="Markdown text file (default: input/text.md)")
    p.add_argument("--prompt", default="input/prompt.md", help="System prompt file (default: input/prompt.md)")
    p.add_argument("--models", default="input/models.txt", help="Models list file (default: input/models.txt)")
    p.add_argument("--output-dir", default="output", help="Output directory (default: output/)")
    return p.parse_args()


def resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else SCRIPTS_DIR / p


async def main() -> None:
    args = parse_args()

    text_path = resolve(args.text)
    prompt_path = resolve(args.prompt)
    models_path = resolve(args.models)
    output_dir = resolve(args.output_dir)

    for p in (text_path, prompt_path, models_path):
        if not p.exists():
            console.print(f"[red]File not found:[/red] {p}")
            raise SystemExit(1)

    text = text_path.read_text(encoding="utf-8")
    system_prompt = prompt_path.read_text(encoding="utf-8").strip()
    models = [m.strip() for m in models_path.read_text(encoding="utf-8").splitlines() if m.strip()]

    console.print(f"[bold]Models:[/bold] {', '.join(models)}")
    console.print(f"[bold]Output:[/bold] {output_dir}")
    console.print()

    await process_all(text, system_prompt, models, output_dir)


if __name__ == "__main__":
    asyncio.run(main())
