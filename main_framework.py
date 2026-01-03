# -*- coding: utf-8 -*-
"""
Script principal simplifié - Version Framework
Utilisation identique à main.py mais avec le framework
"""
import sys
from pathlib import Path

# Ajouter le dossier sage-x3-rpa au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent / 'sage-x3-rpa'))

from modules.lettrage.lettrage_robot import LettrageRobot

def main():
    # Configuration (comme dans votre main.py)
    URL = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FPREPROD%2F%24sessions%3Ff%3DLETTRAGE%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%2765059cf7-11e9-4b40-bac9-66ef183fb4e1~ep~%2764a56978-56ab-46f1-8d83-ed18f7fa6484~appConn~())"
    
    FICHIER_EXCEL = r"C:\Users\m.astitou\Desktop\selenuim\reglement a annuler.xlsx"
    
    # Créer et lancer le robot (comme avant)
    robot = LettrageRobot()
    
    try:
        robot.run(excel_file=FICHIER_EXCEL, url=URL)
        input("\n⏸️ Appuyez sur Entree pour fermer...")
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        input("\n⏸️ Appuyez sur Entree...")

if __name__ == "__main__":
    main()
