from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from .model import Assessment, Subject

EMPTY_VALUES = {"", "-", "--"}
SMALL_WORDS = {"a", "as", "o", "os", "e", "de", "da", "das", "do", "dos", "em", "para", "com"}
ROMAN_NUMERALS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII"}
AVERAGE_LABELS ={"MD": "MD", "MFD/Conceito": "MFD"}


def parse_boletim(html: str) -> list[Subject]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="tabela_boletim")
    if table is None:
        return []

    labels = _column_labels(table)
    subjects = []
    for row in table.select("tbody > tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != len(labels):
            continue
        columns = dict(zip(labels, cells))
        subjects.append(_subject_from_row(columns))
    return subjects


def parse_detail(html: str) -> dict[str, Assessment]:
    soup = BeautifulSoup(html, "html.parser")
    assessments: dict[str, Assessment] = {}
    for heading in soup.find_all("h4"):
        table = heading.find_next("table")
        if table is None or "Nota Obtida" not in table.get_text():
            continue
        etapa = _text(heading).split(" - ")[0]
        for row in table.select("tbody > tr"):
            values = [_value(td) for td in row.find_all("td", recursive=False)]
            if len(values) != 6 or values[0] is None:
                continue
            sigla, tipo, descricao, data, peso, nota = values
            assessment = Assessment(etapa, sigla, tipo or "", descricao, data, peso, nota)
            assessments[assessment.key] = assessment
    return assessments


def _column_labels(table: Tag) -> list[str]:
    # Grouped headers like N1/NAF span two sub-columns (N = nota, F = faltas) in the second header row
    header_rows = table.select("thead > tr")
    sub_labels = iter(_text(th) for th in header_rows[1].find_all("th")) if len(header_rows) > 1 else iter(())
    labels = []
    for th in header_rows[0].find_all("th"):
        text = _text(th, separator="")
        span = int(th.get("colspan", 1))
        if span == 1:
            labels.append(text)
            continue
        labels += [f"{text}/{next(sub_labels, i)}" for i in range(span)]
    return labels


def _subject_from_row(columns: dict[str, Tag]) -> Subject:
    detail_link = columns["Opções"].find("a", string=lambda s: s and s.strip() == "Detalhar") if "Opções" in columns else None
    faltas = _value(columns.get("T. Faltas"))
    return Subject(
        diario=_text(columns["Diário"]),
        name=_subject_name(_text(columns["Disciplina"])),
        situacao=_value(columns.get("Situação")),
        faltas=int(faltas) if faltas and faltas.isdigit() else None,
        frequencia=_value(columns.get("% Freq.")),
        averages=_averages(columns),
        detail_url=detail_link["href"] if detail_link else None,
    )


def _averages(columns: dict[str, Tag]) -> dict[str, str | None]:
    averages = {}
    for label, cell in columns.items():
        if label in AVERAGE_LABELS:
            averages[AVERAGE_LABELS[label]] = _value(cell)
        elif label.endswith("/N"):
            averages[label.removesuffix("/N")] = _value(cell)
    return averages


def _subject_name(disciplina: str) -> str:
    # "SUP.11857 (SCLAXD3) - ATIVIDADES DE EXTENSÃO 3" -> "Atividades de Extensão 3"
    raw = disciplina.split(" - ", 1)[-1]
    return " ".join(_title_word(word, i) for i, word in enumerate(raw.lower().split()))


def _title_word(word: str, position: int) -> str:
    if word.upper() in ROMAN_NUMERALS:
        return word.upper()
    if position and word in SMALL_WORDS:
        return word
    return word.capitalize()


def _value(cell: Tag | None) -> str | None:
    if cell is None:
        return None
    text = _text(cell)
    return None if text in EMPTY_VALUES else text


def _text(tag: Tag, separator: str = " ") -> str:
    return " ".join(tag.get_text(separator).split())
