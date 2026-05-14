# -*- coding: utf-8 -*-
"""
API REST pour déclencher les robots RPA Sage X3
FastAPI avec endpoints pour chaque module
Architecture Queue-Based pour traitement asynchrone
"""
import sys
from pathlib import Path

# Ajouter le répertoire racine au path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import threading
import uuid
from datetime import datetime
import shutil
import pandas as pd

# Importer les robots
from modules.lettrage.lettrage_robot import LettrageRobot
from modules.bonne_commande.bonne_commande_robot import BonneCommandeRobot
from modules.imputation.ImputationRobot import ImputationRobot
from core.logger import Logger

# Importer le queue manager
from utils.queue_manager import add_task, load_queue

app = FastAPI(
    title="Sage X3 RPA API",
    description="API REST pour déclencher les robots d'automatisation Sage X3",
    version="1.0.0"
)

# Logger
logger = Logger.get_logger('api', 'api')

# Stockage des tâches en cours
tasks_status: Dict[str, Dict[str, Any]] = {}

# Dossier pour les fichiers uploadés
UPLOAD_DIR = Path("data/input/excel/api_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# MODÈLES DE DONNÉES
# ============================================================================

class LettrageRequest(BaseModel):
    """Requête pour déclencher le lettrage"""
    excel_file: str
    url: Optional[str] = None
    headless: bool = False


class BonneCommandeRequest(BaseModel):
    """Requête pour déclencher les bons de commande"""
    excel_file: str
    headless: bool = False


class BonneCommandeDataRequest(BaseModel):
    """Requête pour déclencher les bons de commande avec données JSON"""
    donnees: List[Dict[str, Any]]
    email_expediteur: str
    headless: bool = True


class FacturationDataRequest(BaseModel):
    """Requête pour déclencher la facturation avec données JSON"""
    donnees: List[Dict[str, Any]]
    email_expediteur: str
    headless: bool = True


class RegelementDataRequest(BaseModel):
    """Requête pour déclencher le règlement avec données JSON"""
    donnees: List[Dict[str, Any]]
    email_expediteur: str
    headless: bool = True


class ReceiptionDataRequest(BaseModel):
    """Requête pour déclencher la réception avec données JSON"""
    donnees: List[Dict[str, Any]]
    email_expediteur: str
    headless: bool = True


class ImputationDataRequest(BaseModel):
    """Requête pour déclencher l'imputation avec données JSON"""
    donnees: List[Dict[str, Any]]
    email_expediteur: str
    headless: bool = True

class DemmandAchatDataRequest(BaseModel):
    """Requête pour déclencher la demande d'achat avec données JSON"""
    donnees: List[Dict[str, Any]]
    email_expediteur: str
    headless: bool = True

class TaskStatus(BaseModel):
    """Statut d'une tâche"""
    task_id: str
    status: str  # pending, running, completed, failed
    module: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================================
# FONCTIONS D'EXÉCUTION EN ARRIÈRE-PLAN
# ============================================================================

def execute_lettrage(task_id: str, excel_file: str, url: str, headless: bool):
    """Exécuter le lettrage en arrière-plan"""
    try:
        tasks_status[task_id]['status'] = 'running'
        tasks_status[task_id]['started_at'] = datetime.now().isoformat()
        
        logger.info(f"Démarrage tâche lettrage: {task_id}")
        
        # Créer le robot
        robot = LettrageRobot(headless=headless)
        
        # Exécuter
        robot.run(excel_file=excel_file, url=url)
        
        # Récupérer les résultats
        summary = robot.generate_summary()
        
        tasks_status[task_id]['status'] = 'completed'
        tasks_status[task_id]['completed_at'] = datetime.now().isoformat()
        tasks_status[task_id]['result'] = {
            'total': summary.get('total', 0),
            'succes': summary.get('succes', 0),
            'echecs': summary.get('echecs', 0),
            'rapport': str(robot.rapport_path) if robot.rapport_path else None
        }
        
        logger.info(f"Tâche lettrage terminée: {task_id}")
        
    except Exception as e:
        logger.error(f" Erreur tâche lettrage {task_id}: {e}")
        tasks_status[task_id]['status'] = 'failed'
        tasks_status[task_id]['completed_at'] = datetime.now().isoformat()
        tasks_status[task_id]['error'] = str(e)


def execute_bonne_commande(task_id: str, excel_file: str, headless: bool):
    """Exécuter les bons de commande en arrière-plan"""
    try:
        tasks_status[task_id]['status'] = 'running'
        tasks_status[task_id]['started_at'] = datetime.now().isoformat()
        
        logger.info(f"Démarrage tâche bonne commande: {task_id}")
        
        # Créer le robot
        robot = BonneCommandeRobot(headless=headless)
        
        # Exécuter
        robot.run(excel_file=excel_file)
        
        # Récupérer les résultats
        summary = robot.generate_summary()
        
        tasks_status[task_id]['status'] = 'completed'
        tasks_status[task_id]['completed_at'] = datetime.now().isoformat()
        tasks_status[task_id]['result'] = {
            'total': summary.get('total', 0),
            'succes': summary.get('succes', 0),
            'echecs': summary.get('echecs', 0),
            'rapport': str(robot.rapport_path) if robot.rapport_path else None
        }
        
        logger.info(f"Tâche bonne commande terminée: {task_id}")
        
    except Exception as e:
        logger.error(f" Erreur tâche bonne commande {task_id}: {e}")
        tasks_status[task_id]['status'] = 'failed'
        tasks_status[task_id]['completed_at'] = datetime.now().isoformat()
        tasks_status[task_id]['error'] = str(e)


# ============================================================================
# FONCTIONS UTILITAIRES QUEUE
# ============================================================================

def save_dataframe_to_excel(donnees: List[Dict[str, Any]], email_expediteur: str) -> str:
    """
    Convertir les données JSON en fichier Excel temporaire

    Args:
        donnees: Liste de dictionnaires contenant les données

    Returns:
        Chemin du fichier Excel créé
    """
    # Créer le DataFrame
    df = pd.DataFrame(donnees)
    
    # Ajouter la colonne email_expediteur à chaque ligne
    df['email_expediteur'] = email_expediteur
    
    # Générer un nom de fichier unique
    filename = f"api_data_BC_{uuid.uuid4()}.xlsx"
    file_path = UPLOAD_DIR / filename

    # Sauvegarder en Excel
    df.to_excel(file_path, index=False)

    logger.info(f" Données JSON converties en Excel: {file_path}")

    return str(file_path)


def save_facturation_to_excel(donnees: List[Dict[str, Any]], email_expediteur: str) -> str:
    """
    Convertir les données JSON facturation en fichier Excel temporaire

    Args:
        donnees: Liste de dictionnaires avec les colonnes: Code, DFF, FactureFrs, Date, BR
        email_expediteur: Email de l'expéditeur

    Returns:
        Chemin du fichier Excel créé
    """
    df = pd.DataFrame(donnees)

    # Ajouter la colonne email_expediteur
    df['email_expediteur'] = email_expediteur

    # Générer un nom de fichier unique
    filename = f"api_data_FACT_{uuid.uuid4()}.xlsx"
    file_path = UPLOAD_DIR / filename

    df.to_excel(file_path, index=False)

    logger.info(f" Données facturation converties en Excel: {file_path}")

    return str(file_path)


def save_regelement_to_excel(donnees: List[Dict[str, Any]], email_expediteur: str) -> str:
    """
    Convertir les données JSON règlement en fichier Excel temporaire

    Args:
        donnees: Liste de dictionnaires avec colonnes: Code_Frs, N_Facture, Refference, Montant, TVA, type_regelement
        email_expediteur: Email de l'expéditeur

    Returns:
        Chemin du fichier Excel créé
    """
    df = pd.DataFrame(donnees)

    # Ajouter la colonne email_expediteur
    df['email_expediteur'] = email_expediteur

    # Générer un nom de fichier unique
    filename = f"api_data_REG_{uuid.uuid4()}.xlsx"
    file_path = UPLOAD_DIR / filename

    df.to_excel(file_path, index=False)

    logger.info(f" Données règlement converties en Excel: {file_path}")

    return str(file_path)


def save_imputation_to_excel(donnees: List[Dict[str, Any]], email_expediteur: str) -> str:
    """
    Convertir les données JSON imputation en fichier Excel temporaire

    Colonnes requises: CodeFrs, N_BC, Reglement, Facture
    """
    df = pd.DataFrame(donnees)
    df['email_expediteur'] = email_expediteur
    filename = f"api_data_IMP_{uuid.uuid4()}.xlsx"
    file_path = UPLOAD_DIR / filename
    df.to_excel(file_path, index=False)
    logger.info(f" Données imputation converties en Excel: {file_path}")
    return str(file_path)


def save_receiption_to_excel(donnees: List[Dict[str, Any]], email_expediteur: str) -> str:
    """
    Convertir les données JSON réception en fichier Excel temporaire

    Args:
        donnees: Liste de dictionnaires avec colonnes:
                 CodeFrs, BLFrs, DateBC, N_BC, CodeArticle, Quantite,
                 N_B_transport, Matricule, Poids, Marque, observation
        email_expediteur: Email de l'expéditeur

    Returns:
        Chemin du fichier Excel créé
    """
    df = pd.DataFrame(donnees)

    # Ajouter la colonne email_expediteur
    df['email_expediteur'] = email_expediteur

    # Générer un nom de fichier unique
    filename = f"api_data_REC_{uuid.uuid4()}.xlsx"
    file_path = UPLOAD_DIR / filename

    df.to_excel(file_path, index=False)

    logger.info(f" Données réception converties en Excel: {file_path}")

    return str(file_path)


def save_da_to_excel(donnees: List[Dict[str, Any]], email_expediteur: str) -> str:
    """
    Convertir les données JSON demande d'achat en fichier Excel temporaire
    observation, lignes[code_sage, effectif] => {
                                                observation, code_sage, effectif,
                                                observation, code_sage, effectif,
                                                }
    Args:
        donnees: Liste de dictionnaires avec colonnes:
                  observation, lignes[code_sage, effectif]
        email_expediteur: Email de l'expéditeur
    Returns:    
        Chemin du fichier Excel créé
    """

    # Liste pour stocker les lignes aplaties
    rows = []

    # Parcourir chaque dictionnaire dans donnees
    for item in donnees:
        observation = item.get('observation', '')
        lignes = item.get('lignes', [])
        
        # Pour chaque ligne, créer une nouvelle ligne avec l'observation
        for ligne in lignes:
            row = {
                'Demandeur': "EL ABBADI Abdelaziz",
                'Observation': observation,
                'code_article': ligne.get('code_sage', ''),
                'quantite': ligne.get('effectif', 0)
            }
            rows.append(row)
    
    # Ajouter la colonne email_expediteur
    df = pd.DataFrame(rows)
    df['email_expediteur'] = email_expediteur

    # Générer un nom de fichier unique
    filename = f"api_data_DA_{uuid.uuid4()}.xlsx"
    file_path = UPLOAD_DIR / filename   

    df.to_excel(file_path, index=False)

    logger.info(f" Données demande d'achat converties en Excel: {file_path}")

    return str(file_path)


# ============================================================================
# ENDPOINTS API
# ============================================================================

@app.get("/")
async def root():
    """Page d'accueil de l'API"""
    return {
        "message": "Sage X3 RPA API",
        "version": "1.0.0",
        "endpoints": {
            "lettrage": "/api/lettrage",
            "bonne_commande": "/api/bonne-commande",
            "bonne_commande_data": "/api/bonne-commande/data",
            "facturation_data": "/api/facturation/data",
            "regelement_data": "/api/regelement/data",
            "receiption_data": "/api/receiption/data",
            "imputation_data": "/api/imputation/data",
            "upload": "/api/upload",
            "status": "/api/task/{task_id}",
            "tasks": "/api/tasks"
        }
    }


@app.get("/health")
async def health():
    """Vérifier la santé de l'API"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/lettrage", response_model=TaskStatus)
async def trigger_lettrage(request: LettrageRequest, background_tasks: BackgroundTasks):
    """
    Déclencher le robot de lettrage
    
    Exemple:
    ```json
    {
        "excel_file": "C:\\path\\to\\file.xlsx",
        "url": "http://...",
        "headless": false
    }
    ```
    """
    # Vérifier que le fichier existe
    if not os.path.exists(request.excel_file):
        raise HTTPException(status_code=404, detail=f"Fichier non trouvé: {request.excel_file}")
    
    # Générer un ID de tâche unique
    task_id = str(uuid.uuid4())
    
    # URL par défaut si non fournie
    url = request.url or "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FPREPROD%2F%24sessions%3Ff%3DLETTRAGE%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%2765059cf7-11e9-4b40-bac9-66ef183fb4e1~ep~%2764a56978-56ab-46f1-8d83-ed18f7fa6484~appConn~())"
    
    # Initialiser le statut
    tasks_status[task_id] = {
        'task_id': task_id,
        'status': 'pending',
        'module': 'lettrage',
        'started_at': None,
        'completed_at': None,
        'result': None,
        'error': None
    }
    
    # Lancer en arrière-plan
    thread = threading.Thread(
        target=execute_lettrage,
        args=(task_id, request.excel_file, url, request.headless)
    )
    thread.start()
    
    logger.info(f"📋 Tâche lettrage créée: {task_id}")
    
    return TaskStatus(**tasks_status[task_id])


@app.post("/api/bonne-commande", response_model=TaskStatus)
async def trigger_bonne_commande(request: BonneCommandeRequest, background_tasks: BackgroundTasks):
    """
    Déclencher le robot de bonne de commande
    
    Exemple:
    ```json
    {
        "excel_file": "C:\\path\\to\\commandes.xlsx",
        "headless": false
    }
    ```
    """
    # Vérifier que le fichier existe
    if not os.path.exists(request.excel_file):
        raise HTTPException(status_code=404, detail=f"Fichier non trouvé: {request.excel_file}")
    
    # Générer un ID de tâche unique
    task_id = str(uuid.uuid4())
    
    # Initialiser le statut
    tasks_status[task_id] = {
        'task_id': task_id,
        'status': 'pending',
        'module': 'bonne_commande',
        'started_at': None,
        'completed_at': None,
        'result': None,
        'error': None
    }
    
    # Lancer en arrière-plan
    thread = threading.Thread(
        target=execute_bonne_commande,
        args=(task_id, request.excel_file, request.headless)
    )
    thread.start()
    
    logger.info(f"📋 Tâche bonne commande créée: {task_id}")

    return TaskStatus(**tasks_status[task_id])


@app.post("/api/bonne-commande/data", response_model=TaskStatus)
async def trigger_bonne_commande_from_data(request: BonneCommandeDataRequest):
    """
    Déclencher une tâche bonne commande avec données JSON
    Les données sont converties en Excel et enqueued pour le worker

    Exemple:
    ```json
    {
        "donnees": [
            {
                "Numero_DA": "DA170753",
                "Acheteur": "RACH",
                "Code_Fournisseur": "T1398",
                "Email_Fournisseur": "exemple1@fournisseur1.com",
                "TEL_Fournisseu": "2126 00 00 00 00",
                "Code_Article": "A00001",
                "Montant": 20,
                "Marque": "DELL",
                "Affaire": ""
            }
        ],
        "email_expediteur": "cyber.analyst@ibel-annour.ma",
        "headless": false
    }
    ```
    """
    # Valider email
    if not request.email_expediteur:
        raise HTTPException(status_code=400, detail="email_expediteur est requis")

    # Convertir JSON → Excel
    excel_file = save_dataframe_to_excel(request.donnees, request.email_expediteur)

    # Enqueue la tâche
    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="bon_commande"
    )

    # Retourner le statut de la tâche enqueued
    queue_tasks = load_queue()
    task = next((t for t in queue_tasks if t['id'] == task_id), None)

    logger.info(f"📋 Tâche bonne commande (JSON) enqueued: {task_id}")

    return TaskStatus(
        task_id=task_id,
        status='pending',
        module='bonne_commande_api',
        started_at=None,
        completed_at=None,
        result=None,
        error=None
    )


@app.post("/api/facturation/data", response_model=TaskStatus)
async def trigger_facturation_from_data(request: FacturationDataRequest):
    """
    Déclencher une tâche facturation avec données JSON
    Les données sont converties en Excel et enqueued pour le worker

    Colonnes requises: Code, DFF, FactureFrs, Date, BR
    Colonne optionnelle: Nom

    Exemple:
    ```json
    {
        "donnees": [
            {
                "Code": "T1398",
                "DFF": "DFF12345",
                "FactureFrs": "FAC001",
                "Date": "15/01/2026",
                "BR": "BR189847",
                "Nom": "Fournisseur ABC"
            }
        ],
        "email_expediteur": "user@example.com",
        "headless": true
    }
    ```
    """
    # Valider email
    if not request.email_expediteur:
        raise HTTPException(status_code=400, detail="email_expediteur est requis")

    # Valider les colonnes requises
    required_columns = ['Code', 'DFF', 'FactureFrs', 'Date', 'BR']
    if request.donnees:
        first_row = request.donnees[0]
        missing = [col for col in required_columns if col not in first_row]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Colonnes manquantes: {', '.join(missing)}. Requises: {', '.join(required_columns)}"
            )

    # Convertir JSON → Excel
    excel_file = save_facturation_to_excel(request.donnees, request.email_expediteur)

    # Enqueue la tâche
    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="facturation"
    )

    logger.info(f"📋 Tâche facturation (JSON) enqueued: {task_id}")

    return TaskStatus(
        task_id=task_id,
        status='pending',
        module='facturation',
        started_at=None,
        completed_at=None,
        result=None,
        error=None
    )


@app.post("/api/regelement/data", response_model=TaskStatus)
async def trigger_regelement_from_data(request: RegelementDataRequest):
    """
    Déclencher une tâche règlement avec données JSON
    Les données sont converties en Excel et enqueued pour le worker

    Colonnes requises: Code_Frs, N_Facture, Refference, Montant, TVA, type_regelement
    - type_regelement: 1 = Effet à payer, 2 = Chèques émis

    Exemple:
    ```json
    {
        "donnees": [
            {
                "Code_Frs": "T1398",
                "N_Facture": "FF123456",
                "Refference": "REF001",
                "Montant": "15000.00",
                "TVA": "300.00",
                "type_regelement": 1
            }
        ],
        "email_expediteur": "user@example.com",
        "headless": true
    }
    ```
    """
    # Valider email
    if not request.email_expediteur:
        raise HTTPException(status_code=400, detail="email_expediteur est requis")

    # Valider les colonnes requises
    required_columns = ['Code_Frs', 'N_Facture', 'Refference', 'Montant', 'TVA', 'type_regelement']
    if request.donnees:
        first_row = request.donnees[0]
        missing = [col for col in required_columns if col not in first_row]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Colonnes manquantes: {', '.join(missing)}. Requises: {', '.join(required_columns)}"
            )

        # Valider type_regelement
        type_reg = first_row.get('type_regelement')
        if type_reg not in [1, 2]:
            raise HTTPException(
                status_code=400,
                detail="type_regelement doit être 1 (Effet à payer) ou 2 (Chèques émis)"
            )

    # Convertir JSON → Excel
    excel_file = save_regelement_to_excel(request.donnees, request.email_expediteur)

    # Enqueue la tâche
    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="regelement"
    )

    logger.info(f"📋 Tâche règlement (JSON) enqueued: {task_id}")

    return TaskStatus(
        task_id=task_id,
        status='pending',
        module='regelement',
        started_at=None,
        completed_at=None,
        result=None,
        error=None
    )


@app.post("/api/receiption/data", response_model=TaskStatus)
async def trigger_receiption_from_data(request: ReceiptionDataRequest):
    """
    Déclencher une tâche réception avec données JSON
    Les données sont converties en Excel et enqueued pour le worker

    Colonnes requises: CodeFrs, BLFrs, DateBC, N_BC, CodeArticle, Quantite,
                       N_B_transport, Matricule, Poids, Marque
    Colonne optionnelle: observation

    Exemple:
    ```json
    {
        "donnees": [
            {
                "CodeFrs": "T1398",
                "BLFrs": "BL001",
                "DateBC": "15/01/2026",
                "N_BC": "BC123456",
                "CodeArticle": "A00001",
                "Quantite": 10,
                "N_B_transport": "BT001",
                "Matricule": "MAT001",
                "Poids": 500,
                "Marque": "DELL",
                "observation": ""
            }
        ],
        "email_expediteur": "user@example.com",
        "headless": true
    }
    ```
    """
    # Valider email
    if not request.email_expediteur:
        raise HTTPException(status_code=400, detail="email_expediteur est requis")

    # Valider les colonnes requises (observation est optionnelle)
    required_columns = ['CodeFrs', 'BLFrs', 'DateBC', 'N_BC', 'CodeArticle', 'Quantite',
                         'N_B_transport', 'Matricule', 'Poids', 'Marque']
    if request.donnees:
        first_row = request.donnees[0]
        missing = [col for col in required_columns if col not in first_row]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Colonnes manquantes: {', '.join(missing)}. Requises: {', '.join(required_columns)}"
            )

    # Convertir JSON → Excel
    excel_file = save_receiption_to_excel(request.donnees, request.email_expediteur)

    #Enqueue la tâche
    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="receiption"
    )

    logger.info(f"📋 Tâche réception (JSON) enqueued: {task_id}")

    return TaskStatus(
        task_id=task_id,
        status='pending',
        module='receiption',
        started_at=None,
        completed_at=None,
        result=None,
        error=None
    )


@app.post("/api/imputation/data", response_model=TaskStatus)
async def trigger_imputation_from_data(request: ImputationDataRequest):
    """
    Déclencher une tâche imputation avec données JSON
    Les données sont converties en Excel et enqueued pour le worker

    Colonnes requises: CodeFrs, N_BC, Reglement, Facture

    Exemple:
    ```json
    {
        "donnees": [
            {
                "CodeFrs": "T1398",
                "N_BC": "BC123456",
                "Reglement": "REG001",
                "Facture": "FAFOU001"
            }
        ],
        "email_expediteur": "user@example.com",
        "headless": true
    }
    ```
    """
    if not request.email_expediteur:
        raise HTTPException(status_code=400, detail="email_expediteur est requis")

    required_columns = ['CodeFrs', 'N_BC', 'Reglement', 'Facture']
    if request.donnees:
        first_row = request.donnees[0]
        missing = [col for col in required_columns if col not in first_row]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Colonnes manquantes: {', '.join(missing)}. Requises: {', '.join(required_columns)}"
            )

    excel_file = save_imputation_to_excel(request.donnees, request.email_expediteur)

    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="imputation"
    )

    logger.info(f"📋 Tâche imputation (JSON) enqueued: {task_id}")

    return TaskStatus(
        task_id=task_id,
        status='pending',
        module='imputation',
        started_at=None,
        completed_at=None,
        result=None,
        error=None
    )


@app.post("/api/demmande_achat/data", response_model=TaskStatus)
async def trigger_demmande_achat_from_data(request: DemmandAchatDataRequest):
    """
    Déclencher une tâche demande d'achat avec données JSON
    Les données sont converties en Excel et enqueued pour le worker

    Colonnes requises: CodeFrs, N_BC, Reglement, Facture

    Exemple:
    ```json
    {
        "donnees": {
            "societe": "AMANA",
            "code_tier": "T6824",
            "mois": 4,
            "annee": 2026,
            "marque": "PAIE 4/2026",
            "observation": "PAIE AMANA 4/2026",
            "lignes": [
                    {
                      "code_article": "A09667",
                      "libelle": "Total CNSS",
                      "montant": 148588.00999999998,
                      "montant_ht": 123823.3417,
                      "montant_moyen": 917.2099,
                      "effectif": 135
                    },
                    ...
                     ,],
            "total_montant": 1262097.49,
            "total_montant_ht": 1051747.9084,
            "total_montant_moyen": 44342.92969999999
        },
        "email_expediteur": "user@example.com",
        "headless": true
    }
    ```
    """
    print(request.donnees)
    if not request.email_expediteur:
        raise HTTPException(status_code=400, detail="email_expediteur est requis")
    required_columns_entite = ['observation', 'marque']
    if request.donnees:
        first_row = request.donnees[0]
        missing = [col for col in required_columns_entite if col not in first_row]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Colonnes manquantes: {', '.join(missing)}. Requises: {', '.join(required_columns_entite)}"
            )
    if request.donnees and 'lignes' in request.donnees[0]:
        required_columns_lignes = ['code_sage', 'effectif']
        for idx, ligne in enumerate(request.donnees[0]['lignes']):
            missing = [col for col in required_columns_lignes if col not in ligne]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Colonnes manquantes dans lignes[{idx}]: {', '.join(missing)}. Requises: {', '.join(required_columns_lignes)}"
                )
            
    excel_file = save_da_to_excel(request.donnees, request.email_expediteur)

    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="demmande_achat",
        societe=request.donnees[0]["observation"]
    )

    logger.info(f"📋 Tâche imputation (JSON) enqueued: {task_id}")

    return TaskStatus(
        task_id=task_id,
        status='pending',
        module='demmande_achat',
        started_at=None,
        completed_at=None,
        result=None,
        error=None
    )


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload un fichier Excel
    
    Retourne le chemin du fichier uploadé
    """
    try:
        # Générer un nom de fichier unique
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = UPLOAD_DIR / unique_filename
        
        # Sauvegarder le fichier
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f" Fichier uploadé: {file.filename} → {file_path}")
        
        return {
            "filename": file.filename,
            "saved_as": unique_filename,
            "path": str(file_path),
            "size": os.path.getsize(file_path)
        }
        
    except Exception as e:
        logger.error(f" Erreur upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """
    Récupérer le statut d'une tâche (mémoire ou queue)
    """
    # Chercher dans la mémoire (compatibilité arrière)
    if task_id in tasks_status:
        return TaskStatus(**tasks_status[task_id])

    # Chercher dans la queue
    queue_tasks = load_queue()
    for task in queue_tasks:
        if task['id'] == task_id:
            return TaskStatus(
                task_id=task['id'],
                status=task['status'],
                module='bonne_commande_api',
                started_at=task.get('started_at'),
                completed_at=task.get('completed_at'),
                result=None,
                error=task.get('error')
            )

    raise HTTPException(status_code=404, detail=f"Tâche non trouvée: {task_id}")

@app.get("/api/tasks/demande_achat")
async def list_tasks_demande_achat():
    """
    Lister toutes les taches liee au demande achat
    where status en pending
    """
    results = []
    tasks = load_queue()
    for task in tasks:
        if task["status"] == "pending" and task["task_type"] == "demmande_achat":
            results.append(task)
    
    return results


@app.get("/api/tasks")
async def list_tasks(module: Optional[str] = None, status: Optional[str] = None):
    """
    Lister toutes les tâches
    
    Paramètres optionnels:
    - module: filtrer par module (lettrage, bonne_commande)
    - status: filtrer par statut (pending, running, completed, failed)
    """
    tasks = list(tasks_status.values())
    
    # Filtrer par module
    if module:
        tasks = [t for t in tasks if t['module'] == module]
    
    # Filtrer par statut
    if status:
        tasks = [t for t in tasks if t['status'] == status]
    
    return {
        "total": len(tasks),
        "tasks": tasks
    }


@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    """
    Supprimer une tâche de l'historique
    """
    if task_id not in tasks_status:
        raise HTTPException(status_code=404, detail=f"Tâche non trouvée: {task_id}")
    
    # Ne supprimer que si terminée ou en échec
    if tasks_status[task_id]['status'] in ['running', 'pending']:
        raise HTTPException(status_code=400, detail="Impossible de supprimer une tâche en cours")
    
    del tasks_status[task_id]
    
    logger.info(f"🗑️ Tâche supprimée: {task_id}")
    
    return {"message": f"Tâche {task_id} supprimée"}


# ============================================================================
# LANCEMENT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("="*80)
    logger.info("DÉMARRAGE API SAGE X3 RPA")
    logger.info("="*80)
    logger.info("📡 Serveur: http://localhost:8003")
    logger.info("📖 Documentation: http://localhost:8003/docs")
    logger.info("="*80)
    
    uvicorn.run(app, host="0.0.0.0", port=8003)
