import json
import os
from datetime import datetime
import uuid
from pathlib import Path

# ✅ Chemin correct
BASE_DIR = Path(__file__).resolve().parent.parent
QUEUE_FILE = BASE_DIR / 'data' / 'queue' / 'tasks.json'

# S'assurer que le dossier existe
QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)

def add_task(file_path, email, task_type="bon_commande"):
    """Ajouter une tâche à la file

    Args:
        file_path: Chemin du fichier Excel
        email: Email du destinataire
        task_type: Type de tâche - "bon_commande" ou "receiption"
    """
    tasks = load_queue()

    # Valider le type de tâche
    valid_types = ["bon_commande", "receiption"]
    if task_type not in valid_types:
        raise ValueError(f"Type de tâche invalide. Doit être: {', '.join(valid_types)}")

    task = {
        "id": str(uuid.uuid4()),
        "status": "pending",
        "task_type": task_type,
        "file": file_path,
        "email": email,
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "completed_at": None
    }

    tasks.append(task)
    save_queue(tasks)
    print(f"✅ Tâche ajoutée: {task['id']} (type: {task_type})")
    return task["id"]

def get_next_task():
    """Récupérer la prochaine tâche en attente"""
    tasks = load_queue()
    for task in tasks:
        if task["status"] == "pending":
            return task
    return None

def update_task(task_id, status, error=None):
    """Mettre à jour le statut d'une tâche"""
    tasks = load_queue()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = status
            if status == "processing":
                task["started_at"] = datetime.now().isoformat()
            elif status in ["completed", "failed"]:
                task["completed_at"] = datetime.now().isoformat()
            if error:
                task["error"] = error
            break
    save_queue(tasks)

def load_queue():
    """Charger la file d'attente"""
    if not QUEUE_FILE.exists():
        return []
    try:
        with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_queue(tasks):
    """Sauvegarder la file d'attente"""
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)