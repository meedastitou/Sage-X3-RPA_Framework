# Guide de Démarrage Rapide

## Installation (1 minute)

```bash
cd C:\Users\m.astitou\Desktop\selenuim\sage-x3-rpa
pip install -r requirements.txt
```

## 🎯 Utilisation Immédiate

### Option 1: Script de test simple
```bash
# Modifiez le chemin du fichier Excel dans test_lettrage.py ligne 17
python test_lettrage.py
```

### Option 2: Script avec arguments
```bash
# Avec votre fichier Excel
python scripts\run_lettrage.py --file "C:\Users\m.astitou\Desktop\selenuim\reglement a annuler.xlsx"

# Mode headless (sans interface)
python scripts\run_lettrage.py --file "votre_fichier.xlsx" --headless
```

### Option 3: Depuis data/input/excel
```bash
# 1. Copier votre fichier Excel
copy "C:\Users\m.astitou\Desktop\selenuim\reglement a annuler.xlsx" data\input\excel\fournisseurs.xlsx

# 2. Lancer
python scripts\run_lettrage.py --file data\input\excel\fournisseurs.xlsx
```

##  Format du fichier Excel

Votre fichier doit contenir ces colonnes :
- **Compte** (ex: 44110000)
- **Code** (ex: T2504)
- **Facture** (ex: FF169917)
- **N-Avis** (ex: ECAHI00003)
- **Nom** (optionnel, ex: SANI ROCHE)

## 📁 Où trouver les résultats ?

- **Rapports Excel** : `data/output/rapports/rapport_lettrage_*.xlsx`
- **Logs détaillés** : `data/output/logs/lettrage_*.log`

## 🎨 Structure du Projet

```
sage-x3-rpa/
├── config/              # Configuration (settings.py, .env)
├── core/                # Framework réutilisable
│   ├── base_robot.py
│   ├── sage_connector.py
│   ├── driver_manager.py
│   └── logger.py
├── modules/
│   └── lettrage/
│       └── lettrage_robot.py    # VOTRE CODE ICI
├── data/
│   ├── input/excel/             # Vos fichiers Excel
│   └── output/
│       ├── rapports/            # Rapports générés
│       └── logs/                # Logs détaillés
├── scripts/
│   └── run_lettrage.py          # Point d'entrée
└── test_lettrage.py             # Script de test rapide
```

## 🔧 Configuration

Éditez `.env` pour modifier :
- URL Sage X3
- Identifiants
- Paramètres Selenium
- Clé API IA (Groq)

## 🐛 Dépannage

### Erreur "Module not found"
```bash
pip install -r requirements.txt
```

### Erreur Selenium
```bash
# Mettre à jour ChromeDriver
pip install --upgrade selenium
```

### Logs pour déboguer
```bash
# Voir les logs en temps réel
type data\output\logs\lettrage_*.log
```

## 💡 Exemples Avancés

### 1. Traiter un fichier spécifique
```bash
python scripts\run_lettrage.py --file "mon_fichier.xlsx"
```

### 2. Mode silencieux (headless)
```bash
python scripts\run_lettrage.py --file "mon_fichier.xlsx" --headless
```

### 3. URL personnalisée
```bash
python scripts\run_lettrage.py --file "mon_fichier.xlsx" --url "http://..."
```

## 🎯 Prochaines Étapes

1. **Tester** avec votre fichier Excel
2. 📖 **Lire** le README.md complet
3. 🔧 **Personnaliser** les paramètres dans `.env`
4. **Ajouter** de nouveaux modules (facturation, reporting...)

## 📞 Support

- Vérifier les logs : `data/output/logs/`
- Vérifier les rapports : `data/output/rapports/`
- Consulter README.md pour la doc complète

---

🎉 **Votre framework est prêt à l'emploi !**
