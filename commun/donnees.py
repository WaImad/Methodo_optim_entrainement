"""
Lecture commune des séances pour toutes les parties du projet
==============================================================

Une séance = un fichier CSV à 1 Hz dans data_cycliste/Sorties_velo ou data_cycliste/Sorties_autres.
Toutes les parties (charge externe, charge interne, profil, évolution) lisent les données par ici,
pour travailler sur les mêmes séances avec le même nettoyage.
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DONNEES = RACINE / "data_cycliste"
DOSSIER_PSY = RACINE / "data_psychologique"
FICHIER_PARAMETRES = Path(__file__).resolve().parent / "parametres.json"

SPORTS = {"velo": "Sorties_velo", "autre": "Sorties_autres"}

HR_MIN_VALIDE = 30         # en dessous, la mesure est considérée comme invalide
HR_MAX_VALIDE = 230
PAUSE_MAX_S = 10           # un trou > 10 s entre deux mesures n'est pas compté comme effort
PART_PUISSANCE_MIN = 0.3   # au moins 30 % des secondes avec des watts, sinon pas de capteur


def date_depuis_nom(stem):
    """Date et heure de début tirées du nom du fichier (2022_01_02_10_35_14)."""
    m = re.match(r"(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})", stem)
    return pd.Timestamp(*map(int, m.groups())) if m else pd.NaT


def lister_seances(sports=("velo", "autre")):
    """
    Liste toutes les séances (sans les lire)

    Retourne:
        DataFrame avec une ligne par séance : cycliste, poids_kg, sport, seance, debut, date, annee, fichier
    """
    lignes = []
    for sport in sports:
        dossier_sport = DOSSIER_DONNEES / SPORTS[sport]
        if not dossier_sport.exists():
            continue
        for dossier in sorted(d for d in dossier_sport.iterdir() if d.is_dir()):
            m = re.match(r"(cyclist\d+)_(\d+)kg", dossier.name)
            if not m:
                continue
            for f in sorted(dossier.rglob("*.csv")):
                if "fc_repos" in f.name:
                    continue
                debut = date_depuis_nom(f.stem)
                lignes.append({
                    "cycliste": m.group(1),
                    "poids_kg": int(m.group(2)),
                    "sport": sport,
                    "seance": f.stem,
                    "debut": debut,
                    "date": debut.normalize(),
                    "annee": debut.year,
                    "fichier": f,
                })
    return pd.DataFrame(lignes)


def lire_seance(f, colonnes=("watts", "hr")):
    """
    Lit et nettoie une séance

    - watts négatifs ou manquants -> 0
    - FC hors de [30, 230] bpm -> manquante (perte du signal)
    - dt = temps entre deux mesures, plafonné à 10 s (les pauses ne comptent pas)
    """
    garder = set(colonnes) | {"secs"}
    df = pd.read_csv(f, usecols=lambda c: c in garder, dtype="float32")
    df = df.dropna(subset=["secs"]).sort_values("secs").reset_index(drop=True)
    df["dt"] = df["secs"].diff().fillna(0).clip(lower=0, upper=PAUSE_MAX_S)
    if "watts" in df:
        df["watts"] = df["watts"].clip(lower=0).fillna(0)
    if "hr" in df:
        df.loc[(df["hr"] < HR_MIN_VALIDE) | (df["hr"] > HR_MAX_VALIDE), "hr"] = np.nan
    return df


def a_puissance(df):
    return "watts" in df and len(df) > 0 and bool((df["watts"] > 0).mean() > PART_PUISSANCE_MIN)


def a_fc(df):
    return "hr" in df and bool(df["hr"].notna().any())


def charger_parametres():
    """FTP par cycliste et par année, FC max par cycliste (voir commun/parametres.py)."""
    with open(FICHIER_PARAMETRES, encoding="utf-8") as fp:
        return json.load(fp)["cyclistes"]
