#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script principal pour lancer la gestion des bons de commande

Exemples d'utilisation:
    python scripts/run_bonne_commande.py --file data/input/excel/commandes.xlsx
    python scripts/run_bonne_commande.py --file data/input/excel/commandes.xlsx --headless
"""
import argparse
import sys
from pathlib import Path

# Ajouter le dossier parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.bonne_commande.bonne_commande_robot import BonneCommandeRobot
from core.logger import Logger

def main():
    parser = argparse.ArgumentParser(description='Gestion automatique des bons de commande Sage X3')
    
    parser.add_argument(
        '--file',
        type=str,
        required=True,
        help='Chemin du fichier Excel d\'entrée'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Exécuter en mode headless (sans interface)'
    )
    
    args = parser.parse_args()
    
    # Logger
    logger = Logger.get_logger('run_bonne_commande', 'scripts')
    
    try:
        logger.info("="*80)
        logger.info("🚀 DÉMARRAGE GESTION BONS DE COMMANDE")
        logger.info("="*80)
        logger.info(f"Fichier: {args.file}")
        logger.info(f"Headless: {args.headless}")
        
        # Créer le robot
        robot = BonneCommandeRobot(headless=args.headless)
        
        # Exécuter
        robot.run(excel_file=args.file)
        
        logger.info("="*80)
        logger.info("✅ TRAITEMENT TERMINÉ AVEC SUCCÈS")
        logger.info("="*80)
        
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Interruption par l'utilisateur")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
