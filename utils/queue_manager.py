import json
import os
from datetime import datetime
import uuid
from pathlib import Path

# Chemin correct
BASE_DIR = Path(__file__).resolve().parent.parent
QUEUE_FILE = BASE_DIR / 'data' / 'queue' / 'tasks.json'

# S'assurer que le dossier existe
QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)

def add_task(file_path, email, task_type="bon_commande", societe=None):
    """Ajouter une tâche à la file

    Args:
        file_path: Chemin du fichier Excel
        email: Email du destinataire
        task_type: Type de tâche - "bon_commande" ou "receiption"
    """
    tasks = load_queue()

    # Valider le type de tâche
    valid_types = ["bon_commande", "receiption", "facturation", "regelement", "vairement", "imputation", "demmande_achat", "dff_annulation_control"]
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
    if (societe):
        task["societe"] = societe
    tasks.append(task)
    save_queue(tasks)
    print(f"Tâche ajoutée: {task['id']} (type: {task_type})")
    return task["id"]

def get_next_task(skip_types: list = None):
    """Récupérer la prochaine tâche en attente

    Args:
        skip_types: Liste de types de tâches à ignorer (ex: ['bon_commande'])
    """
    tasks = load_queue()
    skip_types = skip_types or []

    for task in tasks:
        if task["status"] == "pending":
            task_type = task.get("task_type", "bon_commande")
            if task_type not in skip_types:
                return task
    return None


def get_last_completed_time(task_type: str) -> datetime:
    """Récupérer le timestamp de la dernière tâche complétée pour un type donné

    Args:
        task_type: Type de tâche (ex: 'bon_commande')

    Returns:
        datetime ou None si aucune tâche complétée
    """
    tasks = load_queue()
    last_time = None

    for task in tasks:
        if (task.get("task_type") == task_type and
            task.get("status") == "completed" and
            task.get("completed_at")):
            try:
                completed_at = datetime.fromisoformat(task["completed_at"])
                if last_time is None or completed_at > last_time:
                    last_time = completed_at
            except (ValueError, TypeError):
                continue

    return last_time


def is_task_type_in_cooldown(task_type: str, cooldown_minutes: int = 30) -> tuple:
    """Vérifier si un type de tâche est en période de cooldown

    Args:
        task_type: Type de tâche à vérifier
        cooldown_minutes: Durée du cooldown en minutes

    Returns:
        tuple (is_in_cooldown: bool, remaining_minutes: float)
    """
    last_completed = get_last_completed_time(task_type)

    if last_completed is None:
        return False, 0

    elapsed = (datetime.now() - last_completed).total_seconds() / 60  # en minutes
    remaining = cooldown_minutes - elapsed

    if remaining > 0:
        return True, remaining

    return False, 0


def has_pending_tasks_of_type(task_type: str) -> bool:
    """Vérifier s'il y a des tâches en attente d'un certain type"""
    tasks = load_queue()
    for task in tasks:
        if task.get("task_type") == task_type and task.get("status") == "pending":
            return True
    return False

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