#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script principal pour lancer le Receiption Sage X3

Exemples d'utilisation:
    python scripts/run_receiption.py --file data/input/excel/fournisseurs.xlsx
    python scripts/run_receiption.py --file data/input/excel/fournisseurs.xlsx --headless
"""
import argparse
import sys
from pathlib import Path

# Ajouter le dossier parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.receiption.ReceiptionRobot import ReceiptionRobot
from core.logger import Logger

# URL par défaut du module réception Sage X3
DEFAULT_URL = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESPTV%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%27xxx~ep~%27xxx~appConn~())"
def main():
    parser = argparse.ArgumentParser(description='Réception automatique Sage X3')
    
    parser.add_argument(
        '--file',
        type=str,
        required=True,
        help='Chemin du fichier Excel d\'entrée'
    )
    
    parser.add_argument(
        '--url',
        type=str,
        default=DEFAULT_URL,
        help='URL du module de réception Sage X3 (optionnel)'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Exécuter en mode headless (sans interface)'
    )
    
    args = parser.parse_args()
    
    # Logger
    logger = Logger.get_logger('run_receiption', 'scripts')
    
    try:
        logger.info("="*80)
        logger.info("🚀 DÉMARRAGE RÉCEPTION SAGE X3")
        logger.info("="*80)
        logger.info(f"Fichier: {args.file}")
        logger.info(f"Headless: {args.headless}")
        
        # Créer le robot
        robot = ReceiptionRobot(headless=args.headless)
        
        # Exécuter
        robot.run(
            excel_file=args.file,
            url=args.url
        )
        
        logger.info("="*80)
        logger.info("✅ RÉCEPTION TERMINÉE AVEC SUCCÈS")
        logger.info("="*80)
        
        
    except KeyboardInterrupt:
        logger.warning("⚠️ Interruption par l'utilisateur")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
