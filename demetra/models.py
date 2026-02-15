from dataclasses import dataclass, field

from slugify import slugify


@dataclass
class LinearIssue:
    id: str
    identifier: str
    title: str
    description: str
    priority: str
    created_at: str
    branch_name: str
    comments: list[str] = field(default_factory=list)

    @property
    def session_id(self) -> str:
        return f"ses_{self.id}"

    @property
    def text(self) -> str:
        if self.comments:
            return f"{self.title}\n({self.description})\n\nComments:\n{'\n'.join(self.comments)}"
        return f"{self.title}\n({self.description})"

    @property
    def slug(self) -> str:
        return slugify(f"{self.identifier}-{self.title}")


@dataclass
class Session:
    ticket_id: str
    session_id: str
    created_at: str
    updated_at: str
