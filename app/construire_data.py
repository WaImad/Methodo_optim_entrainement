"""
Prépare les données de l'app (app/data.js) à partir des JSON des quatre parties
===============================================================================

On ne garde que ce que les pages affichent, pour que data.js reste léger.
data.js est un script (window.DATA = ...) et pas un .json : l'app s'ouvre alors en double-cliquant
sur index.html, sans serveur.
"""

import json
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
SORTIE = Path(__file__).resolve().parent / "data.js"
DUREES_MMP = [5, 30, 60, 180, 300, 480, 1200, 3600]


def lire(chemin):
    with open(RACINE / chemin, encoding="utf-8") as fp:
        return json.load(fp)


def arrondi(v, n=1):
    return None if v is None else round(v, n)


def page_profil(p):
    bio = p["global_profile"]["bioenergetics"]
    valenzuela = p["global_profile"]["signature_1_bioenergetic_valenzuela"]["relative"]
    return {
        "profil_choisi": p.get("profil_choisi"),
        "profil_valenzuela": valenzuela.get("hybrid_profile_note"),
        "cp": arrondi(bio.get("cp_watts"), 0),
        "cp_wkg": arrondi(bio.get("cp_w_kg"), 2),
        "w_prime_kj": arrondi(bio.get("w_prime_kj"), 1),
        "mmp_durees": DUREES_MMP,
        "mmp_w": [arrondi(bio.get(f"mmp_{d}s"), 0) for d in DUREES_MMP],
        "mmp_wkg": [arrondi(bio.get(f"mmp_{d}s_w_kg"), 2) for d in DUREES_MMP],
        "derive_cardiaque_pct": arrondi(p["global_profile"]["cardiac_drift"].get("median_drift_pct"), 1),
    }


def page_externe(e):
    hebdo = e["charge_hebdomadaire"]
    return {
        "ftp": {str(f["annee"]): round(f["ftp"]) for f in e["ftp"]},
        "semaine": [h["semaine"][:10] for h in hebdo],
        "tss_semaine": [arrondi(h["TSS"], 0) for h in hebdo],
        "heures_semaine": [arrondi(h["heures"], 1) for h in hebdo],
        "zones": [{"annee": z["annee"], "zone": z["zone"], "pct": arrondi(z["pct"], 1)}
                  for z in e["zones_puissance"]],
    }


def page_interne(i):
    s = pd.DataFrame(i["seances"])
    s["date"] = pd.to_datetime(s["date"])
    semaine = s["date"].dt.to_period("W-SUN").dt.start_time
    hebdo = s.groupby(semaine)[["trimp_edwards", "srpe_charge"]].sum(min_count=1)

    zones = [f"t_z{k}" for k in range(1, 6)]
    hooper = s.dropna(subset=["hooper_index"]).drop_duplicates("date").sort_values("date")
    return {
        "fc_max": i["info"]["fc_max"],
        "nb_seances_fc": i["info"]["nb_seances_fc"],
        "semaine": hebdo.index.strftime("%Y-%m-%d").tolist(),
        "trimp_semaine": [arrondi(v, 0) if pd.notna(v) else None for v in hebdo["trimp_edwards"]],
        "srpe_semaine": [arrondi(v, 0) if pd.notna(v) else None for v in hebdo["srpe_charge"]],
        "zones_fc_min": [arrondi(v, 0) for v in s[zones].sum()],
        "hooper_date": hooper["date"].dt.strftime("%Y-%m-%d").tolist(),
        "hooper": hooper["hooper_index"].astype(int).tolist(),
    }


def main():
    profil = lire("profil/profil.json")["cyclistes"]
    externe = lire("charge_externe/charge_externe.json")["cyclistes"]
    interne = lire("charge_interne/charge_interne.json")["cyclistes"]
    evolution = lire("evolution/evolution.json")["cyclistes"]
    parametres = lire("commun/parametres.json")["cyclistes"]

    cyclistes = []
    for cid in sorted(externe, key=lambda c: int(c.removeprefix("cyclist"))):
        types = evolution[cid]["info"]["nb_seances_par_type"]
        cyclistes.append({
            "id": cid,
            "label": "Cycliste " + cid.removeprefix("cyclist"),
            "weight_kg": parametres[cid]["poids_kg"],
            "years": externe[cid]["info"]["annees"],
            "n_rides": types["velo"] + types["velo_fc"],
            "n_other": types["autre"],
            "hr_max": parametres[cid]["fc_max"],
            "profil": page_profil(profil[cid]) if cid in profil else None,
            "externe": page_externe(externe[cid]),
            "interne": page_interne(interne[cid]),
            "evolution": {"info": evolution[cid]["info"], **evolution[cid]["quotidien"]},
        })

    SORTIE.write_text("window.DATA = " + json.dumps({"cyclists": cyclistes}, ensure_ascii=False) + ";\n",
                      encoding="utf-8")
    print(f"Écrit : {SORTIE} ({SORTIE.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    main()
