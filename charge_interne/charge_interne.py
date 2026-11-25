import json
import re
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from commun.donnees import DOSSIER_PSY, lister_seances, lire_seance, a_puissance, a_fc, charger_parametres

# ---------- Paramètres à adapter ----------
# séances, nettoyage (FC valide 30-230 bpm, pauses > 10 s) et FC max : communs à tout le groupe (dossier commun/)
DOSSIER_XLSX = DOSSIER_PSY                             # 1 .xlsx par cycliste
FC_MAX = {}             # ex : {"cyclist1": 192} pour forcer une valeur. Sinon : commun/parametres.json
BORNES = [0.5, 0.6, 0.7, 0.8, 0.9]   # zones Edwards (% FC max)
FICHIER_SORTIE = Path(__file__).resolve().parent / "charge_interne.json"


# ---------- Lecture d'une sortie ----------
def lire_sortie(f):
    df = lire_seance(f, colonnes=("hr", "watts"))
    # durée = temps écoulé entre deux mesures, les trous trop longs sont plafonnés
    sortie = {
        "duree_s": float(df["dt"].sum()),
        "a_puissance": a_puissance(df),
        "a_fc": a_fc(df),
        "hist": None,
        "hr_max": None,
        "hr_moy": None,
    }
    ok = df["hr"].notna()
    hist = df.loc[ok, "dt"].groupby(df.loc[ok, "hr"].round().astype(int)).sum()
    if hist.empty or hist.sum() == 0:
        return sortie   # séance gardée, sans indicateurs de FC
    sortie.update({
        "hist": hist,
        "hr_max": int(hist.index.max()),
        "hr_moy": float((hist.index.to_numpy() * hist.to_numpy()).sum() / hist.sum()),
    })
    return sortie


def zones_edwards(hist, fc_max):
    """Retourne (minutes par zone 0..5, TRIMP Edwards)."""
    zone = np.digitize(hist.index.to_numpy() / fc_max, BORNES)  # 0 = sous 50 %
    t_min = np.bincount(zone, weights=hist.to_numpy(), minlength=6) / 60
    trimp = float((t_min[1:] * np.arange(1, 6)).sum())
    return t_min, trimp


# ---------- Lecture du fichier Excel d'un cycliste ----------
def lire_xlsx(cycliste):
    num = re.search(r"\d+", cycliste)
    if not num:
        return None, None
    # le nom du fichier doit se terminer par ce numéro exact (1 ne matche pas 10 ni 11)
    motif = re.compile(rf"(?<!\d){num.group(0)}$")
    candidats = [p for p in DOSSIER_XLSX.rglob("Charge_interne_psy_*.xlsx")
                 if motif.search(p.stem) and not p.name.startswith("~$")]
    if not candidats:
        return None, None
    xl = pd.read_excel(candidats[0], sheet_name=["seances", "hooper"])

    s = xl["seances"].copy()
    s["cle"] = s["fichier"].astype(str).map(lambda x: Path(x).stem)
    s["date_j"] = pd.to_datetime(s["date"], dayfirst=True, errors="coerce").dt.normalize()

    h = xl["hooper"].copy()
    h["date_j"] = pd.to_datetime(h["date"], dayfirst=True, errors="coerce").dt.normalize()
    h = h.dropna(subset=["date_j"]).drop_duplicates("date_j")  # 1 réponse par jour (la première)
    return s, h.set_index("date_j")


def date_depuis_nom(stem):
    m = re.match(r"(\d{4})_(\d{2})_(\d{2})", stem)
    return pd.Timestamp(int(m[1]), int(m[2]), int(m[3])) if m else pd.NaT


def trouver_seance(s, stem, date):
    """Croisement par nom de fichier, sinon par date si une seule séance ce jour-là."""
    if s is None:
        return {}
    par_nom = s[s["cle"] == stem]
    if len(par_nom):
        return par_nom.iloc[0].to_dict()
    if pd.notna(date):
        par_date = s[s["date_j"] == date]
        if len(par_date) == 1:
            return par_date.iloc[0].to_dict()
    return {}


# ---------- Nettoyage pour JSON ----------
def propre(v):
    if isinstance(v, dict):
        return {k: propre(x) for k, x in v.items()}
    if isinstance(v, list):
        return [propre(x) for x in v]
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, np.generic):
        return v.item()
    return v


# ---------- Construction ----------
def construire():
    resultat = {}
    parametres = charger_parametres()
    for cycliste, liste in lister_seances().groupby("cycliste"):   # vélo et autres sports
        poids_cycliste = int(liste["poids_kg"].iloc[0])

        # Passe 1 : lecture légère de toutes les sorties
        sorties = []
        for _, ligne in liste.iterrows():
            f = ligne["fichier"]
            try:
                res = lire_sortie(f)
            except Exception as e:
                print(f"[{cycliste}] erreur {f.name} : {e}")
                continue
            res["fichier"] = f
            res["sport"] = ligne["sport"]
            sorties.append(res)
        if not sorties:
            continue

        fc_max = FC_MAX.get(cycliste) or parametres[cycliste]["fc_max"]
        s, h = lire_xlsx(cycliste)
        if s is None:
            print(f"[{cycliste}] pas de fichier xlsx trouvé")

        # Passe 2 : calcul des métriques et croisement
        seances = []
        for x in sorties:
            f = x["fichier"]
            stem = f.stem
            date = date_depuis_nom(stem)
            # séance sans FC : pas de zones ni de TRIMP, mais RPE et Hooper quand même
            if x["hist"] is not None:
                t_min, trimp = zones_edwards(x["hist"], fc_max)
            else:
                t_min, trimp = [None] * 6, None

            ligne_s = trouver_seance(s, stem, date)
            ligne_h = {}
            if h is not None and pd.notna(date) and date in h.index:
                ligne_h = h.loc[date].to_dict()

            rpe = ligne_s.get("rpe")
            hooper = [ligne_h.get(k) for k in ("sommeil", "stress", "fatigue", "courbatures")]
            arrondi = lambda v, n: round(v, n) if v is not None else None

            seances.append({
                "seance": stem,
                "date": date,
                "annee": int(date.year) if pd.notna(date) else None,
                "sport": x["sport"],
                "duree_s": round(x["duree_s"]),
                "duree_h": round(x["duree_s"] / 3600, 3),
                "a_puissance": x["a_puissance"],
                "a_fc": x["a_fc"],
                "cycliste": cycliste,
                "poids_kg": poids_cycliste,
                "hr_moy": arrondi(x["hr_moy"], 1),
                "hr_max": x["hr_max"],
                "t_z1": arrondi(t_min[1], 2),
                "t_z2": arrondi(t_min[2], 2),
                "t_z3": arrondi(t_min[3], 2),
                "t_z4": arrondi(t_min[4], 2),
                "t_z5": arrondi(t_min[5], 2),
                "trimp_edwards": arrondi(trimp, 1),
                "rpe": rpe,
                "lactate": ligne_s.get("lactate"),
                "sommeil": ligne_h.get("sommeil"),
                "stress": ligne_h.get("stress"),
                "fatigue": ligne_h.get("fatigue"),
                "courbatures": ligne_h.get("courbatures"),
                # métriques supplémentaires
                "srpe_charge": (rpe * x["duree_s"] / 60) if pd.notna(rpe) else None,
                "hooper_index": sum(hooper) if all(pd.notna(v) for v in hooper) else None,
            })

        seances.sort(key=lambda d: d["seance"])
        resultat[cycliste] = {
            "info": {
                "poids_kg": poids_cycliste,
                "fc_max": fc_max,
                "annees": sorted({s["annee"] for s in seances if s["annee"]}),
                "nb_seances_total": len(seances),
                "nb_seances_fc": sum(1 for s in seances if s["a_fc"]),
            },
            "seances": seances,
        }
        print(f"[{cycliste}] {len(seances)} séances (dont {resultat[cycliste]['info']['nb_seances_fc']} avec FC), FC max = {fc_max}")

    return resultat


if __name__ == "__main__":
    data = propre({
        "metadata": {
            "titre": "Charge d'entraînement interne - Cyclistes",
            "date_export": datetime.now().isoformat(timespec="seconds"),
            "description": "Données de charge interne (FC moyenne, TRIMP, s-RPE) "
                           "organisées par cycliste",
            "parametres": charger_parametres(),
        },
        "cyclistes": construire(),
    })
    with open(FICHIER_SORTIE, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
    print(f"Écrit : {FICHIER_SORTIE}")