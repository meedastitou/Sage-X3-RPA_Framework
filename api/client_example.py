#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Client Python pour l'API Sage X3 RPA
Exemple d'utilisation de l'API via requests
"""
import requests
import time
import json
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"

class SageRPAClient:
    """Client Python pour l'API Sage X3 RPA"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip('/')
    
    def upload_file(self, file_path: str) -> dict:
        """
        Upload un fichier Excel
        
        Returns:
            dict avec path, filename, etc.
        """
        print(f" Upload du fichier: {file_path}")
        
        with open(file_path, 'rb') as f:
            response = requests.post(
                f"{self.base_url}/api/upload",
                files={'file': f}
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"Fichier uploadé: {result['saved_as']}")
            return result
        else:
            raise Exception(f"Erreur upload: {response.text}")
    
    def trigger_lettrage(self, excel_file: str, headless: bool = False, url: str = None) -> str:
        """
        Déclencher le lettrage
        
        Returns:
            task_id
        """
        print(f"Déclenchement lettrage...")
        
        payload = {
            'excel_file': excel_file,
            'headless': headless
        }
        
        if url:
            payload['url'] = url
        
        response = requests.post(
            f"{self.base_url}/api/lettrage",
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            task_id = result['task_id']
            print(f"Tâche créée: {task_id}")
            return task_id
        else:
            raise Exception(f"Erreur déclenchement: {response.text}")
    
    def trigger_bonne_commande(self, excel_file: str, headless: bool = False) -> str:
        """
        Déclencher les bons de commande
        
        Returns:
            task_id
        """
        print(f"Déclenchement bonne commande...")
        
        payload = {
            'excel_file': excel_file,
            'headless': headless
        }
        
        response = requests.post(
            f"{self.base_url}/api/bonne-commande",
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            task_id = result['task_id']
            print(f"Tâche créée: {task_id}")
            return task_id
        else:
            raise Exception(f"Erreur déclenchement: {response.text}")
    
    def get_task_status(self, task_id: str) -> dict:
        """Récupérer le statut d'une tâche"""
        response = requests.get(f"{self.base_url}/api/task/{task_id}")
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Erreur récupération statut: {response.text}")
    
    def wait_for_completion(self, task_id: str, poll_interval: int = 5) -> dict:
        """
        Attendre la fin d'une tâche (polling)
        
        Args:
            task_id: ID de la tâche
            poll_interval: Intervalle de vérification (secondes)
        
        Returns:
            Résultat final de la tâche
        """
        print(f"⏳ Attente de la fin de la tâche {task_id}...")
        
        while True:
            status = self.get_task_status(task_id)
            
            print(f" Statut: {status['status']}")
            
            if status['status'] == 'completed':
                print(f"Tâche terminée avec succès!")
                print(f" Résultats: {json.dumps(status['result'], indent=2)}")
                return status
            
            elif status['status'] == 'failed':
                print(f" Tâche échouée: {status['error']}")
                return status
            
            time.sleep(poll_interval)
    
    def list_tasks(self, module: str = None, status: str = None) -> dict:
        """Lister les tâches"""
        params = {}
        if module:
            params['module'] = module
        if status:
            params['status'] = status
        
        response = requests.get(f"{self.base_url}/api/tasks", params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Erreur liste tâches: {response.text}")


# ============================================================================
# EXEMPLES D'UTILISATION
# ============================================================================

def exemple_lettrage_simple():
    """Exemple 1: Lettrage simple avec fichier local"""
    print("="*80)
    print("📋 EXEMPLE 1: Lettrage Simple")
    print("="*80)
    
    client = SageRPAClient()
    
    # Chemin du fichier Excel
    excel_file = r"C:\Users\m.astitou\Desktop\selenuim\reglement a annuler.xlsx"
    
    # Déclencher le lettrage
    task_id = client.trigger_lettrage(excel_file, headless=False)
    
    # Attendre la fin
    result = client.wait_for_completion(task_id)
    
    print("\n" + "="*80)
    print("EXEMPLE 1 TERMINÉ")
    print("="*80)


def exemple_upload_puis_lettrage():
    """Exemple 2: Upload fichier puis lettrage"""
    print("="*80)
    print("📋 EXEMPLE 2: Upload + Lettrage")
    print("="*80)
    
    client = SageRPAClient()
    
    # 1. Upload le fichier
    local_file = r"C:\Users\m.astitou\Desktop\selenuim\reglement a annuler.xlsx"
    upload_result = client.upload_file(local_file)
    
    # 2. Déclencher le lettrage avec le fichier uploadé
    task_id = client.trigger_lettrage(upload_result['path'], headless=False)
    
    # 3. Attendre la fin
    result = client.wait_for_completion(task_id)
    
    print("\n" + "="*80)
    print("EXEMPLE 2 TERMINÉ")
    print("="*80)


def exemple_bonne_commande():
    """Exemple 3: Bonne de commande"""
    print("="*80)
    print("📋 EXEMPLE 3: Bonne de Commande")
    print("="*80)
    
    client = SageRPAClient()
    
    # Fichier Excel
    excel_file = r"C:\path\to\commandes.xlsx"
    
    # Déclencher
    task_id = client.trigger_bonne_commande(excel_file, headless=True)
    
    # Attendre la fin
    result = client.wait_for_completion(task_id)
    
    print("\n" + "="*80)
    print("EXEMPLE 3 TERMINÉ")
    print("="*80)


def exemple_lister_taches():
    """Exemple 4: Lister toutes les tâches"""
    print("="*80)
    print("📋 EXEMPLE 4: Liste des Tâches")
    print("="*80)
    
    client = SageRPAClient()
    
    # Lister toutes les tâches
    tasks = client.list_tasks()
    
    print(f"\n {tasks['total']} tâche(s) totale(s)\n")
    
    for task in tasks['tasks']:
        print(f"  • {task['task_id'][:8]}... | {task['module']:15} | {task['status']}")
    
    print("\n" + "="*80)
    print("EXEMPLE 4 TERMINÉ")
    print("="*80)


def exemple_async_multiple():
    """Exemple 5: Lancer plusieurs tâches en parallèle"""
    print("="*80)
    print("📋 EXEMPLE 5: Tâches Multiples en Parallèle")
    print("="*80)
    
    client = SageRPAClient()
    
    # Lancer plusieurs tâches
    task_ids = []
    
    files = [
        r"C:\path\to\file1.xlsx",
        r"C:\path\to\file2.xlsx",
        r"C:\path\to\file3.xlsx"
    ]
    
    for file in files:
        try:
            task_id = client.trigger_lettrage(file, headless=True)
            task_ids.append(task_id)
        except Exception as e:
            print(f" Erreur fichier {file}: {e}")
    
    print(f"\n{len(task_ids)} tâche(s) lancée(s)")
    
    # Attendre que toutes soient terminées
    print("\n⏳ Attente de la fin de toutes les tâches...")
    
    while True:
        all_done = True
        
        for task_id in task_ids:
            status = client.get_task_status(task_id)
            if status['status'] in ['pending', 'running']:
                all_done = False
                break
        
        if all_done:
            break
        
        time.sleep(10)
    
    # Afficher les résultats
    print("\n RÉSULTATS:")
    for task_id in task_ids:
        status = client.get_task_status(task_id)
        print(f"  • {task_id[:8]}... → {status['status']}")
    
    print("\n" + "="*80)
    print("EXEMPLE 5 TERMINÉ")
    print("="*80)


if __name__ == "__main__":
    print("\n" + "="*80)
    print("CLIENT API SAGE X3 RPA - EXEMPLES")
    print("="*80)
    
    print("\nChoisissez un exemple:")
    print("1. Lettrage simple")
    print("2. Upload + Lettrage")
    print("3. Bonne de commande")
    print("4. Lister les tâches")
    print("5. Tâches multiples en parallèle")
    
    choix = input("\nVotre choix (1-5): ")
    
    try:
        if choix == "1":
            exemple_lettrage_simple()
        elif choix == "2":
            exemple_upload_puis_lettrage()
        elif choix == "3":
            exemple_bonne_commande()
        elif choix == "4":
            exemple_lister_taches()
        elif choix == "5":
            exemple_async_multiple()
        else:
            print(" Choix invalide")
    
    except Exception as e:
        print(f"\n Erreur: {e}")
        import traceback
        traceback.print_exc()
    
    input("\n⏸️ Appuyez sur Entrée pour fermer...")
