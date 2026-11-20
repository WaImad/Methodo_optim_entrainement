"""
Script de calcul de la charge d'entraînement externe pour cyclistes
===================================================================

Ce script traite les données d'entraînement de cyclistes (fichiers CSV avec puissance et fréquence cardiaque)
et calcule les indicateurs de charge externe, notamment le TSS (Training Stress Score).

Sortie : Un fichier JSON contenant toutes les métriques pour une application de visualisation

Auteur : Équipe FARSI, ORLANDI, GEINDRE, COVA CORREA
Date : 2026-11-20
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import re
from datetime import datetime
import warnings

# Ignorer les avertissements pour un affichage plus propre
warnings.filterwarnings('ignore')


# ==============================
# 1. CHARGEMENT DES DONNÉES
# ==============================

def charger_donnees_cyclistes(dossier="data_cycliste"):
    """
    Charge tous les fichiers CSV d'entraînement des cyclistes

    Paramètres:
        dossier : chemin vers le dossier contenant les données

    Retourne:
        dict : dictionnaire avec un DataFrame par cycliste
    """
    print(f"🔄 Chargement des données depuis {dossier}...")

    # Trouver tous les fichiers CSV, en excluant les fichiers fc_repos
    dossier_path = Path(dossier)
    fichiers = [f for f in dossier_path.rglob("*.csv") if "fc_repos" not in f.name]

    print(f"   📁 {len(fichiers)} fichiers à charger")

    donnees_brutes = []

    for fichier in fichiers:
        try:
            # Lire le fichier CSV
            df = pd.read_csv(fichier)

            # Vérifier que le fichier contient bien des données
            if df.shape[1] < 2:
                continue

            # Extraire les informations du chemin du fichier
            chemin_str = str(fichier)

            # Identifiant du cycliste (ex: cyclist1, cyclist2...)
            cycliste_match = re.search(r'cyclist\d+', chemin_str)
            cycliste = cycliste_match.group(0) if cycliste_match else None

            # Poids du cycliste (ex: 70kg)
            poids_match = re.search(r'(\d+)kg', chemin_str)
            poids_kg = int(poids_match.group(1)) if poids_match else None

            # Année (ex: 2022)
            annee_match = re.search(r'/(\d{4})/', chemin_str)
            annee = int(annee_match.group(1)) if annee_match else None

            # Nom de la séance (nom du fichier sans extension)
            seance = fichier.stem

            # Ajouter les métadonnées au DataFrame
            df['cycliste'] = cycliste
            df['poids_kg'] = poids_kg
            df['annee'] = annee
            df['seance'] = seance

            donnees_brutes.append(df)

        except Exception as e:
            print(f"   ⚠️  Erreur lors du chargement de {fichier.name}: {e}")
            continue

    # Combiner toutes les données en un seul DataFrame
    df_complet = pd.concat(donnees_brutes, ignore_index=True)

    # Organiser les données par cycliste dans un dictionnaire
    donnees = {
        cycliste: groupe.reset_index(drop=True)
        for cycliste, groupe in df_complet.groupby('cycliste')
    }

    print(f"   ✅ {len(donnees)} cyclistes chargés")
    return donnees


# ==============================
# 2. CALCULS DE PUISSANCE
# ==============================

def preparer_seance(df_seance):
    """
    Prépare une séance : trie par temps, remplace les valeurs manquantes

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

    # Remplacer les puissances manquantes ou négatives par 0
    # (cela correspond à une roue libre ou une perte de signal)
    df['watts'] = df['watts'].fillna(0)
    df.loc[df['watts'] < 0, 'watts'] = 0

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


def resumer_seances(df_cycliste):
    """
    Résume chaque séance d'un cycliste : durée, puissances, travail total

    Paramètres:
        df_cycliste : DataFrame contenant toutes les séances d'un cycliste

    Retourne:
        DataFrame avec une ligne par séance et ses indicateurs
    """
    resultats = []

    # Grouper par séance
    for (cycliste, annee, seance, poids_kg), groupe in df_cycliste.groupby(
        ['cycliste', 'annee', 'seance', 'poids_kg']
    ):
        # Préparer la séance
        df_prep, dt = preparer_seance(groupe)

        # Calculer les indicateurs
        duree_s = len(df_prep) * dt
        p_moy = df_prep['watts'].mean()
        np = puissance_normalisee(df_prep['watts'], dt)
        mmp20 = meilleure_puissance(df_prep['watts'], dt, duree_s=1200)
        travail_kj = (df_prep['watts'] * dt).sum() / 1000

        # Fréquence cardiaque moyenne (en excluant les valeurs à 0 = perte de signal)
        if 'hr' in df_prep.columns:
            hr_valides = df_prep['hr'][df_prep['hr'] > 0]
            hr_moy = hr_valides.mean() if len(hr_valides) > 0 else float('nan')
        else:
            hr_moy = float('nan')

        resultats.append({
            'cycliste': cycliste,
            'annee': annee,
            'seance': seance,
            'poids_kg': poids_kg,
            'duree_s': duree_s,
            'duree_h': duree_s / 3600,
            'p_moy': p_moy,
            'np': np,
            'mmp20': mmp20,
            'travail_kj': travail_kj,
            'hr_moy': hr_moy
        })

    return pd.DataFrame(resultats)


# ==============================
# 3. CALCUL DE LA FTP ET DU TSS
# ==============================

def calculer_ftp(df_seances):
    """
    Estime la FTP (Functional Threshold Power) pour chaque cycliste et chaque saison

    La FTP est estimée à 95% de la meilleure puissance sur 20 minutes de la saison.
    C'est la puissance maximale qu'un cycliste peut maintenir pendant environ 1 heure.

    Paramètres:
        df_seances : DataFrame avec toutes les séances résumées

    Retourne:
        DataFrame avec la FTP par cycliste et par saison
    """
    print("📊 Calcul de la FTP (seuil fonctionnel)...")

    ftp = df_seances.groupby(['cycliste', 'annee']).agg(
        mmp20_saison=('mmp20', 'max')
    ).reset_index()

    # FTP = 95% de la meilleure puissance sur 20 minutes
    ftp['ftp'] = ftp['mmp20_saison'] * 0.95

    print("   ✅ FTP calculée pour chaque cycliste/saison")
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
    print("🎯 Calcul du TSS (Training Stress Score)...")

    # Joindre les FTP aux séances
    df = df_seances.merge(df_ftp[['cycliste', 'annee', 'ftp']],
                          on=['cycliste', 'annee'],
                          how='left')

    # Calculer l'IF (Intensity Factor)
    df['IF'] = df['np'] / df['ftp']

    # Calculer le TSS
    df['TSS'] = (df['duree_s'] * df['np'] * df['IF']) / (df['ftp'] * 3600) * 100

    # Calculer la FTP en W/kg (pour comparer les cyclistes entre eux)
    df['ftp_wkg'] = df['ftp'] / df['poids_kg']

    print("   ✅ TSS calculé pour toutes les séances")
    return df


def calculer_zones_puissance(donnees, df_ftp):
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
        donnees : dictionnaire avec les données brutes par cycliste
        df_ftp : DataFrame avec les FTP

    Retourne:
        DataFrame avec le pourcentage de temps par zone
    """
    print("🎨 Calcul des zones de puissance...")

    bornes = [-np.inf, 0.55, 0.75, 0.90, 1.05, 1.20, np.inf]
    noms = ['Z1 Récup', 'Z2 Endurance', 'Z3 Tempo', 'Z4 Seuil', 'Z5 VO2max', 'Z6 Anaérobie']

    resultats_zones = []

    for cycliste, df_cycliste in donnees.items():
        # S'assurer que annee est du bon type
        df_cycliste_copy = df_cycliste.copy()
        if 'annee' in df_cycliste_copy.columns:
            df_cycliste_copy['annee'] = pd.to_numeric(df_cycliste_copy['annee'], errors='coerce')

        # Joindre les FTP
        df = df_cycliste_copy.merge(df_ftp[['cycliste', 'annee', 'ftp']],
                                     on=['cycliste', 'annee'],
                                     how='inner')

        # Exclure les lignes sans données valides
        df = df.dropna(subset=['watts', 'ftp'])

        # Calculer le ratio puissance / FTP
        df['ratio_ftp'] = df['watts'] / df['ftp']

        # Assigner chaque seconde à une zone
        df['zone'] = pd.cut(df['ratio_ftp'], bins=bornes, labels=noms, right=False)

        # Compter le nombre de secondes par zone
        comptage = df.groupby(['cycliste', 'annee', 'zone']).size().reset_index(name='n')

        # Calculer le pourcentage
        comptage['pct'] = comptage.groupby(['cycliste', 'annee'])['n'].transform(
            lambda x: x / x.sum() * 100
        )

        resultats_zones.append(comptage)

    zones_df = pd.concat(resultats_zones, ignore_index=True)

    print("   ✅ Zones de puissance calculées")
    return zones_df


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

    # Calculer le numéro de semaine
    df['semaine'] = df['date_debut'].dt.to_period('W-MON').dt.start_time

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
        print(f"   ⚠️  {len(problematiques)} séances avec IF > 1.05 et durée > 1h (FTP potentiellement sous-estimée)")
    else:
        print("   ✅ Aucune anomalie détectée")

    return problematiques


# ==============================
# 6. EXPORT JSON
# ==============================

def exporter_json(df_tss, df_ftp, df_zones, df_stats, charge_hebdo, fichier_sortie="charge_externe.json"):
    """
    Exporte toutes les données au format JSON pour l'application de visualisation

    Paramètres:
        df_tss : séances avec TSS
        df_ftp : FTP par cycliste/saison
        df_zones : répartition par zones
        df_stats : statistiques par cycliste
        charge_hebdo : charge hebdomadaire
        fichier_sortie : nom du fichier JSON
    """
    print(f"💾 Export des données vers {fichier_sortie}...")

    # Préparer les dates pour la sérialisation JSON
    df_tss_export = df_tss.copy()
    df_tss_export['date_debut'] = df_tss_export['seance'].apply(extraire_date_seance)
    df_tss_export['date_debut'] = df_tss_export['date_debut'].astype(str)

    charge_hebdo_export = charge_hebdo.copy()
    charge_hebdo_export['semaine'] = charge_hebdo_export['semaine'].astype(str)

    # Créer la structure JSON
    donnees_json = {
        'metadata': {
            'titre': 'Charge d\'entraînement externe - Cyclistes',
            'date_export': datetime.now().isoformat(),
            'description': 'Données de charge externe (TSS, FTP, zones) pour application de visualisation'
        },
        'seances': df_tss_export.to_dict(orient='records'),
        'ftp': df_ftp.to_dict(orient='records'),
        'zones_puissance': df_zones.to_dict(orient='records'),
        'stats_cyclistes': df_stats.to_dict(orient='records'),
        'charge_hebdomadaire': charge_hebdo_export.to_dict(orient='records')
    }

    # Écrire le fichier JSON
    with open(fichier_sortie, 'w', encoding='utf-8') as f:
        json.dump(donnees_json, f, ensure_ascii=False, indent=2)

    print(f"   ✅ Export terminé : {fichier_sortie}")
    print(f"   📊 {len(df_tss_export)} séances exportées")


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

    # Étape 1 : Charger les données
    donnees = charger_donnees_cyclistes(dossier="data_cycliste")

    # Étape 2 : Résumer chaque séance
    print("\n📋 Résumé des séances...")
    seances = pd.concat([resumer_seances(df) for df in donnees.values()], ignore_index=True)
    print(f"   ✅ {len(seances)} séances traitées")

    # Étape 3 : Calculer la FTP
    print()
    ftp = calculer_ftp(seances)
    print(ftp[['cycliste', 'annee', 'ftp']].to_string(index=False))

    # Étape 4 : Calculer le TSS
    print()
    tss = calculer_tss(seances, ftp)

    # Étape 5 : Calculer les zones de puissance
    print()
    zones = calculer_zones_puissance(donnees, ftp)

    # Étape 6 : Statistiques par cycliste
    print("\n📈 Calcul des statistiques par cycliste...")
    stats = calculer_stats_par_cycliste(tss)
    print(stats.to_string(index=False))

    # Étape 7 : Charge hebdomadaire
    print("\n📅 Calcul de la charge hebdomadaire...")
    charge_hebdo = calculer_charge_hebdomadaire(tss)
    print(f"   ✅ {len(charge_hebdo)} semaines analysées")

    # Étape 8 : Contrôle qualité
    print("\n🔍 Contrôle qualité...")
    controle_qualite(tss)

    # Étape 9 : Export JSON
    print()
    exporter_json(tss, ftp, zones, stats, charge_hebdo)

    print("\n" + "="*60)
    print("    ✅ TRAITEMENT TERMINÉ AVEC SUCCÈS")
    print("="*60 + "\n")


# ==============================
# POINT D'ENTRÉE DU SCRIPT
# ==============================

if __name__ == "__main__":
    main()
