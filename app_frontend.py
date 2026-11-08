"""Tableau de bord MaintAI Cloud (Streamlit).

Lancement : docker compose up (service "dashboard", http://localhost:8501)
       ou : streamlit run app_frontend.py
Le tableau de bord ne parle qu'à l'API (comme n'importe quel client) : toutes les
règles (rôles, plans, isolation des usines) sont appliquées par l'API.
"""
import os

import pandas as pd
import requests
import streamlit as st

API = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
ROLE_LABELS = {"owner": "Propriétaire", "admin": "Administrateur", "member": "Membre (technicien)"}
STATUS_LABELS = {"OPEN": "🔴 Ouverte", "ACKNOWLEDGED": "🟠 Acquittée", "CLOSED": "🟢 Fermée"}

st.set_page_config(page_title="MaintAI Cloud", page_icon="⚙️", layout="wide")


# ------------------------------------------------------------------ appels à l'API

def call(method: str, path: str, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {st.session_state['token']}"
    try:
        r = requests.request(method, f"{API}{path}", headers=headers, timeout=30, **kwargs)
    except requests.RequestException as e:
        st.error(f"API injoignable ({API}) : {e}")
        st.stop()
    if r.status_code == 401 and st.session_state.get("token"):
        st.session_state.clear()
        st.warning("Session expirée : reconnectez-vous.")
        st.stop()
    return r


def error_of(r: requests.Response) -> str:
    try:
        detail = r.json().get("detail")
    except ValueError:
        return r.text
    if isinstance(detail, list):  # erreurs de validation
        return " ; ".join(f"{'.'.join(map(str, d.get('loc', [])[1:]))} : {d.get('msg')}" for d in detail)
    return str(detail)


def ok_or_error(r: requests.Response, success: str | None = None) -> bool:
    if r.ok:
        if success:
            st.success(success)
        return True
    st.error(error_of(r))
    return False


def pct(x) -> str:
    return "" if x is None else f"{x:.1%}"


# ------------------------------------------------------------------ connexion

def login_page():
    st.title("⚙️ MaintAI Cloud")
    st.caption("Maintenance prédictive pour usines")
    invitation = st.query_params.get("invitation")
    if invitation:
        accept_invitation_form(invitation)
        return
    tab_login, tab_register = st.tabs(["Se connecter", "Inscrire mon usine"])
    with tab_login, st.form("login"):
        email = st.text_input("E-mail")
        password = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Se connecter", type="primary"):
            r = call("POST", "/auth/login", data={"username": email, "password": password})
            if ok_or_error(r):
                st.session_state["token"] = r.json()["access_token"]
                st.rerun()
    with tab_register, st.form("register"):
        org = st.text_input("Nom de l'usine")
        name = st.text_input("Votre nom")
        email = st.text_input("E-mail ")
        password = st.text_input("Mot de passe (8 caractères minimum)", type="password")
        if st.form_submit_button("Créer mon usine (plan Gratuit)", type="primary"):
            r = call("POST", "/auth/register",
                     json={"org_name": org, "full_name": name, "email": email, "password": password})
            if ok_or_error(r):
                st.session_state["token"] = r.json()["access_token"]
                st.rerun()


def accept_invitation_form(token: str):
    r = call("GET", f"/auth/invitations/{token}")
    if not ok_or_error(r):
        return
    info = r.json()
    st.subheader(f"Invitation à rejoindre « {info['organization']} »")
    st.write(f"Compte : **{info['email']}** — rôle : **{ROLE_LABELS[info['role']]}**")
    with st.form("accept"):
        name = st.text_input("Votre nom")
        password = st.text_input("Choisissez un mot de passe (8 caractères minimum)", type="password")
        if st.form_submit_button("Accepter l'invitation", type="primary"):
            r = call("POST", "/auth/accept-invitation",
                     json={"token": token, "full_name": name, "password": password})
            if ok_or_error(r):
                st.session_state["token"] = r.json()["access_token"]
                st.query_params.clear()
                st.rerun()


# ------------------------------------------------------------------ onglets d'une usine

def machines_by_id() -> dict:
    return {m["id"]: m for m in call("GET", "/machines").json()}


def tab_alerts(me: dict):
    @st.fragment(run_every=5)
    def live():
        machines = machines_by_id()
        active = call("GET", "/alerts", params={"status": "active"}).json()
        st.subheader(f"Alertes actives : {len(active)}")
        st.caption("Mise à jour automatique toutes les 5 secondes.")
        if not active:
            st.success("Aucune alerte active : les machines fonctionnent normalement.")
        for a in active:
            name = machines.get(a["machine_id"], {}).get("name", a["machine_id"][:8])
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(f"**{name}** — {STATUS_LABELS[a['status']]} depuis {a['created_at'][:19].replace('T', ' ')}")
                c2.metric("Risque max", pct(a["peak_risk_score"]))
                c3.metric("Mode probable", a["probable_mode"] or "—")
                st.write(a["details"])
                if a["status"] == "ACKNOWLEDGED":
                    st.info(f"Prise en charge par {a['acknowledged_by_name']} : {a['ack_comment'] or '(sans commentaire)'}")
                else:
                    with st.form(f"ack-{a['id']}"):
                        comment = st.text_input("Commentaire", key=f"c-{a['id']}",
                                                placeholder="ex. outil changé, inspection prévue")
                        if st.form_submit_button(f"Acquitter (en tant que {me['full_name']})"):
                            ok_or_error(call("POST", f"/alerts/{a['id']}/acknowledge", json={"comment": comment}),
                                        "Alerte acquittée")
                            st.rerun()
    live()
    with st.expander("Historique des alertes fermées"):
        closed = call("GET", "/alerts", params={"status": "CLOSED", "limit": 200}).json()
        if closed:
            machines = machines_by_id()
            st.dataframe(pd.DataFrame([{
                "machine": machines.get(a["machine_id"], {}).get("name"), "ouverte": a["created_at"][:19],
                "fermée": (a["closed_at"] or "")[:19], "risque max": pct(a["peak_risk_score"]),
                "mode": a["probable_mode"], "acquittée par": a["acknowledged_by_name"]} for a in closed]),
                width="stretch", hide_index=True)
        else:
            st.write("Aucune alerte fermée.")


def tab_machines(is_admin: bool):
    machines = call("GET", "/machines").json()
    if is_admin:
        with st.expander("➕ Déclarer une machine"):
            with st.form("new-machine"):
                name = st.text_input("Nom de la machine", placeholder="ex. Tour CN-04")
                if st.form_submit_button("Déclarer"):
                    r = call("POST", "/machines", json={"name": name})
                    if ok_or_error(r):
                        st.session_state["new_key"] = (r.json()["name"], r.json()["api_key"])
        if st.session_state.get("new_key"):
            name, key = st.session_state["new_key"]
            st.warning(f"Clé d'API de « {name} » — copiez-la maintenant, elle ne sera plus jamais affichée :")
            st.code(key, language="text")
            if st.button("J'ai copié la clé"):
                del st.session_state["new_key"]
                st.rerun()
    if not machines:
        st.info("Aucune machine déclarée.")
        return
    st.dataframe(pd.DataFrame([{
        "machine": m["name"], "statut": m["status"], "clé": m["api_key_prefix"] + "…",
        "clé révoquée": "oui" if m["api_key_revoked_at"] else "non", "déclarée le": m["created_at"][:10]}
        for m in machines]), width="stretch", hide_index=True)

    choice = st.selectbox("Machine", machines, format_func=lambda m: m["name"])
    if choice is None:
        return
    data = call("GET", f"/machines/{choice['id']}/mesures", params={"limit": 300}).json()
    if data:
        # risque et seuil lus directement dans la réponse JSON (une mesure pas encore
        # traitée par le worker n'a pas de prédiction : valeur vide)
        df = pd.DataFrame(data)
        df["risque"] = [d["prediction"]["risk_score"] if d["prediction"] else None for d in data]
        df["seuil"] = [d["prediction"]["threshold"] if d["prediction"] else None for d in data]
        df = df.iloc[::-1]
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        st.markdown("**Risque de panne** (et seuil d'alerte de l'usine)")
        st.line_chart(df.set_index("timestamp")[["risque", "seuil"]])
        st.markdown("**Mesures**")
        sensor = st.radio("Mesure", ["torque", "rotational_speed", "tool_wear", "air_temp", "process_temp"],
                          horizontal=True)
        st.line_chart(df.set_index("timestamp")[[sensor]])
        last = [d for d in data if d["prediction"] and d["prediction"]["decision"]][:20]
        if last:
            st.markdown("**Dernières mesures à risque et leur explication**")
            st.dataframe(pd.DataFrame([{
                "heure": d["timestamp"][:19], "risque": pct(d["prediction"]["risk_score"]),
                "mode probable": d["prediction"]["probable_mode"],
                "explication": d["prediction"]["explanation"],
                "modèle": d["prediction"]["model_version"]} for d in last]),
                width="stretch", hide_index=True)
    else:
        st.info("Pas encore de mesures pour cette machine.")

    if is_admin and choice["status"] == "ACTIVE":
        c1, c2, c3 = st.columns(3)
        if c1.button("🔄 Remplacer la clé", help="L'ancienne clé cesse de fonctionner"):
            r = call("POST", f"/machines/{choice['id']}/api-key/rotate")
            if ok_or_error(r):
                st.session_state["new_key"] = (r.json()["name"], r.json()["api_key"])
                st.rerun()
        if c2.button("⛔ Révoquer la clé", help="Les mesures envoyées avec cette clé seront refusées"):
            ok_or_error(call("POST", f"/machines/{choice['id']}/api-key/revoke"), "Clé révoquée")
        if c3.button("🗄️ Archiver la machine", help="Libère une place du plan ; l'historique est gardé"):
            if ok_or_error(call("DELETE", f"/machines/{choice['id']}"), "Machine archivée"):
                st.rerun()


def tab_settings(is_admin: bool):
    s = call("GET", "/org/settings").json()
    st.subheader("Coût des erreurs et seuil d'alerte")
    st.write("Une **panne manquée** coûte combien de **fausses alertes** ? Plus ce ratio est grand, "
             "plus le seuil baisse : on alerte plus tôt, avec plus de fausses alertes.")
    ratio = st.slider("Ratio de coût (panne manquée / fausse alerte)", 1, 200, int(s["cost_ratio"]),
                      disabled=not is_admin)
    p = call("GET", "/org/settings/preview", params={"cost_ratio": ratio}).json()
    c1, c2, c3 = st.columns(3)
    c1.metric("Seuil d'alerte", pct(p["threshold"]))
    c2.metric("Pannes détectées (attendu)", pct(p["recall"]))
    c3.metric("Fausses alertes (sur 10 000)", p["false_alarms"])
    st.caption(f"Estimé sur les probabilités hors-échantillon du modèle {s['model_version']}.")
    st.subheader("Hystérésis des alertes")
    c1, c2, c3 = st.columns(3)
    open_k = c1.number_input("Mesures hautes d'affilée pour ouvrir", 1, 50, s["alert_open_k"], disabled=not is_admin)
    close_k = c2.number_input("Mesures basses d'affilée pour fermer", 1, 50, s["alert_close_k"], disabled=not is_admin)
    factor = c3.slider("Seuil bas = facteur × seuil haut", 0.05, 0.95, float(s["alert_close_factor"]),
                       disabled=not is_admin)
    if is_admin and st.button("Enregistrer les réglages", type="primary"):
        ok_or_error(call("PUT", "/org/settings", json={"cost_ratio": ratio, "alert_open_k": open_k,
                                                       "alert_close_k": close_k, "alert_close_factor": factor}),
                    "Réglages enregistrés : le nouveau seuil s'applique aux prochaines mesures.")
    if not is_admin:
        st.info("Seuls le propriétaire et les administrateurs peuvent modifier ces réglages.")


def tab_team(me: dict):
    members = call("GET", "/org/members").json()
    st.dataframe(pd.DataFrame([{"nom": m["full_name"], "e-mail": m["email"], "rôle": ROLE_LABELS[m["role"]]}
                               for m in members]), width="stretch", hide_index=True)
    if me["role"] not in ("owner", "admin"):
        return
    st.subheader("Inviter un collègue")
    with st.form("invite"):
        email = st.text_input("E-mail du collègue")
        roles = ["member", "admin"] if me["role"] == "owner" else ["member"]
        role = st.selectbox("Rôle", roles, format_func=lambda r: ROLE_LABELS[r])
        if st.form_submit_button("Envoyer l'invitation"):
            r = call("POST", "/org/invitations", json={"email": email, "role": role})
            ok_or_error(r, "Invitation envoyée par e-mail (en développement : voir http://localhost:8025)")
    pending = [i for i in call("GET", "/org/invitations").json() if not i["accepted_at"] and not i["revoked_at"]]
    if pending:
        st.markdown("**Invitations en attente**")
        for inv in pending:
            c1, c2 = st.columns([4, 1])
            c1.write(f"{inv['email']} — {ROLE_LABELS[inv['role']]} — expire le {inv['expires_at'][:10]}")
            if c2.button("Annuler", key=f"rev-{inv['id']}"):
                call("DELETE", f"/org/invitations/{inv['id']}")
                st.rerun()
    others = [m for m in members if m["role"] != "owner" and m["id"] != me["id"]]
    if others:
        st.subheader("Gérer les membres")
        target = st.selectbox("Membre", others, format_func=lambda m: f"{m['full_name']} ({ROLE_LABELS[m['role']]})")
        if target is None:
            return
        c1, c2 = st.columns(2)
        if me["role"] == "owner":
            new_role = "admin" if target["role"] == "member" else "member"
            if c1.button(f"Passer {ROLE_LABELS[new_role].lower()}"):
                ok_or_error(call("PATCH", f"/org/members/{target['id']}", json={"role": new_role}), "Rôle modifié")
                st.rerun()
        if c2.button("Retirer de l'usine"):
            if ok_or_error(call("DELETE", f"/org/members/{target['id']}"), "Membre retiré"):
                st.rerun()


def tab_subscription(me: dict, org: dict):
    limits = org["limits"]
    st.subheader(f"Plan {org['plan_label']}")
    c1, c2 = st.columns(2)
    c1.metric("Machines", f"{org['machines']} / {limits['max_machines']}")
    c2.metric("Mesures aujourd'hui", f"{org['measures_today']:,} / {limits['max_measures_per_day']:,}".replace(",", " "))
    st.progress(min(1.0, org["measures_today"] / limits["max_measures_per_day"]))
    if me["role"] == "owner":
        target = "FREE" if org["plan"] == "PRO" else "PRO"
        label = "Passer au plan Pro (paiement simulé)" if target == "PRO" else "Revenir au plan Gratuit"
        if st.button(label):
            if ok_or_error(call("PUT", "/org/plan", json={"plan": target}), "Plan modifié"):
                st.rerun()

    st.subheader("Modèle d'IA")
    models = call("GET", "/org/models").json()
    st.write(f"Modèle utilisé : **{models['current_model']}**")
    if models["custom_model_allowed"] and me["role"] in ("owner", "admin"):
        st.caption("Le réentraînement utilise vos mesures envoyées avec un retour terrain (champ « label »).")
        if st.button("Réentraîner sur les données de l'usine"):
            ok_or_error(call("POST", "/org/models/retrain"),
                        "Réentraînement lancé en arrière-plan : actualisez dans une minute.")
    elif not models["custom_model_allowed"]:
        st.info("Le réentraînement sur vos propres données est inclus dans le plan Pro.")
    if models["history"]:
        st.dataframe(pd.DataFrame([{"version": h["name"], "statut": h["status"], "résultat": h["message"],
                                    "demandé le": h["created_at"][:19]} for h in models["history"]]),
                     width="stretch", hide_index=True)

    st.subheader("Export (plan Pro)")
    if limits["export"] and me["role"] in ("owner", "admin"):
        cols = st.columns(2)
        for col, name in zip(cols, ("mesures", "alertes")):
            if col.button(f"Préparer l'export des {name}"):  # généré seulement sur demande
                r = call("GET", f"/export/{name}.csv")
                if ok_or_error(r):
                    col.download_button(f"Télécharger les {name} (CSV)", r.content,
                                        file_name=f"maintai_{name}.csv", mime="text/csv")
    else:
        st.info("L'export CSV est réservé au plan Pro (propriétaire et administrateurs).")

    st.subheader("Mesures en quarantaine")
    q = call("GET", "/quarantaine", params={"limit": 100}).json()
    if q:
        st.dataframe(pd.DataFrame([{"reçue": x["received_at"][:19], "message_id": x["message_id"],
                                    "raisons": " ; ".join(x["reasons"])} for x in q]),
                     width="stretch", hide_index=True)
    else:
        st.write("Aucune mesure rejetée.")


# ------------------------------------------------------------------ super-administrateur

def superadmin_page():
    st.subheader("Usines")
    orgs = call("GET", "/admin/organizations").json()
    st.dataframe(pd.DataFrame([{
        "usine": o["name"], "plan": o["plan"], "membres": o["members"],
        "machines": f"{o['machines']}/{o['max_machines']}",
        "mesures du jour": f"{o['measures_today']}/{o['max_measures_per_day']}",
        "alertes actives": o["active_alerts"], "dernière mesure": (o["last_measure_at"] or "")[:19],
        "modèle": o["model"]} for o in orgs]), width="stretch", hide_index=True)
    if orgs:
        c1, c2 = st.columns([3, 1])
        target = c1.selectbox("Usine", orgs, format_func=lambda o: f"{o['name']} ({o['plan']})")
        new_plan = "FREE" if target["plan"] == "PRO" else "PRO"
        if c2.button(f"Passer en {new_plan}"):
            if ok_or_error(call("PUT", f"/admin/organizations/{target['id']}/plan", json={"plan": new_plan})):
                st.rerun()
    st.subheader("Workers")
    w = call("GET", "/admin/workers").json()
    st.metric("Tâches en attente dans la file", w["queued_tasks"])
    if w["workers"]:
        st.dataframe(pd.DataFrame([{"worker": x["name"], "en ligne": "✅", "processus": x["processes"],
                                    "tâches en cours": x["active_tasks"]} for x in w["workers"]]),
                     width="stretch", hide_index=True)
    else:
        st.error("Aucun worker ne répond : les mesures ne sont plus analysées.")


# ------------------------------------------------------------------ page principale

def main():
    if not st.session_state.get("token"):
        login_page()
        return
    me = call("GET", "/auth/me").json()
    with st.sidebar:
        st.markdown(f"### {me['full_name']}")
        if me["is_superadmin"]:
            st.write("Super-administrateur (équipe MaintAI)")
        else:
            st.write(f"{me['organization']['name']}")
            st.write(f"{ROLE_LABELS[me['role']]} — plan {me['organization']['plan']}")
        if st.button("Se déconnecter"):
            st.session_state.clear()
            st.rerun()
    st.title("⚙️ MaintAI Cloud")
    if me["is_superadmin"]:
        superadmin_page()
        return
    org = call("GET", "/org").json()
    is_admin = me["role"] in ("owner", "admin")
    t1, t2, t3, t4, t5 = st.tabs(["🚨 Alertes", "🏭 Machines", "🎚️ Coûts et seuils", "👥 Équipe", "💳 Abonnement, IA, export"])
    with t1:
        tab_alerts(me)
    with t2:
        tab_machines(is_admin)
    with t3:
        tab_settings(is_admin)
    with t4:
        tab_team(me)
    with t5:
        tab_subscription(me, org)


main()
