"""Entraînement du modèle de risque de panne (Machine failure) sur AI4I 2020.

Lancement (dans l'image Docker, pour avoir les mêmes versions que le worker) :
    docker compose run --rm trainer
Options : --cost-ratio 50  --data data/ai4i2020.csv
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from app.ml.cost import DEFAULT_COST_RATIO, NEVER_ALERT, best_f1_threshold, best_threshold, confusion_at
from app.ml.explain import shapley_contributions
from app.ml.features import FEATURES, RAW_FEATURES, build_features, from_ai4i
from app.ml.registry import next_version, save_artifact

SEED = 42
TARGET = "Machine failure"
MODES = ["TWF", "HDF", "PWF", "OSF", "RNF"]
UCI_ANNOUNCED = {"TWF": 120, "RNF": 5}  # chiffres de la page UCI cités dans le sujet
MIN_LIFT = 5  # un mode est "prédictible" si sa PR-AUC dépasse 5 fois celle du hasard


def candidates() -> dict:
    feats = FunctionTransformer(build_features)
    return {
        "logistic_regression": Pipeline([
            ("features", feats), ("scale", StandardScaler()),
            ("model", LogisticRegression(class_weight="balanced", max_iter=5000)),
        ]),
        "random_forest": Pipeline([
            ("features", feats),
            ("model", RandomForestClassifier(
                n_estimators=300, class_weight="balanced_subsample",
                n_jobs=-1, random_state=SEED)),
        ]),
        "hist_gradient_boosting": Pipeline([
            ("features", feats),
            ("model", HistGradientBoostingClassifier(class_weight="balanced", random_state=SEED)),
        ]),
    }


def oof_proba(pipeline, X, y) -> np.ndarray:
    """Probabilités hors-échantillon : chaque ligne est prédite par un modèle
    qui ne l'a jamais vue (validation croisée stratifiée en 5 blocs)."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    return cross_val_predict(pipeline, X, y, cv=cv, method="predict_proba")[:, 1]


def fmt(c: dict) -> str:
    return (f"seuil={c['threshold']:.3f}  coût={c['cost']:.0f}  "
            f"pannes détectées={c['tp']}/{c['tp'] + c['fn']} (rappel {c['recall']:.1%})  "
            f"fausses alertes={c['fp']}  précision={c['precision']:.1%}")


def report_data(df: pd.DataFrame) -> dict:
    print("=" * 78 + "\n1. DONNÉES\n" + "=" * 78)
    n, n_fail = len(df), int(df[TARGET].sum())
    counts = {m: int(df[m].sum()) for m in MODES}
    print(f"{n} lignes, {n_fail} pannes ({n_fail / n:.2%})")
    print("Modes mesurés : " + ", ".join(f"{m} {c}" for m, c in counts.items()))

    n_modes = df[MODES].sum(axis=1)
    fail_no_mode = int(((df[TARGET] == 1) & (n_modes == 0)).sum())
    rnf_no_fail = int(((df["RNF"] == 1) & (df[TARGET] == 0)).sum())
    mode_no_fail = int(((df[TARGET] == 0) & (n_modes > 0)).sum())
    twf_fail = int(((df["TWF"] == 1) & (df[TARGET] == 1)).sum())

    print("\nÉcart avec la page UCI :")
    for m, announced in UCI_ANNOUNCED.items():
        print(f"  {m} : {announced} annoncés par UCI, {counts[m]} mesurés dans le fichier "
              f"(écart {counts[m] - announced:+d})")
    print("Constats dans le fichier :")
    print(f"  - {twf_fail} des {counts['TWF']} TWF sont aussi marqués 'Machine failure'.")
    print(f"  - {rnf_no_fail} des {counts['RNF']} RNF ont 'Machine failure' = 0 "
          f"(panne aléatoire notée, mais machine non déclarée en panne).")
    print(f"  - {mode_no_fail} lignes ont un mode de panne sans 'Machine failure'.")
    print(f"  - {fail_no_mode} pannes n'ont aucun mode renseigné.")
    print(f"  - {int((n_modes > 1).sum())} lignes ont plusieurs modes à la fois (multi-étiquette).")
    return {"rows": n, "failures": n_fail, "mode_counts": counts,
            "uci_announced": UCI_ANNOUNCED, "failure_without_mode": fail_no_mode,
            "rnf_without_failure": rnf_no_fail, "mode_without_failure": mode_no_fail}


def train_modes(df: pd.DataFrame, X: pd.DataFrame, idx_tr, idx_te, algorithm: str) -> dict:
    """Mode de panne (multi-étiquette) : un classifieur oui/non par mode, car une
    même panne peut avoir plusieurs modes à la fois."""
    print("\n" + "=" * 78 + "\n5. MODES DE PANNE (un classifieur par mode)\n" + "=" * 78)
    print(f"Un mode est jugé prédictible si sa PR-AUC hors-échantillon dépasse {MIN_LIFT} x le hasard.\n")
    print(f"{'mode':5s} {'nb':>4s} {'hasard':>7s} {'PR-AUC cv':>10s} {'PR-AUC test':>12s} "
          f"{'test : trouvés / fausses':>26s}  prédictible ?")

    models, thresholds, report, predictable = {}, {}, {}, []
    proba_te = {}
    for m in MODES:
        ym = df[m].to_numpy()
        # évaluation : seuil choisi sur 80 %, mesuré sur les 20 % jamais vus
        thr_tr = best_f1_threshold(ym[idx_tr], oof_proba(candidates()[algorithm], X.iloc[idx_tr], ym[idx_tr]))
        p_te = candidates()[algorithm].fit(X.iloc[idx_tr], ym[idx_tr]).predict_proba(X.iloc[idx_te])[:, 1]
        proba_te[m] = p_te
        test = confusion_at(ym[idx_te], p_te, thr_tr["threshold"], 1.0)
        test["pr_auc"] = float(average_precision_score(ym[idx_te], p_te))

        # modèle final sur 100 % ; seuil choisi sur les probabilités hors-échantillon
        oof = oof_proba(candidates()[algorithm], X, ym)
        pr_auc_oof = float(average_precision_score(ym, oof))
        prevalence = float(ym.mean())
        ok = pr_auc_oof >= MIN_LIFT * prevalence
        models[m] = candidates()[algorithm].fit(X, ym)
        thresholds[m] = best_f1_threshold(ym, oof)["threshold"]
        if ok:
            predictable.append(m)
        report[m] = {"count": int(ym.sum()), "prevalence": prevalence, "pr_auc_oof": pr_auc_oof,
                     "threshold_f1": thresholds[m], "holdout_test": test, "predictable": ok}
        print(f"{m:5s} {int(ym.sum()):4d} {prevalence:7.4f} {pr_auc_oof:10.3f} {test['pr_auc']:12.3f} "
              f"{test['tp']:>9d}/{test['tp'] + test['fn']:<3d} / {test['fp']:<10d}  {'oui' if ok else 'NON'}")

    # Diagnostic : sur les vraies pannes du test, le mode le plus probable est-il le bon ?
    true_modes = df[predictable].to_numpy()[idx_te]
    fail_te = (df[TARGET].to_numpy()[idx_te] == 1) & (true_modes.sum(axis=1) > 0)
    P = np.column_stack([proba_te[m] for m in predictable])
    top1 = P.argmax(axis=1)
    hits = true_modes[np.arange(len(top1)), top1][fail_te]
    report["top1_on_test_failures"] = {"correct": int(hits.sum()), "total": int(fail_te.sum())}
    print(f"\nSur les {int(fail_te.sum())} vraies pannes du test (avec mode connu), le mode le plus probable "
          f"est correct {int(hits.sum())} fois ({hits.mean():.0%}).")
    return {"models": models, "thresholds": thresholds, "predictable": predictable, "report": report}


def check_contributions(df, X, idx_tr, idx_te, pipe, predictable) -> dict:
    """Contrôle : sur les vraies pannes du test (modèle entraîné sur 80 %), les
    mesures qui contribuent le plus correspondent-elles à la physique de chaque mode ?"""
    print("\n" + "=" * 78 + "\n6. CONTRIBUTIONS (pannes du test, un seul mode, modèle 80 %)\n" + "=" * 78)
    y = df[TARGET].to_numpy()
    reference = {f: float(v) for f, v in X.iloc[idx_tr][y[idx_tr] == 0].median().items()}
    predict = lambda d: pipe.predict_proba(d)[:, 1]
    print("Contribution moyenne au risque, en points de pourcentage :")
    print(f"{'mode':5s} {'nb':>3s} " + " ".join(f"{f:>16s}" for f in RAW_FEATURES) + "   check somme")
    out = {}
    single = df[MODES].sum(axis=1).to_numpy() == 1
    for m in predictable:
        rows = idx_te[(df[m].to_numpy()[idx_te] == 1) & single[idx_te] & (y[idx_te] == 1)]
        if len(rows) == 0:
            continue
        phi, base = shapley_contributions(predict, X.iloc[rows], reference)
        # propriété d'additivité : référence + somme des contributions = risque prédit
        err = float(np.abs(base + phi.sum(axis=1) - predict(X.iloc[rows])).max())
        mean = phi.mean(axis=0)
        out[m] = {"n": int(len(rows)), "mean_contribution": dict(zip(RAW_FEATURES, mean.round(4).tolist())),
                  "additivity_max_error": err}
        print(f"{m:5s} {len(rows):3d} " + " ".join(f"{v * 100:+16.1f}" for v in mean) + f"   écart max {err:.1e}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/ai4i2020.csv")
    parser.add_argument("--cost-ratio", type=float, default=DEFAULT_COST_RATIO)
    args = parser.parse_args()

    path = Path(args.data)
    if not path.exists():
        sys.exit(f"Fichier introuvable : {path}. Téléchargez AI4I 2020 depuis UCI (DOI 10.24432/C5HS5C).")
    data_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    df = pd.read_csv(path, encoding="utf-8-sig")
    data_info = report_data(df)

    X, y = from_ai4i(df), df[TARGET].to_numpy()
    ratio = args.cost_ratio
    prevalence = y.mean()

    # ---- 2. Comparaison des modèles (sur 80 % des données, test mis de côté) ----
    idx_tr, idx_te = train_test_split(np.arange(len(y)), test_size=0.2, stratify=y, random_state=SEED)
    X_tr, X_te, y_tr, y_te = X.iloc[idx_tr], X.iloc[idx_te], y[idx_tr], y[idx_te]
    print("\n" + "=" * 78 + "\n2. COMPARAISON (validation croisée 5 blocs sur 80 % des données)\n" + "=" * 78)
    print(f"Ratio de coût : panne manquée = {ratio:g} x fausse alerte")
    print(f"Référence PR-AUC d'un modèle au hasard = taux de pannes = {prevalence:.3f}")
    print(f"Référence 'ne jamais alerter' : coût = {confusion_at(y_tr, np.zeros(len(y_tr)), NEVER_ALERT, ratio)['cost']:.0f}")
    print(f"Référence 'toujours alerter'  : coût = {confusion_at(y_tr, np.ones(len(y_tr)), 0.0, ratio)['cost']:.0f}\n")

    comparison = {}
    for name, pipe in candidates().items():
        p = oof_proba(pipe, X_tr, y_tr)
        best = best_threshold(y_tr, p, ratio)
        comparison[name] = {"pr_auc": float(average_precision_score(y_tr, p)), **best}
        print(f"{name:24s} PR-AUC={comparison[name]['pr_auc']:.3f}  {fmt(best)}")

    chosen = min(comparison, key=lambda k: (comparison[k]["cost"], -comparison[k]["pr_auc"]))
    threshold_tr = comparison[chosen]["threshold"]
    print(f"\n-> Modèle retenu : {chosen} (coût le plus bas ; PR-AUC en cas d'égalité)")

    # ---- 3. Test final sur les 20 % jamais vus ----
    print("\n" + "=" * 78 + "\n3. TEST SUR 20 % JAMAIS VUS (estimation honnête)\n" + "=" * 78)
    pipe = candidates()[chosen].fit(X_tr, y_tr)
    p_te = pipe.predict_proba(X_te)[:, 1]
    test = {"pr_auc": float(average_precision_score(y_te, p_te)),
            **confusion_at(y_te, p_te, threshold_tr, ratio)}
    never = confusion_at(y_te, np.zeros(len(y_te)), NEVER_ALERT, ratio)["cost"]
    always = confusion_at(y_te, np.ones(len(y_te)), 0.0, ratio)["cost"]
    print(f"PR-AUC test = {test['pr_auc']:.3f}   (hasard : {y_te.mean():.3f})")
    print(f"Avec le seuil choisi en validation : {fmt(test)}")
    print(f"Comparaison coût test : modèle {test['cost']:.0f} | jamais alerter {never:.0f} | toujours alerter {always:.0f}")

    # ---- 4. Modèle final : réentraîné sur 100 % des données ----
    print("\n" + "=" * 78 + "\n4. MODÈLE FINAL (100 % des données)\n" + "=" * 78)
    oof_all = oof_proba(candidates()[chosen], X, y)
    final_thr = best_threshold(y, oof_all, ratio)
    final_pipe = candidates()[chosen].fit(X, y)
    print(f"PR-AUC hors-échantillon (100 %) = {average_precision_score(y, oof_all):.3f}")
    print(f"Seuil déployé : {fmt(final_thr)}")
    print("Seuil recalculé pour d'autres ratios (sans réentraîner) :")
    for r in (10, 20, 50, 100):
        c = best_threshold(y, oof_all, r)
        print(f"  ratio {r:>3} -> seuil {c['threshold']:.3f}  (rappel {c['recall']:.1%}, fausses alertes {c['fp']})")

    modes = train_modes(df, X, idx_tr, idx_te, chosen)

    # Machine de référence pour les contributions : médiane des cycles sans panne
    reference = {f: float(v) for f, v in X[y == 0].median().items()}
    contrib_check = check_contributions(df, X, idx_tr, idx_te, pipe, modes["predictable"])

    version = next_version()
    artifact = {
        "name": f"risk_model_v{version}",
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "algorithm": chosen,
        "pipeline": final_pipe,
        "raw_features": RAW_FEATURES,
        "features": FEATURES,
        "cost_ratio": ratio,
        "threshold": final_thr["threshold"],
        "oof_proba": oof_all.astype(np.float32),
        "oof_y": y.astype(np.int8),
        "mode_models": modes["models"],
        "mode_thresholds": modes["thresholds"],
        "predictable_modes": modes["predictable"],
        "reference": reference,
        "metrics": {"comparison_cv": comparison, "holdout_test": test,
                    "oof_full_pr_auc": float(average_precision_score(y, oof_all)),
                    "deployed_threshold": final_thr,
                    "modes": modes["report"],
                    "contributions_check": contrib_check},
        "data": {**data_info, "file": str(path), "sha256": data_sha256},
        "sklearn_version": sklearn.__version__,
        "seed": SEED,
    }
    model_file = save_artifact(artifact)
    report = {k: v for k, v in artifact.items() if k not in ("pipeline", "oof_proba", "oof_y", "mode_models")}
    model_file.with_suffix(".json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nModèle sauvegardé : {model_file}  (+ rapport {model_file.with_suffix('.json').name})")


if __name__ == "__main__":
    main()
