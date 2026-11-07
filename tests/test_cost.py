from app.ml.cost import best_threshold

Y = [1, 0, 1, 0, 0, 0]
P = [0.9, 0.8, 0.3, 0.2, 0.2, 0.1]


def test_ratio_eleve_on_alerte_large():
    r = best_threshold(Y, P, cost_ratio=50)
    assert (r["fn"], r["fp"], r["cost"]) == (0, 1, 1.0)
    assert 0.2 < r["threshold"] <= 0.3


def test_ratio_faible_on_alerte_peu():
    r = best_threshold(Y, P, cost_ratio=0.5)
    assert (r["tp"], r["fp"], r["cost"]) == (1, 0, 0.5)


def test_ne_jamais_alerter_si_c_est_le_moins_cher():
    r = best_threshold([1, 0, 0], [0.1, 0.9, 0.8], cost_ratio=1)
    assert r["tp"] == 0 and r["fp"] == 0
