"""
Évolution de la charge dans le temps
====================================

Lit les séances de charge_externe.json (TSS) et de charge_interne.json (TRIMP d'Edwards)
et construit la charge de chaque jour, avec toutes les séances :
- vélo avec puissance : TSS
- vélo sans puissance et autres sports : TSS estimé à partir du TRIMP,
  avec le rapport TSS / TRIMP du cycliste (appris sur ses sorties qui ont les deux)
- ni puissance ni FC : 0, compté à part

Puis le modèle forme / fatigue : CTL (42 j), ATL (7 j), TSB = CTL - ATL.

Sortie : evolution/evolution.json
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
FICHIER_EXTERNE = RACINE / "charge_externe" / "charge_externe.json"
FICHIER_INTERNE = RACINE / "charge_interne" / "charge_interne.json"
FICHIER_SORTIE = Path(__file__).resolve().parent / "evolution.json"

TAU_CTL, TAU_ATL = 42, 7
TYPES = ["velo", "velo_fc", "autre"]


def lire(fichier):
    with open(fichier, encoding="utf-8") as fp:
        return json.load(fp)


def seances_cycliste(externe, interne):
    """Une ligne par séance avec son TSS (puissance) et son TRIMP (FC)."""
    e = pd.DataFrame(externe["seances"])[["seance", "date", "annee", "sport", "duree_s", "duree_h",
                                          "a_puissance", "a_fc", "TSS"]]
    i = pd.DataFrame(interne["seances"])[["seance", "sport", "trimp_edwards", "srpe_charge"]]
    s = e.merge(i, on=["seance", "sport"], how="left")
    s["date"] = pd.to_datetime(s["date"])
    return s


def charge_estimee(s):
    """TSS retenu pour chaque séance, et type de séance."""
    avec_les_deux = s["TSS"].notna() & (s["trimp_edwards"] > 20)
    ratio = float((s.loc[avec_les_deux, "TSS"] / s.loc[avec_les_deux, "trimp_edwards"]).median())

    s["type"] = np.where(s["sport"] == "autre", "autre",
                         np.where(s["TSS"].notna(), "velo", "velo_fc"))
    s["tss_retenu"] = s["TSS"].fillna(ratio * s["trimp_edwards"])
    s["sans_donnees"] = s["tss_retenu"].isna()
    s["tss_retenu"] = s["tss_retenu"].fillna(0)
    return s, ratio


def forme_fatigue(charge):
    """CTL et ATL : moyennes exponentielles de la charge quotidienne, TSB = CTL - ATL (fraîcheur du matin)."""
    ctl, atl, tsb = [], [], []
    c = a = 0.0
    for x in charge:
        tsb.append(c - a)
        c += (x - c) / TAU_CTL
        a += (x - a) / TAU_ATL
        ctl.append(c)
        atl.append(a)
    return ctl, atl, tsb


def quotidien(s):
    """Une ligne par jour, jours sans séance à 0 (ils font baisser la forme et la fatigue)."""
    jour = s["date"].dt.normalize()
    d = pd.DataFrame({t: s["tss_retenu"].where(s["type"] == t, 0).groupby(jour).sum() for t in TYPES})
    d["heures"] = s["duree_h"].groupby(jour).sum()
    d = d.asfreq("D", fill_value=0)
    d["ctl"], d["atl"], d["tsb"] = forme_fatigue(d[TYPES].sum(axis=1))
    return d


def main():
    externe, interne = lire(FICHIER_EXTERNE), lire(FICHIER_INTERNE)
    resultat = {}

    for cycliste in sorted(externe["cyclistes"]):
        s, ratio = charge_estimee(seances_cycliste(externe["cyclistes"][cycliste],
                                                   interne["cyclistes"][cycliste]))
        d = quotidien(s)
        n = s["type"].value_counts()
        print(f"[{cycliste}] {len(s)} séances : {n.get('velo', 0)} vélo, {n.get('velo_fc', 0)} vélo estimé FC, "
              f"{n.get('autre', 0)} autre sport, {int(s['sans_donnees'].sum())} sans données ; "
              f"{ratio:.2f} TSS par point de TRIMP")

        s["date"] = s["date"].dt.strftime("%Y-%m-%d")
        resultat[cycliste] = {
            "info": {
                "annees": sorted(s["annee"].unique().tolist()),
                "nb_seances_total": len(s),
                "nb_seances_par_type": {t: int(n.get(t, 0)) for t in TYPES},
                "nb_seances_sans_donnees": int(s["sans_donnees"].sum()),
                "tss_par_trimp": round(ratio, 3),
            },
            "seances": s[["seance", "date", "annee", "sport", "duree_s", "duree_h", "a_puissance", "a_fc",
                          "type", "TSS", "trimp_edwards", "tss_retenu", "sans_donnees"]]
                       .round(2).replace({np.nan: None}).to_dict(orient="records"),
            "quotidien": {
                "date": d.index.strftime("%Y-%m-%d").tolist(),
                **{f"tss_{t}": d[t].round(1).tolist() for t in TYPES},
                "heures": d["heures"].round(2).tolist(),
                "ctl": d["ctl"].round(1).tolist(),
                "atl": d["atl"].round(1).tolist(),
                "tsb": d["tsb"].round(1).tolist(),
            },
        }

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as fp:
        json.dump({
            "metadata": {
                "titre": "Évolution de la charge - Cyclistes",
                "date_export": datetime.now().isoformat(timespec="seconds"),
                "description": "Charge quotidienne (TSS, estimé par la FC si besoin) et modèle forme / fatigue",
                "parametres": externe["metadata"]["parametres"],
            },
            "cyclistes": resultat,
        }, fp, ensure_ascii=False, indent=2)
    print("Écrit :", FICHIER_SORTIE)


if __name__ == "__main__":
    main()
