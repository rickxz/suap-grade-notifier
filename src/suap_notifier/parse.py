from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup, Tag

from .model import Assessment, Subject

EMPTY_VALUES = {"", "-", "--"}
SMALL_WORDS = {"a", "as", "o", "os", "e", "de", "da", "das", "do", "dos", "em", "para", "com"}
ROMAN_NUMERALS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII"}
# Labels are compared accent-free and uppercased; SUAP has renamed these columns before (2026-10)
FALTAS_LABELS = ("T. FALTAS", "TOTAL DE FALTAS")
FIXED_AVERAGES = {"MD": "MD", "MEDIA": "MD", "NAF": "NAF", "NAF/N": "NAF", "MFD/CONCEITO": "MFD"}
ETAPA_AVERAGE = re.compile(r"(?:N|ETAPA )(\d)/(?:N|NOTA)")
COURSE_CODE = re.compile(r"[A-Z]+\.\d+")
CLASS_CODE = re.compile(r"\([A-Z0-9]+\)")


class LayoutChanged(Exception):
    pass


def parse_boletim(html: str) -> list[Subject] | None:
    """Returns None when there is no boletim table (e.g. maintenance page).

    Raises LayoutChanged when the table exists but lacks the columns needed to identify subjects.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="tabela_boletim")
    if table is None:
        return None

    labels = [_normalize(label) for label in _column_labels(table)]
    missing = {"DIARIO", "DISCIPLINA"} - set(labels)
    if missing:
        raise LayoutChanged(f"boletim columns {sorted(missing)} not found in {labels}")
    subjects = []
    for row in table.select("tbody > tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != len(labels):
            continue
        columns = dict(zip(labels, cells))
        subjects.append(_subject_from_row(columns))
    return subjects


def parse_detail(html: str) -> dict[str, Assessment] | None:
    """Returns None when the page lacks the "Detalhamento das Notas" section."""
    soup = BeautifulSoup(html, "html.parser")
    if soup.find("h3", string=lambda s: s and "Detalhamento das Notas" in s) is None:
        return None
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
    options = columns.get("OPCOES")
    detail_link = options.find("a", string=lambda s: s and s.strip() == "Detalhar") if options else None
    faltas = _value(next((columns[label] for label in FALTAS_LABELS if label in columns), None))
    faltas_count = re.match(r"\d+", faltas) if faltas else None
    return Subject(
        diario=_text(columns["DIARIO"]),
        name=_subject_name(_text(columns["DISCIPLINA"])),
        situacao=_value(columns.get("SITUACAO")),
        faltas=int(faltas_count.group()) if faltas_count else None,
        frequencia=_value(columns.get("% FREQ.")),
        averages=_averages(columns),
        detail_url=detail_link["href"] if detail_link else None,
    )


def _averages(columns: dict[str, Tag]) -> dict[str, str | None]:
    # Keys stay N1/MD/NAF/MFD across layouts so saved snapshots keep diffing cleanly
    averages = {}
    for label, cell in columns.items():
        etapa = ETAPA_AVERAGE.fullmatch(label)
        if etapa:
            averages[f"N{etapa.group(1)}"] = _value(cell)
        elif label in FIXED_AVERAGES:
            averages[FIXED_AVERAGES[label]] = _value(cell)
    return averages


def _subject_name(disciplina: str) -> str:
    # Both "SUP.11857 (SCLAXD3) - ATIVIDADES DE EXTENSÃO 3" and "ESTRUTURA DE DADOS (SCLESDD) - SUP.11771"
    parts = re.split(r"\s+-\s+", CLASS_CODE.sub("", disciplina))
    raw = " - ".join(part.strip() for part in parts if part.strip() and not COURSE_CODE.fullmatch(part.strip()))
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


def _normalize(label: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFKD", label) if not unicodedata.combining(c))
    return " ".join(stripped.upper().split())
