import pytest

from app.services.hysteresis import Counters, HysteresisConfig, step

CFG = HysteresisConfig(high=0.5, low=0.2, open_k=3, close_k=2)


def run(risks, cfg=CFG, active=False):
    """Rejoue une suite de risques ; renvoie la liste des actions."""
    c, actions = Counters(), []
    for r in risks:
        a = step(c, r, cfg, active)
        actions.append(a)
        if a == "open":
            active = True
        elif a == "close":
            active = False
    return actions


def test_ouvre_apres_k_mesures_hautes_consecutives():
    assert run([0.9, 0.9, 0.9]) == [None, None, "open"]


def test_le_seuil_haut_est_inclus():
    assert run([0.5, 0.5, 0.5])[-1] == "open"


def test_une_mesure_basse_remet_le_compteur_a_zero():
    assert run([0.9, 0.9, 0.1, 0.9, 0.9]) == [None] * 5


def test_la_zone_morte_remet_aussi_le_compteur_a_zero():
    assert run([0.9, 0.9, 0.3, 0.9, 0.9]) == [None] * 5


def test_une_seule_ouverture_tant_que_l_alerte_est_active():
    assert run([0.9] * 6).count("open") == 1


def test_ne_ferme_pas_dans_la_zone_morte():
    # entre 0.2 et 0.5 : l'alerte reste ouverte
    assert run([0.9, 0.9, 0.9, 0.3, 0.3, 0.3, 0.3]).count("close") == 0


def test_ferme_apres_k_mesures_basses_consecutives():
    assert run([0.9, 0.9, 0.9, 0.1, 0.1]) == [None, None, "open", None, "close"]


def test_rouvre_apres_fermeture_si_le_risque_remonte():
    actions = run([0.9] * 3 + [0.1] * 2 + [0.9] * 3)
    assert actions.count("open") == 2 and actions.count("close") == 1


def test_les_compteurs_continuent_d_un_lot_a_l_autre():
    c = Counters()
    assert step(c, 0.9, CFG, False) is None  # lot 1
    assert step(c, 0.9, CFG, False) is None  # lot 2
    assert step(c, 0.9, CFG, False) == "open"  # lot 3


@pytest.mark.parametrize("kwargs", [dict(high=0.5, low=0.5), dict(high=0.5, low=0.6),
                                    dict(high=0.5, low=0.2, open_k=0)])
def test_configuration_invalide_refusee(kwargs):
    with pytest.raises(ValueError):
        HysteresisConfig(**kwargs)
