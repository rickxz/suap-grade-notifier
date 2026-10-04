from pathlib import Path

from suap_notifier.parse import parse_boletim, parse_detail

FIXTURES = Path(__file__).parent / "fixtures"


def test_boletim_reads_every_subject_row():
    subjects = parse_boletim((FIXTURES / "boletim.html").read_text(encoding="utf-8"))

    assert [s.diario for s in subjects] == ["111111", "111112"]


def test_boletim_reads_summary_columns():
    extensao, calculo = parse_boletim((FIXTURES / "boletim.html").read_text(encoding="utf-8"))

    assert extensao.name == "Atividades de Extensão 3"
    assert extensao.situacao == "Aprovado"
    assert extensao.faltas == 12
    assert extensao.frequencia == "90,0%"
    assert extensao.averages == {"N1": "7,70", "MD": "7,70", "NAF": None, "MFD": "7,70"}
    assert extensao.detail_url == "/edu/detalhar_matricula_diario_boletim/100000/2000001/"

    assert calculo.name == "Cálculo II"
    assert calculo.situacao == "Cursando"
    assert calculo.averages == {"N1": None, "MD": None, "NAF": None, "MFD": None}


def test_page_without_boletim_table_is_not_a_boletim():
    assert parse_boletim("<div>Sistema em manutenção</div>") is None


def test_detail_reads_assessments_per_etapa():
    assessments = parse_detail((FIXTURES / "detalhe.html").read_text(encoding="utf-8"))

    assert list(assessments) == ["Etapa 1|A1", "Etapa 1|A2", "Etapa Final|A1"]
    a2 = assessments["Etapa 1|A2"]
    assert (a2.tipo, a2.descricao, a2.data, a2.peso, a2.nota) == ("Atividade", "Execução do projeto", "24/06/2026", "70", "8,00")


def test_detail_maps_dashes_to_none():
    final = parse_detail((FIXTURES / "detalhe.html").read_text(encoding="utf-8"))["Etapa Final|A1"]

    assert final.tipo == "Prova"
    assert (final.descricao, final.data, final.peso, final.nota) == (None, None, None, None)


def test_page_without_detalhamento_is_not_a_detail_page():
    assert parse_detail("<h2>Sistema em manutenção</h2>") is None


def test_detail_page_without_assessments_is_empty():
    assert parse_detail("<h3>Detalhamento das Notas</h3><div></div>") == {}
