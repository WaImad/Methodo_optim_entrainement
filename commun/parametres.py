"""
Paramètres communs à toutes les parties : FTP et FC max de chaque cycliste
===========================================================================

- FTP par cycliste et par année = 0.95 x meilleure puissance moyenne sur 20 min de l'année
  (sorties vélo avec capteur de puissance)
- FC max par cycliste = plus haute moyenne glissante de la FC sur 10 s, toutes séances confondues

Sortie : commun/parametres.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from commun.donnees import FICHIER_PARAMETRES, a_fc, a_puissance, lire_seance, lister_seances


def pics_seance(f):
    """Meilleure 20 min (si capteur de puissance) et pic de FC sur 10 s d'une séance."""
    df = lire_seance(f)
    mmp20 = None
    if a_puissance(df) and len(df) >= 1200:
        mmp20 = float(df["watts"].rolling(1200).mean().max())
    pic_fc = float(df["hr"].rolling(10).mean().max()) if a_fc(df) else None
    return mmp20, pic_fc


def main():
    seances = lister_seances()
    print(f"{len(seances)} séances à lire...")
    pics = [pics_seance(f) for f in seances["fichier"]]
    seances["mmp20"] = [p[0] for p in pics]
    seances["pic_fc"] = [p[1] for p in pics]

    resultat = {}
    for cycliste, s in seances.groupby("cycliste"):
        velo = s[(s["sport"] == "velo") & s["mmp20"].notna()]
        ftp = {str(a): round(0.95 * g["mmp20"].max()) for a, g in velo.groupby("annee")}
        resultat[cycliste] = {
            "poids_kg": int(s["poids_kg"].iloc[0]),
            "fc_max": round(s["pic_fc"].max()),
            "ftp": ftp,
        }
        print(cycliste, resultat[cycliste])

    with open(FICHIER_PARAMETRES, "w", encoding="utf-8") as fp:
        json.dump({
            "metadata": {
                "date_export": datetime.now().isoformat(timespec="seconds"),
                "ftp": "0.95 x meilleure 20 min de l'année (sorties vélo avec puissance)",
                "fc_max": "plus haute moyenne glissante sur 10 s, toutes séances",
            },
            "cyclistes": resultat,
        }, fp, ensure_ascii=False, indent=2)
    print("Écrit :", FICHIER_PARAMETRES)


if __name__ == "__main__":
    main()
