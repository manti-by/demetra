from dataclasses import dataclass, field
from datetime import datetime

from slugify import slugify


@dataclass
class LinearTask:
    id: str
    title: str
    priority: int
    state: str
    description: str
    created_at: datetime
    comments: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        if not self.comments:
            return f"{self.title}\n{self.description}"

        comments = "\n* ".join(self.comments)
        return f"{self.title}\n{self.description}\n**Comments**{comments}"

    @property
    def slug(self) -> str:
        return "opencode/feature/" + slugify(f"{self.id}-{self.title}")
