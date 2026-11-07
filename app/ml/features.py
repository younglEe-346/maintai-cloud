"""Variables d'entrée du modèle.

Le modèle reçoit les 5 mesures envoyées par la machine (noms de l'API) et
calcule lui-même 3 variables physiques. Ce calcul fait partie du pipeline
scikit-learn : l'entraînement et le worker utilisent donc exactement le même code.
"""
import numpy as np
import pandas as pd

# nom dans l'API -> nom de la colonne dans le fichier AI4I
SENSOR_COLUMNS = {
    "air_temp": "Air temperature [K]",
    "process_temp": "Process temperature [K]",
    "rotational_speed": "Rotational speed [rpm]",
    "torque": "Torque [Nm]",
    "tool_wear": "Tool wear [min]",
}
RAW_FEATURES = list(SENSOR_COLUMNS)
DERIVED_FEATURES = ["temp_diff", "power_w", "wear_x_torque"]
FEATURES = RAW_FEATURES + DERIVED_FEATURES


def from_ai4i(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes du CSV AI4I avec les noms utilisés par l'API."""
    return df.rename(columns={v: k for k, v in SENSOR_COLUMNS.items()})[RAW_FEATURES]


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(raw, columns=RAW_FEATURES).astype(float)
    # Écart de température : une mauvaise dissipation de chaleur fait chuter cet écart.
    X["temp_diff"] = X["process_temp"] - X["air_temp"]
    # Puissance mécanique (W) = couple x vitesse angulaire (rad/s).
    X["power_w"] = X["torque"] * X["rotational_speed"] * 2 * np.pi / 60
    # Usure x couple : effort cumulé sur l'outil (surcharge).
    X["wear_x_torque"] = X["tool_wear"] * X["torque"]
    return X[FEATURES]
