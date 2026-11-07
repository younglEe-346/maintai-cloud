"""Tableau de bord Streamlit : la page se charge sans erreur (test sans navigateur)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app_frontend.py")


def test_page_de_connexion_sans_erreur():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Se connecter", "Inscrire mon usine"]
    assert len(at.text_input) >= 2
