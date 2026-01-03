# 🚀 DÉMARRAGE RAPIDE - API REST

## ⚡ Installation Express (2 minutes)

```bash
cd C:\Users\m.astitou\Desktop\selenuim\sage-x3-rpa

# Installer les dépendances API
pip install fastapi uvicorn python-multipart requests
```

## 🚀 Lancer l'API

```bash
# Depuis le dossier sage-x3-rpa
python api/main.py
```

**L'API démarre sur** : http://localhost:8000

## 📖 Accéder à la Documentation

Ouvrir dans votre navigateur : http://localhost:8000/docs

## 🎯 Test Rapide (3 méthodes)

### Méthode 1 : Via le Navigateur (Swagger UI)

1. Aller sur http://localhost:8000/docs
2. Cliquer sur `/api/lettrage` → `POST`
3. Cliquer sur "Try it out"
4. Modifier le JSON :
```json
{
  "excel_file": "C:\\Users\\m.astitou\\Desktop\\selenuim\\reglement a annuler.xlsx",
  "headless": false
}
```
5. Cliquer sur "Execute"
6. Copier le `task_id`
7. Aller sur `/api/task/{task_id}` → `GET`
8. Coller le `task_id` et "Execute"

### Méthode 2 : Via cURL

```bash
# Déclencher le lettrage
curl -X POST "http://localhost:8000/api/lettrage" ^
  -H "Content-Type: application/json" ^
  -d "{\"excel_file\": \"C:\\\\Users\\\\m.astitou\\\\Desktop\\\\selenuim\\\\reglement a annuler.xlsx\", \"headless\": false}"

# Copier le task_id de la réponse, puis:
curl "http://localhost:8000/api/task/VOTRE_TASK_ID"
```

### Méthode 3 : Via Python

```python
import requests

# Déclencher
response = requests.post('http://localhost:8000/api/lettrage', json={
    'excel_file': r'C:\Users\m.astitou\Desktop\selenuim\reglement a annuler.xlsx',
    'headless': False
})
task_id = response.json()['task_id']
print(f"Task ID: {task_id}")

# Vérifier le statut
status = requests.get(f'http://localhost:8000/api/task/{task_id}')
print(status.json())
```

## 📝 Exemple Complet avec le Client Python

```bash
# Lancer le client exemple
python api/client_example.py

# Choisir l'exemple 1 (Lettrage simple)
```

## 🎯 Workflow Complet

```
1. Démarrer l'API
   └─> python api/main.py

2. Upload un fichier (optionnel)
   └─> POST /api/upload

3. Déclencher un robot
   └─> POST /api/lettrage ou /api/bonne-commande

4. Récupérer task_id

5. Vérifier le statut (polling)
   └─> GET /api/task/{task_id}
   └─> Répéter jusqu'à status = completed/failed

6. Récupérer les résultats
   └─> Dans la réponse: result.rapport
```

## 📊 Exemple de Réponse Complète

**Tâche terminée :**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "module": "lettrage",
  "started_at": "2025-12-29T10:30:00.123456",
  "completed_at": "2025-12-29T10:35:42.789012",
  "result": {
    "total": 62,
    "succes": 58,
    "echecs": 4,
    "rapport": "C:\\...\\rapport_lettrage_20251229_103000.xlsx"
  },
  "error": null
}
```

## 🔥 Use Cases

### 1. Intégration dans une Application Web
```javascript
// Frontend JavaScript
fetch('http://localhost:8000/api/lettrage', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    excel_file: 'C:\\path\\to\\file.xlsx',
    headless: true
  })
})
.then(res => res.json())
.then(data => console.log('Task ID:', data.task_id));
```

### 2. Scheduler Automatique (Cron)
```python
# scheduler.py
import requests
import schedule

def run_daily_lettrage():
    requests.post('http://localhost:8000/api/lettrage', json={
        'excel_file': 'C:\\data\\daily.xlsx',
        'headless': True
    })

schedule.every().day.at("09:00").do(run_daily_lettrage)
```

### 3. Webhook après Traitement
Modifier `api/main.py` pour ajouter un webhook quand c'est terminé

## ⚙️ Configuration Avancée

### Changer le Port

```python
# Dans api/main.py, dernière ligne:
uvicorn.run(app, host="0.0.0.0", port=9000)  # Au lieu de 8000
```

### Activer CORS (pour frontend web)

```python
# Dans api/main.py, ajouter:
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production: liste d'URLs autorisées
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 🐛 Dépannage

### Port déjà utilisé
```bash
# Changer le port dans api/main.py
uvicorn.run(app, host="0.0.0.0", port=9000)
```

### API ne démarre pas
```bash
# Vérifier les dépendances
pip install fastapi uvicorn python-multipart

# Vérifier le dossier
cd C:\Users\m.astitou\Desktop\selenuim\sage-x3-rpa
python api/main.py
```

### Erreur "Module not found"
```bash
# S'assurer d'être dans le bon dossier
cd sage-x3-rpa
python api/main.py
```

---

✅ **Votre API est prête à l'emploi en 2 minutes !**
