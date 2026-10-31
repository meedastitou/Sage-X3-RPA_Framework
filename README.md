# 🤖 Sage X3 RPA Framework

Framework professionnel et scalable pour l'automatisation de Sage X3.

## 🎯 Modules Disponibles

- **Lettrage** : Lettrage automatique des fournisseurs (Excel, SQL, IA)
- 🔜 **Facturation** : Génération automatique de factures
- 🔜 **Reporting** : Génération de rapports automatisés

## 📁 Architecture

```
sage-x3-rpa/
├── config/          # Configuration centralisée
├── core/            # Framework de base (réutilisable)
├── modules/         # Modules métier (lettrage, facturation, ...)
├── data/            # Données (input/output)
├── utils/           # Utilitaires communs
├── scripts/         # Points d'entrée
└── tests/           # Tests unitaires
```

## Installation

### 1. Installer les dépendances
```bash
cd sage-x3-rpa
pip install -r requirements.txt
```

### 2. Configuration
Éditer le fichier `.env` avec vos paramètres Sage X3

## 💻 Utilisation

### Lettrage Simple (Excel)
```bash
python scripts\run_lettrage.py --file data\input\excel\fournisseurs.xlsx
```

### Mode Headless (sans interface)
```bash
python scripts\run_lettrage.py --file data\input\excel\fournisseurs.xlsx --headless
```

##  Format des fichiers Excel

### Lettrage
Le fichier Excel doit contenir les colonnes suivantes :

| Compte   | Code  | Facture  | N-Avis     | Nom (optionnel) |
|----------|-------|----------|------------|-----------------|
| 44110000 | T2504 | FF169917 | ECAHI00003 | SANI ROCHE      |

## 🏗️ Développer un nouveau module

### 1. Créer la structure
```bash
mkdir modules\mon_module
```

### 2. Hériter de BaseRobot
```python
from core.base_robot import BaseRobot

class MonModuleRobot(BaseRobot):
    def __init__(self):
        super().__init__('mon_module')
    
    def execute(self, *args, **kwargs):
        # Votre logique ici
        self.connect_sage()
        # ...
        self.add_result({'statut': 'Succes'})
```

### 3. Créer le script de lancement
```python
# scripts/run_mon_module.py
from modules.mon_module.mon_module_robot import MonModuleRobot

robot = MonModuleRobot()
robot.run()
```

## 📈 Rapports

Les rapports sont automatiquement générés dans `data/output/rapports/` avec :
- Horodatage automatique
- Format Excel
- Sauvegarde incrémentale (optionnel)
- Statistiques de réussite/échec

## 📝 Logs

Les logs sont sauvegardés dans `data/output/logs/` avec :
- Horodatage automatique
- Logs console + fichier
- Niveaux configurables (DEBUG, INFO, WARNING, ERROR)

## 🔐 Sécurité

-  Ne jamais committer `.env` ou `credentials.json`
- Utiliser des variables d'environnement
- Ajouter les fichiers sensibles dans `.gitignore`

## 🎯 Roadmap

- [x] Module Lettrage (base)
- [ ] Module Lettrage (IA)
- [ ] Module Lettrage (SQL)
- [ ] Module Facturation
- [ ] Module Reporting
- [ ] API REST
- [ ] Interface Web

## 📞 Support

Pour toute question :
1. Vérifier les logs dans `data/output/logs/`
2. Consulter la documentation
3. Créer une issue

## 📄 Licence

Propriétaire - Usage interne uniquement
