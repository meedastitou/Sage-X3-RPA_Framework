# 📋 Résumé: Migration vers Architecture Queue-Based

## Objectif
Convertir l'API pour enqueuer les tâches dans une file d'attente gérée par `worker_rpa.py` au lieu d'exécuter directement les robots.

## Architecture

```
┌─────────────────┐
│   Dashboard     │
└────────┬────────┘
         │ POST /api/bonne-commande/data (JSON)
         ▼
┌─────────────────────────────────────┐
│   API (FastAPI)                     │
│ - Validation des données            │
│ - Conversion JSON → Excel           │
│ - Enqueue vers la queue             │
└────────┬────────────────────────────┘
         │ add_task()
         ▼
┌─────────────────────────────────────┐
│   Queue (data/queue/tasks.json)     │
│ {                                   │
│   "id": "uuid",                     │
│   "status": "pending",              │
│   "task_type": "bon_commande",      │
│   "file": "path/to/excel",          │
│   "email": "email@example.com"      │
│ }                                   │
└────────┬────────────────────────────┘
         │ get_next_task()
         ▼
┌─────────────────────────────────────┐
│   Worker (workers/worker_rpa.py)    │
│ - Boucle infinie                    │
│ - Récupère tâches pending           │
│ - Exécute le robot approprié        │
│ - Met à jour le statut              │
└─────────────────────────────────────┘
         │ BonneCommandeRobot.execute_from_dataframe()
         ▼
┌─────────────────────────────────────┐
│   Sage X3 (via Selenium)            │
└─────────────────────────────────────┘
```

## Modifications Effectuées

### 1. api/main.py

#### Ajout des imports queue_manager
```python
from utils.queue_manager import add_task, load_queue
```

#### Nouvelle fonction: save_dataframe_to_excel()
Convertit les données JSON en fichier Excel temporaire:
- Input: `List[Dict[str, Any]]` (données JSON)
- Output: `str` (chemin du fichier Excel créé)
- Location: `data/input/excel/api_uploads/`

#### Endpoint modifié: POST /api/bonne-commande/data
**Ancien comportement:**
- Validait les données
- Exécutait directement le robot en thread

**Nouveau comportement:**
1. Valide les données (email_expediteur requis)
2. Convertit JSON → Excel avec `save_dataframe_to_excel()`
3. Enqueue la tâche avec `add_task(excel_file, email, "bon_commande")`
4. Retourne l'ID de la tâche depuis la queue

**Code:**
```python
@app.post("/api/bonne-commande/data", response_model=TaskStatus)
async def trigger_bonne_commande_from_data(request: BonneCommandeDataRequest):
    """
    Déclencher une tâche bonne commande avec données JSON
    Les données sont converties en Excel et enqueued pour le worker
    """
    # Valider email
    if not request.email_expediteur:
        raise HTTPException(status_code=400, detail="email_expediteur est requis")
    
    # Convertir JSON → Excel
    excel_file = save_dataframe_to_excel(request.donnees)
    
    # Enqueue
    task_id = add_task(
        file_path=excel_file,
        email=request.email_expediteur,
        task_type="bon_commande"
    )
    
    # Retourner le statut de la tâche enqueued
    queue_tasks = load_queue()
    task = next((t for t in queue_tasks if t['id'] == task_id), None)
    
    return TaskStatus(
        task_id=task_id,
        status='pending',
        module='bonne_commande_api',
        started_at=None,
        completed_at=None,
        result=None,
        error=None
    )
```

#### Endpoint modifié: GET /api/task/{task_id}
**Ancien comportement:**
- Lisait uniquement depuis `tasks_status` (dictionnaire en mémoire)
- Ignorait les tâches enqueued

**Nouveau comportement:**
1. Cherche d'abord dans la mémoire (compatibilité arrière)
2. Sinon cherche dans la queue avec `load_queue()`
3. Convertit le format queue au format API
4. Retourne 404 si non trouvé

**Code:**
```python
@app.get("/api/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Récupérer le statut d'une tâche (mémoire ou queue)"""
    # Chercher dans la mémoire
    if task_id in tasks_status:
        return TaskStatus(**tasks_status[task_id])
    
    # Chercher dans la queue
    queue_tasks = load_queue()
    for task in queue_tasks:
        if task['id'] == task_id:
            return {
                'task_id': task['id'],
                'status': task['status'],
                'module': 'bonne_commande_api',
                'started_at': task.get('started_at'),
                'completed_at': task.get('completed_at'),
                'result': None,
                'error': task.get('error')
            }
    
    raise HTTPException(status_code=404, detail=f"Tâche non trouvée: {task_id}")
```

#### Fonctions supprimées
- `execute_bonne_commande_from_data()` - Plus utilisée, logique déplacée vers queue

#### Fonctions conservées
- `execute_lettrage()` - Toujours utilisée par endpoint `/api/lettrage`
- Autres endpoints conservés pour compatibilité

### 2. Fichiers Existants (Inchangés)

#### utils/queue_manager.py
Aucune modification - déjà fonctionnel
- `add_task()` - Crée une nouvelle tâche dans la queue
- `get_next_task()` - Récupère la prochaine tâche pending
- `update_task()` - Met à jour le statut d'une tâche
- `load_queue()` / `save_queue()` - I/O du fichier queue

#### workers/worker_rpa.py
Aucune modification - déjà compatible
- Boucle continue qui poll pour les tâches pending
- Exécute le robot approprié selon task_type
- Met à jour le statut dans la queue

## Flux de Données

### 1. Requête API

```json
POST /api/bonne-commande/data
{
  "donnees": [
    {
      "numero_commande": "BDC001",
      "fournisseur": "ACME",
      "montant_ht": 1000.00,
      "montant_ttc": 1200.00,
      "date_commande": "2024-01-15"
    }
  ],
  "email_expediteur": "user@example.com",
  "headless": true
}
```

### 2. Traitement API

1. Validation des données (DataFrame conversion check)
2. Création d'un fichier Excel temporaire
   - Fichier: `data/input/excel/api_uploads/api_data_<uuid>.xlsx`
   - Contient: Les données JSON converties en lignes Excel
3. Appel à `add_task()`:
   - Crée un objet task avec UUID
   - Ajoute à la queue
   - Retourne l'UUID

### 3. Réponse API

```json
200 OK
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "module": "bonne_commande_api",
  "started_at": null,
  "completed_at": null,
  "result": null,
  "error": null
}
```

### 4. Queue (data/queue/tasks.json)

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "pending",
    "task_type": "bon_commande",
    "file": "/path/to/data/input/excel/api_uploads/api_data_<uuid>.xlsx",
    "email": "user@example.com",
    "created_at": "2024-01-20T10:30:00",
    "started_at": null,
    "completed_at": null,
    "error": null
  }
]
```

### 5. Worker Processing

1. Worker appelle `get_next_task()`
   - Récupère première tâche avec status="pending"
   - Met à jour status → "running"
2. Selon task_type, lance le robot approprié
3. Charge le fichier Excel en DataFrame
4. Exécute `robot.execute_from_dataframe(df)`
5. Met à jour status → "completed" ou "failed"

## Avantages de Cette Architecture

✅ **Découplage**: L'API ne bloque pas en attendant la fin du robot
✅ **Scalabilité**: Plusieurs workers peuvent traiter les tâches en parallèle
✅ **Persistance**: Les tâches restent enqueued si le worker crash
✅ **Monitoring**: API retourne rapidement, utilisateur peut poller le statut
✅ **Résilience**: Worker peut être redémarré sans perdre les tâches

## Test et Validation

### Tests Inclus (test_api_queue_integration.py)

1. **Test 1**: Vérifier que l'API enqueue correctement
2. **Test 2**: Récupérer le statut depuis la queue
3. **Test 3**: Valider le format du fichier queue
4. **Test 4**: Vérifier que plusieurs tâches peuvent être enqueued
5. **Test 5**: Vérifier que les fichiers Excel sont créés correctement
6. **Test 6**: Validation des erreurs (email manquant)

### Exécuter les tests

```bash
# Depuis le répertoire racine du projet
python tests/test_api_queue_integration.py
```

## Prochaines Étapes (Optionnelles)

1. **Dashboard UI**: Afficher le statut des tâches en temps réel
2. **WebSocket**: Notifications en temps réel au lieu de polling
3. **Base de données**: Remplacer JSON par une véritable BD pour la scalabilité
4. **Retry logic**: Automatiquement réessayer les tâches échouées
5. **Logging détaillé**: Enregistrer les étapes du traitement

## Notes Importantes

⚠️ **Compatibilité arrière**: Les anciens endpoints qui utilisaient la mémoire (threads) sont conservés
⚠️ **Fichiers Excel**: Les fichiers créés par l'API doivent rester en place pour le worker
⚠️ **Worker**: Doit être lancé séparément avec `python workers/worker_rpa.py`
⚠️ **Queue persistance**: Les tâches restent en attente jusqu'à ce qu'elles soient traitées
