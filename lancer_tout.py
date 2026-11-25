"""
Relance tout le projet dans l'ordre, puis reconstruit les données de l'app
==========================================================================

    python lancer_tout.py

Il faut les données dans data_cycliste/ (Sorties_velo et Sorties_autres) et data_psychologique/.
Paquets : pandas, numpy, openpyxl, scipy, matplotlib, et jupyter (nbconvert) pour le notebook du profil.
"""

import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent

ETAPES = [
    ("Paramètres communs (FTP, FC max)", [sys.executable, "commun/parametres.py"]),
    ("Charge externe", [sys.executable, "charge_externe/charge_externe.py"]),
    ("Charge interne et psy", [sys.executable, "charge_interne/charge_interne.py"]),
    ("Profil", [sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute",
                "--output-dir", "profil/.execution", "profil/profilage.ipynb"]),
    ("Évolution", [sys.executable, "evolution/evolution.py"]),
    ("Données de l'app", [sys.executable, "app/construire_data.py"]),
]


def main():
    for nom, commande in ETAPES:
        print(f"\n===== {nom} =====")
        resultat = subprocess.run(commande, cwd=RACINE)
        if resultat.returncode != 0:
            if nom == "Profil":
                print("Notebook non exécuté (jupyter installé ?), on garde le profil.json existant.")
                continue
            sys.exit(f"Échec : {nom}")
    shutil.rmtree(RACINE / "profil" / ".execution", ignore_errors=True)
    print("\nTerminé. Ouvrir app/index.html")


if __name__ == "__main__":
    main()
