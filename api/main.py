# -*- coding: utf-8 -*-
"""
API REST pour déclencher les robots RPA Sage X3
FastAPI avec endpoints pour chaque module
Architecture Queue-Based pour traitement asynchrone
"""
import json
import sys
from pathlib import Path

# Ajouter le répertoire racine au path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
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
from config.settings import _TYPE_REGLEMENT_
# Importer le queue manager
from utils.queue_manager import add_task, load_queue
from query.query_ff import query_ff
from query.solde_fournisseur import query_sold_fournisseur
from query.BC_solde_non_attache import querry_bc_solde_non_attache

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
class DFFAnnulationControlRequest(BaseModel):
    """Requête pour déclencher l'annulation Control avec données JSON"""
    donnees: List[Dict[str, Any]]
    email_expediteur: str
    headless: bool = True

class DemmandAchatDataRequest(BaseModel):
    """Requête pour déclencher la demande d'achat avec données JSON"""
    donnees: List[Dict[str, Any]]
    email_expediteur: str
    headless: bool = True

class SignatureDALigne(BaseModel):
    code_article: str
    numero_da: str

class SignatureDADataRequest(BaseModel):
    donnees: List[SignatureDALigne] = Field(..., min_length=1)
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

def save_dff_annulation_control_to_excel(donnees: List[Dict[str, Any]], email_expediteur: str) -> str:
    """
    Convertir les données JSON annulation control de dff en fichier Excel temporaire

    Colonnes requises: DFF
    """
    df = pd.DataFrame(donnees)
    df['email_expediteur'] = email_expediteur
    filename = f"api_data_DFF_AC_{uuid.uuid4()}.xlsx"
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
    
    if 'N_Facture' not in df.columns:
        df['N_Facture'] = ''
    df['N_Facture'] = df['N_Facture'].fillna('').astype(str)  # garde les zéros de tête

    # Ajouter la colonne email_expediteur
    df['email_expediteur'] = email_expediteur

    # Générer un nom de fichier unique
    filename = f"api_data_REC_{uuid.uuid4()}.xlsx"
    file_path = UPLOAD_DIR / filename

    df.to_excel(file_path, index=False)

    logger.info(f" Données réception converties en Excel: {file_path}")

    return str(file_path)

def _get_status(item: Dict[str, Any]) -> str:
    """Retourne le status d'une ligne ('' si absent ou vide). Clé insensible à la casse."""
    for cle, valeur in item.items():
        if str(cle).strip().lower() == 'status' and valeur is not None:
            return str(valeur).strip()
    return ''
 
 
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
                'quantite': ligne.get('effectif', 0),
                'marque': "PRESTATION",
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


def save_da_to_excel_with_status(donnees: List[Dict[str, Any]], email_expediteur: str) -> str:
    """
    Convertit les données JSON demande d'achat en fichier Excel temporaire.

    Structure attendue :
        [
          {
            "id_da": "DA-CF-202610-ZO24KR",   # optionnel, identifiant de la DA
            "observation": "...",              # optionnel si id_da présent (repli sur id_da)
            "marque": "...",                   # optionnel (défaut PRESTATION)
            "Demandeur": "...",                # optionnel (ou "demandeur")
            "status": "charge_fixe",           # optionnel, valable pour toute la demande
            "lignes": [
              {"code_sage": "A00001", "effectif": 3, "status": "charge_fixe"},  # status optionnel par ligne
              ...
            ]
          }
        ]

    Colonnes Excel produites :
        Demandeur, Observation, code_article, quantite, marque, status,
        email_expediteur, id_da

    Règle pour `status` : valeur de la ligne si présente, sinon valeur de la demande,
    sinon chaîne vide. La colonne existe toujours dans le fichier.
    """
    rows = []

    for item in donnees:
        id_da       = (item.get("id_da") or "").strip()
        observation = item.get("observation") or id_da
        marque      = item.get("marque") or "PRESTATION"
        demandeur   = item.get("Demandeur") or item.get("demandeur")
        status_item = (item.get("status") or "").strip()

        for ligne in item.get("lignes", []):
            status_ligne = (ligne.get("status") or "").strip()

            rows.append({
                "Demandeur":    demandeur,
                "Observation":  observation,
                "code_article": ligne.get("code_sage", ""),
                "quantite":     ligne.get("effectif", 0),
                "marque":       marque,
                "status":       status_ligne or status_item,
                "id_da":        id_da,
            })

    df = pd.DataFrame(
        rows,
        columns=["Demandeur", "Observation", "code_article", "quantite", "marque", "status", "id_da"],
    )
    df["email_expediteur"] = email_expediteur

    # id_da en dernière colonne, après email_expediteur
    df = df[["Demandeur", "Observation", "code_article", "quantite", "marque",
             "status", "email_expediteur", "id_da"]]

    filename  = f"api_data_DA_status_{uuid.uuid4()}.xlsx"
    file_path = UPLOAD_DIR / filename

    df.to_excel(file_path, index=False)

    logger.info(f"Données DA (avec status) converties en Excel: {file_path} | colonnes: {list(df.columns)}")

    return str(file_path)   # indispensable, sinon "file": null dans la queue



def save_signature_da_to_excel(donnees: List[Dict[str, Any]], email_expediteur: str) -> str:
    """
    Convertir les données JSON de signature de DA (format plat) en fichier Excel temporaire.

    Args:
        donnees: Liste de dictionnaires plats avec les colonnes:
                 numero_da, code_article
        email_expediteur: Email de l'expéditeur

    Returns:
        Chemin du fichier Excel créé

    Raises:
        ValueError: si une ligne n'a pas de numero_da ou de code_article
    """
    rows = []
    vues = set()
    doublons = 0

    for idx, item in enumerate(donnees):
        # str() protège contre un numero_da envoyé en nombre par n8n
        numero_da = str(item.get('numero_da') or '').strip().upper()
        code_article = str(item.get('code_article') or '').strip()

        if not numero_da or not code_article:
            raise ValueError(
                f"donnees[{idx}]: numero_da et code_article sont obligatoires "
                f"(reçu: numero_da='{numero_da}', code_article='{code_article}')"
            )

        # Une même ligne ne doit pas être signée deux fois par le robot
        cle = (numero_da, code_article)
        if cle in vues:
            doublons += 1
            logger.warning(f" Doublon ignoré (signature DA): {numero_da} / {code_article}")
            continue
        vues.add(cle)

        rows.append({
            'code_article': code_article,
            'numero_da': numero_da,
        })

    df = pd.DataFrame(rows, columns=['code_article', 'numero_da'])
    df['email_expediteur'] = email_expediteur

    filename = f"api_data_SIGNATURE_DA_{uuid.uuid4()}.xlsx"
    file_path = UPLOAD_DIR / filename

    df.to_excel(file_path, index=False)

    logger.info(
        f" Données signature DA converties en Excel: {file_path} "
        f"({len(rows)} ligne(s), {df['numero_da'].nunique()} DA, {doublons} doublon(s) ignoré(s))"
    )

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
    details = [row['Numero_DA'] for row in request.donnees]

    # Enqueue la tâche
    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="bon_commande",
        details=details
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
    details = [row['BR'] for row in request.donnees]
    # Enqueue la tâche
    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="facturation",
        details=details
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
    details = [row['N_Facture'] for row in request.donnees]
    # Enqueue la tâche
    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="regelement",
        details=details
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


@app.post("/api/regelement/virement", response_model=TaskStatus)
async def trigger_virement_from_data(request: RegelementDataRequest):
    """
    Déclencher une tâche virement (mode de paiement VIR) avec données JSON.
    Les données sont converties en Excel et enqueued pour le worker.

    Colonnes requises: Code_Frs, N_Facture, Refference, Montant, TVA
    Colonnes optionnelles: Raison, objet
    - objet : "VIR <Refference> <Raison>". S'il est absent ou vide, il est
      reconstruit automatiquement à partir de Refference et Raison.
    - type_regelement : forcé à 2 pour les VIR

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
                "Raison": "Paiement facture",
                "objet": "VIR REF001 Paiement facture"
            }
        ],
        "email_expediteur": "user@example.com",
        "headless": true
    }
```
    """
    if not request.email_expediteur:
        raise HTTPException(status_code=400, detail="email_expediteur est requis")

    if not request.donnees:
        raise HTTPException(status_code=400, detail="donnees est vide")

    # Valider les colonnes requises sur TOUTES les lignes
    required_columns = ['Code_Frs', 'N_Facture', 'Refference', 'Montant', 'TVA']
    for i, row in enumerate(request.donnees, start=1):
        missing = [col for col in required_columns if col not in row]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Ligne {i} : colonnes manquantes: {', '.join(missing)}. "
                       f"Requises: {', '.join(required_columns)}"
            )

        row['type_virement'] = row.get('type_virement') or 1
        row.pop('type_regelement', None)  # inutile pour les virements

        # Objet du virement : utilisé tel quel s'il est fourni,
        # sinon reconstruit en "VIR <Refference> <Raison>"
        reference = str(row.get('Refference') or '').strip()
        raison    = str(row.get('Raison') or '').strip()
        objet     = str(row.get('objet') or '').strip()

        if not objet:
            objet = " ".join(p for p in ("VIR", reference, raison) if p)

        row['Raison'] = raison
        row['objet']  = objet

    # Convertir JSON → Excel (la colonne objet est incluse)
    excel_file = save_regelement_to_excel(request.donnees, request.email_expediteur)
    details = [row['N_Facture'] for row in request.donnees]

    # Enqueue la tâche avec le type "vairement"
    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="vairement",
        details=details
    )

    logger.info(
        f"📋 Tâche virement (JSON) enqueued: {task_id} "
        f"({len(request.donnees)} ligne(s), objets: {[r['objet'] for r in request.donnees]})"
    )

    return TaskStatus(
        task_id=task_id,
        status='pending',
        module='vairement',
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
    donnees = []
    for row in request.donnees:
        row = dict(row)
        row['N_Facture'] = row.get('N_Facture') or ''
        donnees.append(row)

    # Convertir JSON → Excel
    excel_file = save_receiption_to_excel(request.donnees, request.email_expediteur)
    details = [row['BLFrs'] for row in request.donnees]
    #Enqueue la tâche
    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="receiption",
        details=details
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


import json  # si pas déjà importé en haut du fichier

@app.post("/api/demmande_achat/data", response_model=TaskStatus)
async def trigger_demmande_achat_from_data(request: DemmandAchatDataRequest):
    """
    Déclencher une tâche demande d'achat avec données JSON
    Les données sont converties en Excel et enqueued pour le worker

    Colonnes requises: CodeFrs, N_BC, Reglement, Facture
    ...
    """

    logger.info(f"📥 Nouvelle requête /api/demmande_achat/data - email_expediteur: {request.email_expediteur}, headless: {request.headless}")
    logger.info(f"📦 Nombre de lignes reçues: {len(request.donnees) if request.donnees else 0}")
    logger.info(f"📦 Données brutes reçues:\n{json.dumps(request.donnees, indent=2, ensure_ascii=False, default=str)}")

    if not request.email_expediteur:
        raise HTTPException(status_code=400, detail="email_expediteur est requis")

    required_columns_entite = ['observation', 'marque']
    if request.donnees:
        first_row = request.donnees[0]
        missing = [col for col in required_columns_entite if col not in first_row]
        if missing:
            logger.warning(f"⚠️ Colonnes manquantes dans la requête: {missing}")
            raise HTTPException(
                status_code=400,
                detail=f"Colonnes manquantes: {', '.join(missing)}. Requises: {', '.join(required_columns_entite)}"
            )

    if request.donnees and 'lignes' in request.donnees[0]:
        required_columns_lignes = ['code_sage', 'effectif']
        for idx, ligne in enumerate(request.donnees[0]['lignes']):
            missing = [col for col in required_columns_lignes if col not in ligne]
            if missing:
                logger.warning(f"⚠️ Colonnes manquantes dans lignes[{idx}]: {missing}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Colonnes manquantes dans lignes[{idx}]: {', '.join(missing)}. Requises: {', '.join(required_columns_lignes)}"
                )

    excel_file = save_da_to_excel(request.donnees, request.email_expediteur)
    logger.info(f"✅ Fichier Excel généré: {excel_file}")

    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="demmande_achat",
        societe=request.donnees[0]["observation"]
    )

    logger.info(f"📋 Tâche demmande_achat (JSON) enqueued: {task_id}")

    return TaskStatus(
        task_id=task_id,
        status='pending',
        module='demmande_achat',
        started_at=None,
        completed_at=None,
        result=None,
        error=None
    )


@app.post("/api/demmande_achat/data_status", response_model=TaskStatus)
async def trigger_demmande_achat_from_data_status(request: DemmandAchatDataRequest):
    """
    Déclencher une tâche demande d'achat avec données JSON (colonnes `status` et `id_da` incluses).
    Les données sont converties en Excel puis enqueued pour le worker.

    Requis : email_expediteur, donnees[*].observation OU donnees[*].id_da,
             donnees[*].lignes[*].code_sage / effectif
    Optionnel : donnees[*].marque, donnees[*].Demandeur, donnees[*].status,
                donnees[*].lignes[*].status
    """
    logger.info(
        f"📥 Nouvelle requête /api/demmande_achat/data_status - "
        f"email_expediteur: {request.email_expediteur}, headless: {request.headless}"
    )
    logger.info(f"📦 Nombre de demandes reçues: {len(request.donnees) if request.donnees else 0}")
    logger.info(
        "📦 Données brutes reçues:\n"
        + json.dumps(request.donnees, indent=2, ensure_ascii=False, default=str)
    )

    if not request.email_expediteur:
        raise HTTPException(status_code=400, detail="email_expediteur est requis")

    if not request.donnees:
        raise HTTPException(status_code=400, detail="donnees est requis et ne doit pas être vide")

    # ── Validation de chaque demande ──
    required_columns_lignes = ["code_sage", "effectif"]

    for d_idx, item in enumerate(request.donnees):
        # observation OU id_da doit être présent
        if not (item.get("observation") or item.get("id_da")):
            logger.warning(f"⚠️ donnees[{d_idx}] : ni 'observation' ni 'id_da'")
            raise HTTPException(
                status_code=400,
                detail=f"donnees[{d_idx}] : 'observation' ou 'id_da' est requis",
            )

        lignes = item.get("lignes")
        if not lignes:
            logger.warning(f"⚠️ donnees[{d_idx}] : 'lignes' absent ou vide")
            raise HTTPException(
                status_code=400,
                detail=f"donnees[{d_idx}] : 'lignes' est absent ou vide",
            )

        for l_idx, ligne in enumerate(lignes):
            missing = [c for c in required_columns_lignes if c not in ligne]
            if missing:
                logger.warning(f"⚠️ Colonnes manquantes dans donnees[{d_idx}].lignes[{l_idx}]: {missing}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Colonnes manquantes dans donnees[{d_idx}].lignes[{l_idx}]: "
                           f"{', '.join(missing)}. Requises: {', '.join(required_columns_lignes)}",
                )

    # ── Excel + tâche worker ──
    excel_file = save_da_to_excel_with_status(request.donnees, request.email_expediteur)
    logger.info(f"✅ Fichier Excel généré: {excel_file}")

    first = request.donnees[0]
    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="demmande_achat",
        societe=first.get("observation") or first.get("id_da"),
    )
    logger.info(f"📋 Tâche demmande_achat (JSON + status + id_da) enqueued: {task_id}")

    return TaskStatus(
        task_id=task_id,
        status="pending",
        module="demmande_achat",
        started_at=None,
        completed_at=None,
        result=None,
        error=None,
    )


@app.post("/api/signature_da/data", response_model=TaskStatus)

async def trigger_signature_da_from_data(request: SignatureDADataRequest):
    """
    Déclencher une tâche de signature de DA avec données JSON.
    Les données sont converties en Excel, stockées, puis enqueued pour le worker.

    Champs requis par ligne: code_article, numero_da
    Champ requis global: email_expediteur

    Exemple:
```json
    {
        "donnees": [
            {"code_article": "A09667", "numero_da": "DA2600123"},
            {"code_article": "A01234", "numero_da": "DA2600123"}
        ],
        "email_expediteur": "developpeur.ia@jbel-annour.ma",
        "headless": false
    }
```
    """
    email = request.email_expediteur.strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="email_expediteur invalide ou manquant")

    donnees = [l.model_dump() for l in request.donnees]   # Pydantic v1: l.dict()

    logger.info(f" Signature DA reçue de {email}: {len(donnees)} ligne(s)")
    for l in donnees:
        logger.info(f"   ➜ {l['numero_da']} | {l['code_article']}")

    try:
        excel_file = save_signature_da_to_excel(donnees, email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    task_id = add_task(
        file_path=excel_file,
        email=email,
        task_type="signature_da",
        societe=donnees[0]["numero_da"],
    )

    logger.info(f" Tâche signature DA enqueued: {task_id}")

    return TaskStatus(
        task_id=task_id,
        status="pending",
        module="signature_da",
        started_at=None,
        completed_at=None,
        result=None,
        error=None,
    )


@app.post("/api/dff_annulation_control/data", response_model=TaskStatus)
async def trigger_dff_annulation_control_from_data(request : DFFAnnulationControlRequest):
    """
    Déclencher une tâche annulation control avec données JSON
    Les données sont converties en Excel et enqueued pour le worker

    Colonnes requises: DFF

    Exemple:
    ```json
    {
        "donnees": [
            {
                "DFF": "DFF12312"
            }
        ],
        "email_expediteur": "user@example.com",
        "headless": true
    }
    ```
    """
    if not request.email_expediteur:
        raise HTTPException(status_code=400, detail="email_expediteur est requis")

    required_columns = ['DFF']
    if request.donnees:
        first_row = request.donnees[0]
        missing = [col for col in required_columns if col not in first_row]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Colonnes manquantes: {', '.join(missing)}. Requises: {', '.join(required_columns)}"
            )

    excel_file = save_dff_annulation_control_to_excel(request.donnees, request.email_expediteur)

    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="imputation"
    )

    logger.info(f"📋 Tâche imputation (JSON) enqueued: {task_id}")

    return TaskStatus(
        task_id=task_id,
        status='pending',
        module='dff_annulation_control',
        started_at=None,
        completed_at=None,
        result=None,
        error=None
    )


@app.get("/api/list_ff_non_regles")
async def list_ff_non_regles():
    """
    Lister les factures fournisseurs non réglées
    """
    import pyodbc

    try:
        # executer la requete SQL pour récupérer les factures non réglées
        conn = pyodbc.connect(
                "DRIVER={ODBC Driver 17 for SQL Server};"
                "SERVER=192.168.1.241\\ERPX3;"
                "DATABASE=x3;"
                "UID=X3U;"
                "PWD=SQL@2019;"
            )
        cursor = conn.cursor()
        cursor.execute(query_ff)
        rows = cursor.fetchall()

        # charge RegelementDataRequest avec les données récupérées 
        result = RegelementDataRequest(donnees=[], email_expediteur="", headless=False)
        for row in rows:
            if row.ModePaiement == "LCR" and row.Ecart >= 0:
                result.donnees.append({
                    "Code_Frs": row.CodeFournisseur,
                    "N_Facture": row.NumFacture,
                    "Refference": row.Reference,
                    "Montant": row.ResteAPayer,
                    "TVA": row.MontantTVA,
                    "type_regelement": _TYPE_REGLEMENT_.get(row.ModePaiement)
                })
                result.email_expediteur = None
                result.headless = False
        return result
        
    except Exception as e:
        logger.error(f" Erreur lecture factures non réglées: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sold_fournisseur/{code_fournisseur}")
async def get_sold_fournisseur(code_fournisseur: str):
    """
    Récupérer le solde d'un fournisseur
    """
    import pyodbc
    try:
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.1.241\\ERPX3;"
            "DATABASE=x3;"
            "UID=X3U;"
            "PWD=SQL@2019;"
        )
        cursor = conn.cursor()
        cursor.execute(query_sold_fournisseur.format(code_fournisseur=code_fournisseur))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Fournisseur non trouvé")

        return {"solde": row.Solde}

    except Exception as e:
        logger.error(f" Erreur lecture solde fournisseur: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bc_solde_non_attache")
async def get_BC_solde_non_attache():
    """
    Récupérer la liste des BC solde et non attaches
    """
    import pyodbc
    try:
        conn = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.1.241\\ERPX3;"
            "DATABASE=x3;"
            "UID=X3U;"
            "PWD=SQL@2019;"
        )
        cursor = conn.cursor()
        cursor.execute(querry_bc_solde_non_attache)
        rows = cursor.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="la liste est vide")

        # Récupérer les noms de colonnes
        columns = [col[0] for col in cursor.description]
        # Convertir chaque row en dict
        result = [dict(zip(columns, row)) for row in rows]

        return result
    
    except Exception as e:
        logger.error(f" Erreur lecture la liste des bc solde non attache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
                module=task['task_type'],
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
