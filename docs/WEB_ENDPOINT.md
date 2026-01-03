# 🌐 Envoi Automatique des Résultats vers Web Endpoint

## 🎯 Vue d'Ensemble

Le système RPA peut automatiquement envoyer les résultats de traitement vers votre endpoint web `jbel-annour.ma/resultat`.

## 📋 Configuration

### 1. **Fichier `.env`**

```env
# Endpoint Web
WEB_ENDPOINT_URL=http://jbel-annour.ma/resultat
WEB_ENDPOINT_ENABLED=True
WEB_ENDPOINT_MODE=json
WEB_ENDPOINT_INCLUDE_FILE=True
WEB_ENDPOINT_TIMEOUT=30

# Retry automatique
WEB_ENDPOINT_RETRY=True
WEB_ENDPOINT_RETRY_COUNT=3
WEB_ENDPOINT_RETRY_DELAY=5

# Authentification (optionnel)
WEB_ENDPOINT_AUTH_TOKEN=votre_token_ici
WEB_ENDPOINT_API_KEY=votre_api_key_ici
```

### 2. **Modes d'Envoi**

| Mode | Description | Usage |
|------|-------------|-------|
| `json` | JSON pur sans fichier | Résultats seulement |
| `multipart` | Form-data avec fichier | Résultats + Excel |
| `base64` | JSON avec fichier encodé | Résultats + Excel en base64 |

## 📤 Formats d'Envoi

### **Mode: `json` (sans fichier)**

**Requête HTTP :**
```http
POST http://jbel-annour.ma/resultat
Content-Type: application/json

{
  "module": "bonne_commande",
  "timestamp": "2025-12-29T10:35:00",
  "statut": "succes",
  "validation_passed": true,
  "statistiques": {
    "total_articles": 3,
    "articles_traites": 3,
    "articles_echec": 0,
    "total_das": 2,
    "das_traitees": 2,
    "das_echec": 0
  },
  "bc_genere": true,
  "rapport_path": "C:\\...\\rapport_bonne_commande_20251229_103500.xlsx"
}
```

### **Mode: `multipart` (avec fichier)**

**Requête HTTP :**
```http
POST http://jbel-annour.ma/resultat
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="module"

bonne_commande
------WebKitFormBoundary
Content-Disposition: form-data; name="statut"

succes
------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="rapport.xlsx"
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

[BINARY DATA]
------WebKitFormBoundary--
```

### **Mode: `base64` (fichier encodé)**

**Requête HTTP :**
```http
POST http://jbel-annour.ma/resultat
Content-Type: application/json

{
  "module": "bonne_commande",
  "statut": "succes",
  "statistiques": { ... },
  "file": {
    "filename": "rapport_bonne_commande_20251229.xlsx",
    "content": "UEsDBBQABgAIAAAAIQBi7p1o...",
    "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  }
}
```

## 🚀 Utilisation dans le Code

### **Option 1: Automatique (Recommandé)**

Le robot envoie automatiquement à la fin :

```python
from modules.bonne_commande.bonne_commande_robot import BonneCommandeRobot

robot = BonneCommandeRobot()
robot.run(excel_file='commandes.xlsx')

# L'envoi se fait automatiquement si WEB_ENDPOINT_ENABLED=True
```

### **Option 2: Manuel**

Contrôler l'envoi manuellement :

```python
from modules.bonne_commande.bonne_commande_robot import BonneCommandeRobot

robot = BonneCommandeRobot()
robot.run(excel_file='commandes.xlsx')

# Envoyer manuellement
result = robot.send_results_to_web(force=True)

if result and result['success']:
    print("✅ Résultats envoyés avec succès")
else:
    print(f"❌ Échec envoi: {result.get('message')}")
```

### **Option 3: Standalone**

Utiliser `ResultSender` directement :

```python
from utils.result_sender import ResultSender

sender = ResultSender('http://jbel-annour.ma/resultat')

# JSON seulement
data = {
    'module': 'test',
    'statut': 'succes',
    'message': 'Test envoi'
}
result = sender.send_json(data)

# Avec fichier
result = sender.send_with_file(
    data=data,
    file_path='rapport.xlsx'
)

# Base64
result = sender.send_base64_file(
    data=data,
    file_path='rapport.xlsx'
)
```

## 🔐 Authentification

### **Bearer Token**

```env
WEB_ENDPOINT_AUTH_TOKEN=Bearer eyJhbGciOiJIUzI1NiIs...
```

Le header sera automatiquement ajouté :
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### **API Key**

```env
WEB_ENDPOINT_API_KEY=sk-1234567890abcdef
```

Le header sera automatiquement ajouté :
```http
X-API-Key: sk-1234567890abcdef
```

## 🔄 Système de Retry

Si l'envoi échoue, le système réessaie automatiquement :

```
📤 Tentative 1/3
❌ Erreur: Connection timeout
⏳ Nouvelle tentative dans 5s...

📤 Tentative 2/3
❌ Erreur: Connection timeout
⏳ Nouvelle tentative dans 5s...

📤 Tentative 3/3
✅ Envoi réussi
```

**Configuration :**
```env
WEB_ENDPOINT_RETRY=True
WEB_ENDPOINT_RETRY_COUNT=3
WEB_ENDPOINT_RETRY_DELAY=5
```

## 📊 Structure des Données Envoyées

### **Bonne de Commande**

```json
{
  "module": "bonne_commande",
  "timestamp": "2025-12-29T10:35:00.123456",
  "statut": "succes" | "echec",
  "validation_passed": true,
  "statistiques": {
    "total_articles": 3,
    "articles_traites": 3,
    "articles_echec": 0,
    "total_das": 2,
    "das_traitees": 2,
    "das_echec": 0
  },
  "bc_genere": true,
  "rapport_path": "C:\\...\\rapport.xlsx",
  "details": {
    "total": 5,
    "succes": 5,
    "echecs": 0
  }
}
```

### **Lettrage**

```json
{
  "module": "lettrage",
  "timestamp": "2025-12-29T11:20:00.123456",
  "statut": "succes",
  "statistiques": {
    "total": 62,
    "succes": 58,
    "echecs": 4
  },
  "rapport_path": "C:\\...\\rapport_lettrage.xlsx",
  "details": {
    "total": 62,
    "succes": 58,
    "echecs": 4
  }
}
```

## 🖥️ Exemple de Serveur Récepteur (Backend)

### **Python Flask**

```python
from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route('/resultat', methods=['POST'])
def recevoir_resultat():
    # JSON seulement
    if request.is_json:
        data = request.get_json()
        print(f"✅ Résultat reçu: {data['module']} - {data['statut']}")
        
        # Sauvegarder en base de données...
        
        return jsonify({'success': True, 'message': 'Résultat reçu'})
    
    # Multipart avec fichier
    elif request.files:
        data = request.form.to_dict()
        file = request.files.get('file')
        
        if file:
            filename = f"rapport_{data['module']}_{data['timestamp']}.xlsx"
            file.save(f'uploads/{filename}')
            print(f"✅ Fichier sauvegardé: {filename}")
        
        return jsonify({'success': True, 'message': 'Résultat et fichier reçus'})
    
    return jsonify({'success': False, 'message': 'Format non supporté'}), 400

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(host='0.0.0.0', port=80)
```

### **Node.js Express**

```javascript
const express = require('express');
const multer = require('multer');
const upload = multer({ dest: 'uploads/' });

const app = express();
app.use(express.json());

app.post('/resultat', upload.single('file'), (req, res) => {
  // Avec fichier
  if (req.file) {
    console.log(`✅ Fichier reçu: ${req.file.originalname}`);
    console.log(`📊 Données: ${JSON.stringify(req.body)}`);
  }
  // JSON seulement
  else {
    console.log(`✅ Résultat reçu: ${req.body.module} - ${req.body.statut}`);
  }
  
  res.json({ success: true, message: 'Résultat reçu' });
});

app.listen(80, () => console.log('Serveur démarré sur port 80'));
```

### **PHP**

```php
<?php
header('Content-Type: application/json');

// JSON
if ($_SERVER['CONTENT_TYPE'] === 'application/json') {
    $data = json_decode(file_get_contents('php://input'), true);
    error_log("✅ Résultat reçu: " . $data['module'] . " - " . $data['statut']);
    
    // Sauvegarder en BDD...
    
    echo json_encode(['success' => true, 'message' => 'Résultat reçu']);
}
// Multipart
else if (isset($_FILES['file'])) {
    $module = $_POST['module'];
    $statut = $_POST['statut'];
    $file = $_FILES['file'];
    
    $filename = "uploads/rapport_{$module}_" . time() . ".xlsx";
    move_uploaded_file($file['tmp_name'], $filename);
    
    error_log("✅ Fichier sauvegardé: $filename");
    echo json_encode(['success' => true, 'message' => 'Résultat et fichier reçus']);
}
?>
```

## 🔍 Logs et Debugging

Les logs d'envoi sont disponibles dans :
```
data/output/logs/api_YYYYMMDD_HHMMSS.log
```

Exemple de log :
```
================================================================================
🌐 ENVOI DES RÉSULTATS VERS L'ENDPOINT WEB
================================================================================
📡 URL: http://jbel-annour.ma/resultat
📊 Mode: json
📤 Envoi JSON vers: http://jbel-annour.ma/resultat
✅ Envoi réussi (Status: 200)
✅ Envoi réussi (tentative 1/3)
================================================================================
```

## ⚙️ Désactiver l'Envoi

Pour désactiver temporairement :

```env
WEB_ENDPOINT_ENABLED=False
```

Ou dans le code :
```python
robot = BonneCommandeRobot()
robot.web_endpoint_config['enabled'] = False
robot.run(excel_file='commandes.xlsx')
# Aucun envoi ne sera effectué
```

## 📋 Checklist de Déploiement

- [ ] Configurer l'URL dans `.env`
- [ ] Activer l'envoi (`WEB_ENDPOINT_ENABLED=True`)
- [ ] Choisir le mode d'envoi
- [ ] Configurer l'authentification si nécessaire
- [ ] Tester avec un robot
- [ ] Vérifier les logs
- [ ] Vérifier la réception sur le serveur
- [ ] Configurer le retry si nécessaire

---

✅ **Envoi automatique des résultats configuré !**
