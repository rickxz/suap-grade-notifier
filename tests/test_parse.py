from pathlib import Path

import pytest

from suap_notifier.parse import LayoutChanged, parse_boletim, parse_detail

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


def test_boletim_layout_from_2026_10_reads_the_same_fields():
    [estrutura] = parse_boletim((FIXTURES / "boletim_2026_10.html").read_text(encoding="utf-8"))

    assert estrutura.diario == "111113"
    assert estrutura.name == "Estrutura de Dados"
    assert estrutura.situacao == "Cursando"
    assert estrutura.faltas == 8
    assert estrutura.frequencia == "80,0%"
    assert estrutura.averages == {"N1": "6,40", "MD": "6,40", "NAF": None, "MFD": None}
    assert estrutura.detail_url == "/edu/detalhar_matricula_diario_boletim/100000/2000003/"


def test_both_layouts_use_the_same_average_keys():
    old = parse_boletim((FIXTURES / "boletim.html").read_text(encoding="utf-8"))[0]
    new = parse_boletim((FIXTURES / "boletim_2026_10.html").read_text(encoding="utf-8"))[0]

    assert old.averages.keys() == new.averages.keys()


def test_table_without_subject_columns_is_a_layout_change():
    html = '<table id="tabela_boletim"><thead><tr><th>Componente</th></tr></thead><tbody><tr><td>X</td></tr></tbody></table>'

    with pytest.raises(LayoutChanged):
        parse_boletim(html)


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
