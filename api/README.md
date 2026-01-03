# 🚀 API REST Sage X3 RPA

API REST pour déclencher les robots d'automatisation Sage X3 via HTTP.

## 📋 Installation

```bash
cd C:\Users\m.astitou\Desktop\selenuim\sage-x3-rpa

# Installer FastAPI et Uvicorn
pip install fastapi uvicorn python-multipart
```

## 🚀 Démarrage

```bash
# Depuis le dossier sage-x3-rpa
python api/main.py
```

L'API démarre sur : **http://localhost:8000**

## 📖 Documentation Interactive

Une fois l'API démarrée, accédez à :
- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

## 🎯 Endpoints Disponibles

### 1. **Déclencher le Lettrage**

**POST** `/api/lettrage`

```bash
curl -X POST "http://localhost:8000/api/lettrage" \
  -H "Content-Type: application/json" \
  -d '{
    "excel_file": "C:\\Users\\m.astitou\\Desktop\\selenuim\\reglement a annuler.xlsx",
    "headless": false
  }'
```

**Réponse :**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "module": "lettrage",
  "started_at": null,
  "completed_at": null,
  "result": null,
  "error": null
}
```

### 2. **Déclencher Bonne de Commande**

**POST** `/api/bonne-commande`

```bash
curl -X POST "http://localhost:8000/api/bonne-commande" \
  -H "Content-Type: application/json" \
  -d '{
    "excel_file": "C:\\path\\to\\commandes.xlsx",
    "headless": true
  }'
```

### 3. **Upload un Fichier Excel**

**POST** `/api/upload`

```bash
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@C:\\path\\to\\file.xlsx"
```

**Réponse :**
```json
{
  "filename": "file.xlsx",
  "saved_as": "550e8400-e29b-41d4-a716-446655440000.xlsx",
  "path": "C:\\...\\data\\input\\excel\\api_uploads\\550e8400...xlsx",
  "size": 12345
}
```

**Puis utiliser ce fichier :**
```bash
curl -X POST "http://localhost:8000/api/lettrage" \
  -H "Content-Type: application/json" \
  -d '{
    "excel_file": "C:\\...\\data\\input\\excel\\api_uploads\\550e8400...xlsx",
    "headless": false
  }'
```

### 4. **Vérifier le Statut d'une Tâche**

**GET** `/api/task/{task_id}`

```bash
curl "http://localhost:8000/api/task/550e8400-e29b-41d4-a716-446655440000"
```

**Réponse (en cours) :**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "module": "lettrage",
  "started_at": "2025-12-29T10:30:00",
  "completed_at": null,
  "result": null,
  "error": null
}
```

**Réponse (terminée) :**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "module": "lettrage",
  "started_at": "2025-12-29T10:30:00",
  "completed_at": "2025-12-29T10:35:00",
  "result": {
    "total": 62,
    "succes": 58,
    "echecs": 4,
    "rapport": "C:\\...\\data\\output\\rapports\\rapport_lettrage_20251229_103000.xlsx"
  },
  "error": null
}
```

### 5. **Lister Toutes les Tâches**

**GET** `/api/tasks`

```bash
# Toutes les tâches
curl "http://localhost:8000/api/tasks"

# Filtrer par module
curl "http://localhost:8000/api/tasks?module=lettrage"

# Filtrer par statut
curl "http://localhost:8000/api/tasks?status=completed"

# Combiner les filtres
curl "http://localhost:8000/api/tasks?module=bonne_commande&status=running"
```

**Réponse :**
```json
{
  "total": 3,
  "tasks": [
    {
      "task_id": "...",
      "status": "completed",
      "module": "lettrage",
      ...
    },
    {
      "task_id": "...",
      "status": "running",
      "module": "bonne_commande",
      ...
    }
  ]
}
```

### 6. **Supprimer une Tâche**

**DELETE** `/api/task/{task_id}`

```bash
curl -X DELETE "http://localhost:8000/api/task/550e8400-e29b-41d4-a716-446655440000"
```

## 🐍 Exemples Python

### Utilisation avec `requests`

```python
import requests
import time

# 1. Upload un fichier
with open('mon_fichier.xlsx', 'rb') as f:
    upload_response = requests.post(
        'http://localhost:8000/api/upload',
        files={'file': f}
    )
    file_path = upload_response.json()['path']
    print(f"✅ Fichier uploadé: {file_path}")

# 2. Déclencher le lettrage
trigger_response = requests.post(
    'http://localhost:8000/api/lettrage',
    json={
        'excel_file': file_path,
        'headless': False
    }
)
task_id = trigger_response.json()['task_id']
print(f"✅ Tâche créée: {task_id}")

# 3. Vérifier le statut (polling)
while True:
    status_response = requests.get(f'http://localhost:8000/api/task/{task_id}')
    status = status_response.json()
    
    print(f"📊 Statut: {status['status']}")
    
    if status['status'] in ['completed', 'failed']:
        if status['status'] == 'completed':
            print(f"✅ Succès: {status['result']}")
        else:
            print(f"❌ Erreur: {status['error']}")
        break
    
    time.sleep(5)  # Attendre 5 secondes avant de revérifier
```

## 🌐 Utilisation depuis un Navigateur

### Via Swagger UI

1. Ouvrir http://localhost:8000/docs
2. Cliquer sur `/api/lettrage`
3. Cliquer sur "Try it out"
4. Remplir le JSON :
```json
{
  "excel_file": "C:\\Users\\m.astitou\\Desktop\\selenuim\\reglement a annuler.xlsx",
  "headless": false
}
```
5. Cliquer sur "Execute"
6. Copier le `task_id` de la réponse
7. Aller sur `/api/task/{task_id}` pour vérifier le statut

## 📊 Statuts des Tâches

| Statut | Description |
|--------|-------------|
| `pending` | Tâche créée, en attente de démarrage |
| `running` | Tâche en cours d'exécution |
| `completed` | Tâche terminée avec succès |
| `failed` | Tâche terminée en échec |

## 🔒 Sécurité

⚠️ **ATTENTION** : Cette API n'a **pas d'authentification** par défaut !

Pour la production, ajoutez :
1. **Authentification** (JWT, OAuth2)
2. **HTTPS** (certificat SSL)
3. **Rate limiting** (limite de requêtes)
4. **CORS** configuré

## 🚀 Déploiement en Production

### Avec Gunicorn (Linux)

```bash
pip install gunicorn
gunicorn api.main:app --workers 4 --bind 0.0.0.0:8000
```

### Avec Systemd (Service Linux)

Créer `/etc/systemd/system/sage-rpa-api.service` :
```ini
[Unit]
Description=Sage X3 RPA API
After=network.target

[Service]
User=votre_utilisateur
WorkingDirectory=/path/to/sage-x3-rpa
ExecStart=/path/to/venv/bin/gunicorn api.main:app --workers 4 --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Démarrer :
```bash
sudo systemctl start sage-rpa-api
sudo systemctl enable sage-rpa-api
```

### Avec Docker

Créer `Dockerfile` :
```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "api/main.py"]
```

Build et run :
```bash
docker build -t sage-rpa-api .
docker run -p 8000:8000 sage-rpa-api
```

## 📈 Monitoring

Logs disponibles dans : `data/output/logs/api_*.log`

## 🔧 Personnalisation

Modifier `api/main.py` pour :
- Ajouter d'autres endpoints
- Modifier les ports
- Ajouter l'authentification
- Configurer CORS
- Ajouter des webhooks

---

✅ **Votre API REST est prête !**
