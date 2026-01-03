# ⚡ DÉMARRAGE RAPIDE - Envoi Résultats Web

## 🎯 Configuration en 3 Minutes

### 1. **Éditer `.env`**

```env
# Modifier cette ligne avec votre URL
WEB_ENDPOINT_URL=http://jbel-annour.ma/resultat

# Activer l'envoi
WEB_ENDPOINT_ENABLED=True

# Mode d'envoi (json, multipart, ou base64)
WEB_ENDPOINT_MODE=json

# Inclure le fichier Excel dans l'envoi
WEB_ENDPOINT_INCLUDE_FILE=True
```

### 2. **Installer la dépendance**

```bash
cd C:\Users\m.astitou\Desktop\selenuim\sage-x3-rpa
pip install requests
```

### 3. **Tester**

```bash
python tests/test_web_endpoint.py
```

## 🚀 Utilisation

### **Automatique (Recommandé)**

L'envoi se fait automatiquement à la fin de chaque robot :

```bash
# Lancer n'importe quel robot
python scripts/run_bonne_commande.py --file commandes.xlsx

# À la fin, les résultats sont automatiquement envoyés
```

### **Via l'API REST**

```bash
# Démarrer l'API
python api/main.py

# Déclencher un robot
curl -X POST "http://localhost:8000/api/bonne-commande" \
  -H "Content-Type: application/json" \
  -d '{"excel_file": "commandes.xlsx", "headless": false}'

# Les résultats sont automatiquement envoyés à jbel-annour.ma
```

## 📋 Format des Données Envoyées

```json
{
  "module": "bonne_commande",
  "timestamp": "2025-12-29T15:30:00",
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
  "rapport_path": "C:\\...\\rapport.xlsx"
}
```

## 🔒 Ajouter une Authentification

```env
# Token Bearer
WEB_ENDPOINT_AUTH_TOKEN=Bearer votre_token_ici

# Ou API Key
WEB_ENDPOINT_API_KEY=sk-1234567890
```

## 🔧 Désactiver Temporairement

```env
WEB_ENDPOINT_ENABLED=False
```

## 🐛 Dépannage

### Erreur de connexion ?

1. Vérifier que `jbel-annour.ma/resultat` est accessible
2. Tester avec curl :
```bash
curl -X POST "http://jbel-annour.ma/resultat" \
  -H "Content-Type: application/json" \
  -d '{"test": "hello"}'
```

### Timeout ?

```env
WEB_ENDPOINT_TIMEOUT=60  # Augmenter à 60 secondes
```

### Retry en cas d'échec ?

```env
WEB_ENDPOINT_RETRY=True
WEB_ENDPOINT_RETRY_COUNT=5
WEB_ENDPOINT_RETRY_DELAY=10
```

## 📖 Documentation Complète

Voir `docs/WEB_ENDPOINT.md` pour :
- Exemples de serveurs récepteurs (Flask, Express, PHP)
- Tous les modes d'envoi
- Gestion avancée
- Logs et debugging

---

✅ **Configuration terminée en 3 minutes !**
