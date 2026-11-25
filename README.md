# Methodo_optim_entrainement
Repo pour le bon déroulement du projet sur le suivi de la charge d'entrainement des cyclistes

## Données

Les données ne sont plus dans le dépôt (traces GPS des coureurs, dépôt public). Il faut les copier à la main :

- `data_cycliste/Sorties_velo/` et `data_cycliste/Sorties_autres/` (le contenu de `Data_Cyclist_Tri`)
- `data_psychologique/` (les 7 fichiers `Charge_interne_psy_cyclisteN.xlsx`)

Ces dossiers sont dans le `.gitignore`.

## Organisation

| Dossier | Qui | Sortie |
|---|---|---|
| `commun/` | tout le monde | `donnees.py` : lecture des séances, `parametres.py` -> `parametres.json` (FTP par année, FC max) |
| `charge_externe/` | Imad | `charge_externe.json` |
| `charge_interne/` | Zoé | `charge_interne.json` |
| `profil/` | Camilo | `profilage.ipynb` -> `profil.json` et `figures/` |
| `evolution/` | Colin | `evolution.json` |
| `app/` | Colin | `construire_data.py` -> `data.js`, l'app web |

Règles communes : toutes les séances sont gardées (vélo et autres sports), avec des valeurs vides quand il manque la puissance ou la FC. FTP = 0.95 x meilleure 20 min de l'année. FC max = plus haute moyenne sur 10 s. Tous les JSON ont la même forme : `metadata` puis `cyclistes` -> `info` et `seances`.

## Lancer

```
pip install pandas numpy openpyxl scipy matplotlib jupyter
python lancer_tout.py
```

Puis ouvrir `app/index.html` (double-clic, pas besoin de serveur). Le bouton "Exporter en PDF" imprime toutes les pages : choisir "Enregistrer au format PDF".
