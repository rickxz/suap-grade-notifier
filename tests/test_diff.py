import copy

from suap_notifier.model import Assessment, Snapshot, Subject, diff


def assessment(sigla, nota, etapa="Etapa 1"):
    return Assessment(etapa, sigla, "Prova", None, None, None, nota)


def subject(diario="1", faltas=4, situacao="Cursando", averages=None, assessments=()):
    return Subject(
        diario=diario,
        name="Cálculo II",
        situacao=situacao,
        faltas=faltas,
        frequencia="90,0%",
        averages=averages or {"N1": None, "MD": None},
        assessments={a.key: a for a in assessments},
    )


def snapshot(*subjects):
    return Snapshot({s.diario: s for s in subjects})


def test_identical_snapshots_have_no_changes():
    old = snapshot(subject(assessments=[assessment("A1", "8,00")]))

    assert diff(old, copy.deepcopy(old)) == []


def test_new_grade_is_reported():
    old = snapshot(subject(assessments=[assessment("A1", None)]))
    new = snapshot(subject(assessments=[assessment("A1", "8,00")]))

    [change] = diff(old, new)

    assert (change.kind, change.label, change.before, change.after) == ("nota", "A1 (Etapa 1)", None, "8,00")
    assert change.describe() == "Cálculo II · A1 (Etapa 1): 8,00"


def test_changed_grade_shows_before_and_after():
    old = snapshot(subject(assessments=[assessment("A1", "6,00")]))
    new = snapshot(subject(assessments=[assessment("A1", "7,50")]))

    [change] = diff(old, new)

    assert change.describe() == "Cálculo II · A1 (Etapa 1): 6,00 → 7,50"


def test_assessment_inserted_in_the_middle_only_reports_itself():
    # The 2022 version compared by position, so an insertion shifted every later grade
    old = snapshot(subject(assessments=[assessment("A1", "8,00"), assessment("A3", "9,00")]))
    new = snapshot(subject(assessments=[assessment("A1", "8,00"), assessment("A2", "7,00"), assessment("A3", "9,00")]))

    [change] = diff(old, new)

    assert change.label == "A2 (Etapa 1)"


def test_same_sigla_in_different_etapas_is_tracked_separately():
    old = snapshot(subject(assessments=[assessment("A1", "8,00", "Etapa 1"), assessment("A1", None, "Etapa Final")]))
    new = snapshot(subject(assessments=[assessment("A1", "8,00", "Etapa 1"), assessment("A1", "6,00", "Etapa Final")]))

    [change] = diff(old, new)

    assert change.label == "A1 (Etapa Final)"


def test_average_change_is_reported():
    old = snapshot(subject(averages={"N1": None, "MD": None}))
    new = snapshot(subject(averages={"N1": "8,60", "MD": None}))

    [change] = diff(old, new)

    assert (change.kind, change.label, change.after) == ("media", "N1", "8,60")


def test_situacao_change_is_reported():
    old = snapshot(subject(situacao="Cursando"))
    new = snapshot(subject(situacao="Aprovado"))

    [change] = diff(old, new)

    assert change.describe() == "Cálculo II · Situação: Cursando → Aprovado"


def test_only_increasing_faltas_are_reported():
    assert [c.after for c in diff(snapshot(subject(faltas=4)), snapshot(subject(faltas=6)))] == ["6"]
    assert diff(snapshot(subject(faltas=6)), snapshot(subject(faltas=4))) == []


def test_new_subject_reports_only_existing_grades():
    old = snapshot(subject(diario="1"))
    new = snapshot(
        subject(diario="1"),
        subject(diario="2", assessments=[assessment("A1", "9,00"), assessment("A2", None)]),
    )

    [change] = diff(old, new)

    assert change.label == "A1 (Etapa 1)"


def test_removed_subject_and_cleared_grade_are_ignored():
    old = snapshot(subject(diario="1", assessments=[assessment("A1", "8,00")]), subject(diario="2"))
    new = snapshot(subject(diario="1", assessments=[assessment("A1", None)]))

    assert diff(old, new) == []


def test_snapshot_round_trips_through_dict():
    original = snapshot(subject(assessments=[assessment("A1", "8,00")]))

    assert Snapshot.from_dict(copy.deepcopy(original.to_dict())) == original
