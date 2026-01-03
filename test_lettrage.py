#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de test simple - Version finale du framework
"""
import sys
from pathlib import Path

# Ajouter le dossier parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.lettrage.lettrage_robot import LettrageRobot
from core.logger import Logger

# URL du module lettrage
URL = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FPREPROD%2F%24sessions%3Ff%3DLETTRAGE%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%2765059cf7-11e9-4b40-bac9-66ef183fb4e1~ep~%2764a56978-56ab-46f1-8d83-ed18f7fa6484~appConn~())"

# Fichier Excel - MODIFIEZ CE CHEMIN
FICHIER_EXCEL = r"C:\Users\m.astitou\Desktop\selenuim\reglement a annuler.xlsx"

def main():
    logger = Logger.get_logger('test', 'scripts')
    
    try:
        logger.info("="*80)
        logger.info("🧪 TEST DU FRAMEWORK SAGE X3 RPA")
        logger.info("="*80)
        
        # Créer le robot
        robot = LettrageRobot(headless=False)
        
        # Exécuter
        robot.run(
            excel_file=FICHIER_EXCEL,
            url=URL
        )
        
        logger.info("="*80)
        logger.info("✅ TEST TERMINÉ")
        logger.info("="*80)
        
        input("\n⏸️ Appuyez sur Entrée pour fermer...")
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        input("\n⏸️ Appuyez sur Entrée...")

if __name__ == '__main__':
    main()
