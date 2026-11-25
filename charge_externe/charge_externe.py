"""
Script de calcul de la charge d'entraînement externe pour cyclistes
===================================================================

Ce script traite les données d'entraînement de cyclistes (fichiers CSV avec puissance et fréquence cardiaque)
et calcule les indicateurs de charge externe, notamment le TSS (Training Stress Score).

Les séances sont lues avec la lecture commune (commun/donnees.py) et la FTP vient de commun/parametres.json,
pour que toutes les parties travaillent sur les mêmes séances et les mêmes valeurs.

Sortie : Un fichier JSON structuré par cycliste avec toutes les métriques pour une application de visualisation

Auteur : Équipe FARSI, ORLANDI, GEINDRE, COVA CORREA
Date : 2026-11-20
"""

import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path
import re
from datetime import datetime
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from commun.donnees import lister_seances, lire_seance, a_puissance, a_fc, charger_parametres

# Ignorer les avertissements pour un affichage plus propre
warnings.filterwarnings('ignore')

FICHIER_SORTIE = Path(__file__).resolve().parent / "charge_externe.json"

# Zones de Coggan (en fraction de la FTP)
BORNES_ZONES = [-np.inf, 0.55, 0.75, 0.90, 1.05, 1.20, np.inf]
NOMS_ZONES = ['Z1 Récup', 'Z2 Endurance', 'Z3 Tempo', 'Z4 Seuil', 'Z5 VO2max', 'Z6 Anaérobie']


# ==============================
# 1. CHARGEMENT DES DONNÉES
# ==============================

def charger_donnees_cyclistes():
    """
    Liste toutes les séances des cyclistes (vélo et autres sports), sans les lire

    Les fichiers sont lus un par un dans resumer_seances, pour ne pas garder 2 Go en mémoire.

    Retourne:
        dict : dictionnaire avec la liste des séances (DataFrame) par cycliste
    """
    print("Liste des séances (data_cycliste/Sorties_velo et Sorties_autres)...")

    seances = lister_seances()
    print(f"   {len(seances)} séances trouvées")

    # Organiser les séances par cycliste dans un dictionnaire
    donnees = {
        cycliste: groupe.reset_index(drop=True)
        for cycliste, groupe in seances.groupby('cycliste')
    }

    print(f"   {len(donnees)} cyclistes trouvés")
    return donnees


# ==============================
# 2. CALCULS DE PUISSANCE
# ==============================

def preparer_seance(df_seance):
    """
    Prépare une séance : trie par temps (le nettoyage est fait par lire_seance)

    Paramètres:
        df_seance : DataFrame d'une séance individuelle

    Retourne:
        DataFrame préparé et intervalle de temps (dt)
    """
    # Trier par temps
    df = df_seance.sort_values('secs').copy()

    # Calculer le pas d'échantillonnage (généralement 1 seconde)
    if len(df) > 1:
        dt = df['secs'].diff().median()
        if pd.isna(dt) or dt <= 0:
            dt = 1.0
    else:
        dt = 1.0

    return df, dt


def meilleure_puissance(watts, dt, duree_s=1200):
    """
    Calcule la meilleure puissance moyenne sur une durée donnée
    (utilisé pour estimer la FTP à partir d'un effort de 20 minutes)

    Paramètres:
        watts : série de puissances
        dt : intervalle de temps entre les mesures (secondes)
        duree_s : durée de la fenêtre glissante (par défaut 1200s = 20 minutes)

    Retourne:
        float : meilleure puissance moyenne
    """
    n = round(duree_s / dt)

    # Si la séance est trop courte, on ne peut pas calculer
    if len(watts) < n:
        return np.nan

    # Calculer la moyenne glissante et prendre le maximum
    moyenne_glissante = watts.rolling(window=n, min_periods=n).mean()
    return moyenne_glissante.max()


def puissance_normalisee(watts, dt):
    """
    Calcule la puissance normalisée (NP - Normalized Power)

    La NP est une métrique qui reflète mieux la charge physiologique qu'une simple moyenne.
    Elle donne plus de poids aux efforts intenses.

    Formule : NP = racine_4(moyenne(puissance_moy_30s^4))

    Paramètres:
        watts : série de puissances
        dt : intervalle de temps entre les mesures

    Retourne:
        float : puissance normalisée
    """
    # Fenêtre de 30 secondes
    n = round(30 / dt)

    if len(watts) < n:
        return np.nan

    # 1. Calculer la moyenne glissante sur 30 secondes
    moy_30s = watts.rolling(window=n, min_periods=n).mean()

    # 2. Élever à la puissance 4
    moy_30s_puissance4 = moy_30s ** 4

    # 3. Calculer la moyenne de ces valeurs
    moyenne_puissance4 = moy_30s_puissance4.mean()

    # 4. Prendre la racine quatrième
    np_value = moyenne_puissance4 ** (1/4)

    return np_value


def resumer_seances(df_cycliste, parametres):
    """
    Résume chaque séance d'un cycliste : durée, puissances, travail total, temps par zone

    Les séances sans capteur de puissance (et les autres sports) sont gardées,
    avec les indicateurs de puissance à vide (NaN, null dans le JSON).

    Paramètres:
        df_cycliste : DataFrame avec la liste des séances d'un cycliste
        parametres : FTP par année (commun/parametres.json)

    Retourne:
        DataFrame avec une ligne par séance et ses indicateurs
    """
    resultats = []

    for _, s in df_cycliste.iterrows():
        # Lire et préparer la séance
        df_prep, dt = preparer_seance(lire_seance(s['fichier']))
        puissance = s['sport'] == 'velo' and a_puissance(df_prep)

        # Durée : somme des pas de temps, les pauses de plus de 10 s ne comptent pas
        duree_s = df_prep['dt'].sum()

        # Fréquence cardiaque moyenne (les pertes de signal sont déjà retirées)
        hr_moy = df_prep['hr'].mean() if a_fc(df_prep) else np.nan

        ligne = {
            'cycliste': s['cycliste'],
            'annee': s['annee'],
            'seance': s['seance'],
            'date': s['date'].strftime('%Y-%m-%d'),
            'sport': s['sport'],
            'poids_kg': s['poids_kg'],
            'duree_s': duree_s,
            'duree_h': duree_s / 3600,
            'a_puissance': puissance,
            'a_fc': a_fc(df_prep),
            'p_moy': np.nan,
            'np': np.nan,
            'mmp20': np.nan,
            'travail_kj': np.nan,
            'hr_moy': hr_moy
        }

        if puissance:
            ligne['p_moy'] = df_prep['watts'].mean()
            ligne['np'] = puissance_normalisee(df_prep['watts'], dt)
            ligne['mmp20'] = meilleure_puissance(df_prep['watts'], dt, duree_s=1200)
            ligne['travail_kj'] = (df_prep['watts'] * df_prep['dt']).sum() / 1000

            # Temps passé dans chaque zone de puissance (minutes)
            ftp = parametres[s['cycliste']]['ftp'].get(str(s['annee']))
            if ftp:
                zone = pd.cut(df_prep['watts'] / ftp, bins=BORNES_ZONES, labels=NOMS_ZONES, right=False)
                minutes = df_prep['dt'].groupby(zone).sum() / 60
                for i, nom in enumerate(NOMS_ZONES, start=1):
                    ligne[f'tp_z{i}'] = minutes.get(nom, 0.0)

        resultats.append(ligne)

    return pd.DataFrame(resultats)


# ==============================
# 3. CALCUL DE LA FTP ET DU TSS
# ==============================

def calculer_ftp(parametres):
    """
    Récupère la FTP (Functional Threshold Power) de chaque cycliste et chaque saison

    La FTP est estimée à 95% de la meilleure puissance sur 20 minutes de la saison.
    C'est la puissance maximale qu'un cycliste peut maintenir pendant environ 1 heure.
    Elle est calculée une seule fois pour tout le groupe par commun/parametres.py.

    Paramètres:
        parametres : contenu de commun/parametres.json

    Retourne:
        DataFrame avec la FTP par cycliste et par saison
    """
    print("FTP (seuil fonctionnel) lue dans commun/parametres.json...")

    ftp = pd.DataFrame([
        {'cycliste': c, 'annee': int(a), 'ftp': f}
        for c, p in parametres.items() for a, f in p['ftp'].items()
    ])

    # FTP = 95% de la meilleure puissance sur 20 minutes
    ftp['mmp20_saison'] = ftp['ftp'] / 0.95

    print("   FTP récupérée pour chaque cycliste/saison")
    return ftp


def calculer_tss(df_seances, df_ftp):
    """
    Calcule le TSS (Training Stress Score) pour chaque séance

    Le TSS combine la durée et l'intensité d'une séance.
    Une heure à la FTP = 100 TSS

    Formule : TSS = (durée_secondes × NP × IF) / (FTP × 3600) × 100
    Où IF (Intensity Factor) = NP / FTP

    Paramètres:
        df_seances : DataFrame avec toutes les séances
        df_ftp : DataFrame avec les FTP

    Retourne:
        DataFrame avec le TSS pour chaque séance
    """
    print("Calcul du TSS (Training Stress Score)...")

    # Joindre les FTP aux séances
    df = df_seances.merge(df_ftp[['cycliste', 'annee', 'ftp']],
                          on=['cycliste', 'annee'],
                          how='left')

    # Calculer l'IF (Intensity Factor)
    df['IF'] = df['np'] / df['ftp']

    # Calculer le TSS (vide pour les séances sans puissance)
    df['TSS'] = (df['duree_s'] * df['np'] * df['IF']) / (df['ftp'] * 3600) * 100

    # Calculer la FTP en W/kg (pour comparer les cyclistes entre eux)
    df['ftp_wkg'] = df['ftp'] / df['poids_kg']

    print("   TSS calculé pour toutes les séances avec puissance")
    return df


def calculer_zones_puissance(df_seances):
    """
    Calcule la répartition du temps passé dans chaque zone de puissance

    Les zones de Coggan :
    - Z1 Récupération : < 55% FTP
    - Z2 Endurance : 55-75% FTP
    - Z3 Tempo : 75-90% FTP
    - Z4 Seuil : 90-105% FTP
    - Z5 VO2max : 105-120% FTP
    - Z6 Anaérobie : > 120% FTP

    Paramètres:
        df_seances : DataFrame des séances, avec le temps par zone (tp_z1 ... tp_z6, en minutes)

    Retourne:
        DataFrame avec le pourcentage de temps par zone
    """
    print("Calcul des zones de puissance...")

    colonnes = [f'tp_z{i}' for i in range(1, 7)]
    df = df_seances[df_seances['a_puissance']]

    # Secondes par zone, par cycliste et par saison
    comptage = (df.groupby(['cycliste', 'annee'])[colonnes].sum() * 60).reset_index()
    comptage = comptage.melt(id_vars=['cycliste', 'annee'], var_name='zone', value_name='n')
    comptage['zone'] = comptage['zone'].map(dict(zip(colonnes, NOMS_ZONES)))

    # Calculer le pourcentage
    comptage['pct'] = comptage.groupby(['cycliste', 'annee'])['n'].transform(
        lambda x: x / x.sum() * 100
    )

    print("   Zones de puissance calculées")
    return comptage.sort_values(['cycliste', 'annee', 'zone']).reset_index(drop=True)


def extraire_date_seance(seance_nom):
    """
    Extrait la date et l'heure de début d'une séance depuis son nom de fichier
    Format attendu : AAAA_MM_JJ_HH_MM_SS

    Paramètres:
        seance_nom : nom de la séance

    Retourne:
        datetime ou None
    """
    match = re.search(r'(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})', seance_nom)
    if match:
        return datetime(
            int(match.group(1)),  # année
            int(match.group(2)),  # mois
            int(match.group(3)),  # jour
            int(match.group(4)),  # heure
            int(match.group(5)),  # minute
            int(match.group(6))   # seconde
        )
    return None


# ==============================
# 4. STATISTIQUES RÉSUMÉES
# ==============================

def calculer_stats_par_cycliste(df_tss):
    """
    Calcule des statistiques résumées par cycliste et par saison

    Paramètres:
        df_tss : DataFrame avec toutes les séances et leur TSS

    Retourne:
        DataFrame avec les statistiques agrégées
    """
    stats = df_tss.groupby(['cycliste', 'annee']).agg(
        n_seances=('seance', 'count'),
        n_seances_puissance=('a_puissance', 'sum'),
        TSS_moyen=('TSS', 'mean'),
        TSS_total=('TSS', 'sum'),
        IF_moyen=('IF', 'mean'),
        duree_totale_h=('duree_h', 'sum'),
        travail_total_kj=('travail_kj', 'sum')
    ).reset_index()

    return stats


def calculer_charge_hebdomadaire(df_tss):
    """
    Calcule la charge d'entraînement par semaine

    Paramètres:
        df_tss : DataFrame avec toutes les séances

    Retourne:
        DataFrame avec le TSS hebdomadaire
    """
    # Extraire les dates
    df_tss['date_debut'] = df_tss['seance'].apply(extraire_date_seance)

    # Filtrer les séances avec date valide
    df = df_tss.dropna(subset=['date_debut']).copy()

    # Calculer la semaine (du lundi au dimanche : 'W-SUN' = semaines qui finissent le dimanche)
    df['semaine'] = df['date_debut'].dt.to_period('W-SUN').dt.start_time

    # Agréger par semaine
    charge_hebdo = df.groupby(['cycliste', 'semaine']).agg(
        TSS=('TSS', 'sum'),
        heures=('duree_h', 'sum'),
        n_seances=('seance', 'count')
    ).reset_index()

    return charge_hebdo


# ==============================
# 5. CONTRÔLE QUALITÉ
# ==============================

def controle_qualite(df_tss):
    """
    Identifie les séances potentiellement problématiques

    Un IF > 1.05 sur une séance de plus d'une heure est suspect
    et peut indiquer une FTP sous-estimée.

    Paramètres:
        df_tss : DataFrame avec toutes les séances

    Retourne:
        DataFrame avec les séances suspectes
    """
    problematiques = df_tss[(df_tss['IF'] > 1.05) & (df_tss['duree_h'] > 1)]

    if len(problematiques) > 0:
        print(f"   {len(problematiques)} séances avec IF > 1.05 et durée > 1h (FTP potentiellement sous-estimée)")
    else:
        print("   Aucune anomalie détectée")

    return problematiques


# ==============================
# 6. EXPORT JSON (PAR CYCLISTE)
# ==============================

def exporter_json_par_cycliste(df_tss, df_ftp, df_zones, df_stats, charge_hebdo, parametres,
                               fichier_sortie=FICHIER_SORTIE):
    """
    Exporte toutes les données au format JSON structuré par cycliste

    Structure :
    {
      "metadata": {..., "parametres": {...}},
      "cyclistes": {
        "cyclist1": {
          "info": {...},
          "seances": [...],
          "ftp": {...},
          "zones_puissance": [...],
          "stats": {...},
          "charge_hebdomadaire": [...]
        },
        "cyclist2": {...}
      }
    }

    Paramètres:
        df_tss : séances avec TSS
        df_ftp : FTP par cycliste/saison
        df_zones : répartition par zones
        df_stats : statistiques par cycliste
        charge_hebdo : charge hebdomadaire
        parametres : FTP et FC max communes
        fichier_sortie : nom du fichier JSON
    """
    print(f"Export des données vers {fichier_sortie}...")

    # Préparer les dates pour la sérialisation JSON
    df_tss_export = df_tss.copy()
    df_tss_export['date_debut'] = df_tss_export['seance'].apply(extraire_date_seance)
    df_tss_export['date_debut'] = df_tss_export['date_debut'].astype(str)

    # Mêmes champs de base en tête pour toutes les parties
    base = ['seance', 'date', 'annee', 'sport', 'duree_s', 'duree_h', 'a_puissance', 'a_fc']
    df_tss_export = df_tss_export[base + [c for c in df_tss_export.columns if c not in base]]

    charge_hebdo_export = charge_hebdo.copy()
    charge_hebdo_export['semaine'] = charge_hebdo_export['semaine'].astype(str)

    # Créer la structure par cycliste
    donnees_json = {
        'metadata': {
            'titre': 'Charge d\'entraînement externe - Cyclistes',
            'date_export': datetime.now().isoformat(timespec='seconds'),
            'description': 'Données de charge externe (TSS, FTP, zones) organisées par cycliste',
            'parametres': parametres
        },
        'cyclistes': {}
    }

    # Obtenir la liste unique des cyclistes
    cyclistes = sorted(df_tss_export['cycliste'].unique())

    for cycliste in cyclistes:
        # Filtrer les données pour ce cycliste
        seances_cycliste = df_tss_export[df_tss_export['cycliste'] == cycliste]
        ftp_cycliste = df_ftp[df_ftp['cycliste'] == cycliste]
        zones_cycliste = df_zones[df_zones['cycliste'] == cycliste]
        stats_cycliste = df_stats[df_stats['cycliste'] == cycliste]
        charge_cycliste = charge_hebdo_export[charge_hebdo_export['cycliste'] == cycliste]

        # Informations générales du cycliste
        poids = seances_cycliste['poids_kg'].iloc[0] if len(seances_cycliste) > 0 else None
        annees = sorted(seances_cycliste['annee'].dropna().unique().tolist())

        # Structurer les données du cycliste
        donnees_json['cyclistes'][cycliste] = {
            'info': {
                'poids_kg': poids,
                'annees': annees,
                'nb_seances_total': len(seances_cycliste)
            },
            'seances': seances_cycliste.to_dict(orient='records'),
            'ftp': ftp_cycliste.to_dict(orient='records'),
            'zones_puissance': zones_cycliste.to_dict(orient='records'),
            'stats': stats_cycliste.to_dict(orient='records'),
            'charge_hebdomadaire': charge_cycliste.to_dict(orient='records')
        }

    # Fonction pour convertir les types numpy/pandas en types Python natifs
    def convertir_types(obj):
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, float)):
            return float(obj) if not np.isnan(obj) else None
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: convertir_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convertir_types(item) for item in obj]
        return obj

    # Convertir tous les types
    donnees_json = convertir_types(donnees_json)

    # Écrire le fichier JSON
    with open(fichier_sortie, 'w', encoding='utf-8') as f:
        json.dump(donnees_json, f, ensure_ascii=False, indent=2)

    print(f"   Export terminé : {fichier_sortie}")
    print(f"   {len(cyclistes)} cyclistes exportés")


# ==============================
# 7. FONCTION PRINCIPALE
# ==============================

def main():
    """
    Fonction principale qui orchestre tout le traitement
    """
    print("\n" + "="*60)
    print("    CALCUL DE LA CHARGE D'ENTRAÎNEMENT EXTERNE")
    print("="*60 + "\n")

    # Étape 1 : Lister les séances et lire les paramètres communs
    donnees = charger_donnees_cyclistes()
    parametres = charger_parametres()

    # Étape 2 : Résumer chaque séance
    print("\nRésumé des séances...")
    seances = pd.concat([resumer_seances(df, parametres) for df in donnees.values()], ignore_index=True)
    print(f"   {len(seances)} séances traitées, dont {int(seances['a_puissance'].sum())} avec puissance")

    # Étape 3 : FTP commune
    print()
    ftp = calculer_ftp(parametres)
    print(ftp[['cycliste', 'annee', 'ftp']].to_string(index=False))

    # Étape 4 : Calculer le TSS
    print()
    tss = calculer_tss(seances, ftp)

    # Étape 5 : Calculer les zones de puissance
    print()
    zones = calculer_zones_puissance(tss)

    # Étape 6 : Statistiques par cycliste (sorties vélo)
    velo = tss[tss['sport'] == 'velo']
    print("\nCalcul des statistiques par cycliste...")
    stats = calculer_stats_par_cycliste(velo)
    print(stats.to_string(index=False))

    # Étape 7 : Charge hebdomadaire (sorties vélo)
    print("\nCalcul de la charge hebdomadaire...")
    charge_hebdo = calculer_charge_hebdomadaire(velo.copy())
    print(f"   {len(charge_hebdo)} semaines analysées")

    # Étape 8 : Contrôle qualité
    print("\nContrôle qualité...")
    controle_qualite(tss)

    # Étape 9 : Export JSON (PAR CYCLISTE)
    print()
    exporter_json_par_cycliste(tss.drop(columns=['mmp20_saison'], errors='ignore'), ftp, zones, stats,
                               charge_hebdo, parametres)

    print("\n" + "="*60)
    print("    TRAITEMENT TERMINÉ AVEC SUCCÈS")
    print("="*60 + "\n")


# ==============================
# POINT D'ENTRÉE DU SCRIPT
# ==============================

if __name__ == "__main__":
    main()
