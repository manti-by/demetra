from dataclasses import dataclass, field

from slugify import slugify


@dataclass
class LinearIssue:
    id: str
    identifier: str
    title: str
    description: str
    priority: str
    state: str
    created_at: str
    branch_name: str
    comments: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        if self.comments:
            return f"{self.title}\n({self.description})\n\nComments:\n{'\n'.join(self.comments)}"
        return f"{self.title}\n({self.description})"

    @property
    def slug(self) -> str:
        return self.branch_name or slugify(f"{self.identifier}-{self.title}")
