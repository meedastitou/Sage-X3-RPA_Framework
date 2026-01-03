#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script pour ajouter une tâche à la file d'attente
Appelé par n8n
"""
import sys
import argparse
from pathlib import Path

# Ajouter le dossier sage-x3-rpa au path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent  # Remonte d'un niveau
sys.path.insert(0, str(project_root))

from utils.queue_manager import add_task


def main():
    parser = argparse.ArgumentParser(description='Ajouter une tâche RPA à la file')
    parser.add_argument('--file', required=True, help='Chemin du fichier Excel')
    parser.add_argument('--email', required=True, help='Email de l\'expéditeur')
    
    args = parser.parse_args()
    
    # Ajouter la tâche
    task_id = add_task(args.file, args.email)
    
    print(f"✅ Tâche ajoutée à la file: {task_id}")
    print(f"📄 Fichier: {args.file}")
    print(f"📧 Email: {args.email}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())