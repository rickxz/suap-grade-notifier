from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Assessment:
    etapa: str
    sigla: str
    tipo: str
    descricao: str | None
    data: str | None
    peso: str | None
    nota: str | None

    @property
    def key(self) -> str:
        return f"{self.etapa}|{self.sigla}"


@dataclass
class Subject:
    diario: str
    name: str
    situacao: str | None
    faltas: int | None
    frequencia: str | None
    averages: dict[str, str | None]
    detail_url: str | None = None
    assessments: dict[str, Assessment] = field(default_factory=dict)


@dataclass
class Snapshot:
    subjects: dict[str, Subject]

    def to_dict(self) -> dict:
        return {diario: asdict(subject) for diario, subject in self.subjects.items()}

    @classmethod
    def from_dict(cls, data: dict) -> Snapshot:
        subjects = {}
        for diario, raw in data.items():
            assessments = {key: Assessment(**a) for key, a in raw.pop("assessments", {}).items()}
            subjects[diario] = Subject(**raw, assessments=assessments)
        return cls(subjects)


@dataclass(frozen=True)
class Change:
    kind: str  # "nota" | "media" | "situacao" | "faltas"
    subject: str
    label: str
    before: str | None
    after: str | None

    def describe(self) -> str:
        if self.before is None:
            return f"{self.subject} · {self.label}: {self.after}"
        return f"{self.subject} · {self.label}: {self.before} → {self.after}"


def diff(old: Snapshot, new: Snapshot) -> list[Change]:
    changes: list[Change] = []
    for diario, subject in new.subjects.items():
        previous = old.subjects.get(diario)
        changes += _diff_subject(previous, subject)
    return changes


def _diff_subject(old: Subject | None, new: Subject) -> list[Change]:
    changes: list[Change] = []
    name = new.name

    old_assessments = old.assessments if old else {}
    for key, assessment in new.assessments.items():
        before = old_assessments.get(key)
        before_nota = before.nota if before else None
        if assessment.nota is not None and assessment.nota != before_nota:
            label = f"{assessment.sigla} ({assessment.etapa})"
            changes.append(Change("nota", name, label, before_nota, assessment.nota))

    old_averages = old.averages if old else {}
    for label, value in new.averages.items():
        before = old_averages.get(label)
        if value is not None and value != before:
            changes.append(Change("media", name, label, before, value))

    if old is None:
        return changes

    if new.situacao and new.situacao != old.situacao:
        changes.append(Change("situacao", name, "Situação", old.situacao, new.situacao))

    if new.faltas is not None and old.faltas is not None and new.faltas > old.faltas:
        changes.append(Change("faltas", name, "Faltas", str(old.faltas), str(new.faltas)))

    return changes
