# Module Update Bon Commande

Robot pour mettre à jour des bons de commande existants dans Sage X3.

## Architecture

Ce module utilise des patterns de conception pour une architecture extensible et maintenable:

- **Strategy Pattern**: Chaque type d'action a son propre handler
- **Factory Pattern**: Création dynamique des handlers appropriés
- **Template Method**: Structure fixe du traitement (pré-process → process → post-process)
- **Validation Pattern**: Validation stricte des données avant traitement

## Structure des Fichiers

```
modules/update_bon_commande/
├── __init__.py
├── UpdateBonCommandeRobot.py       # Robot principal (Template Method)
├── action_handlers.py               # Classe de base abstraite (Strategy)
├── handler_factory.py               # Factory pour créer les handlers
├── validators.py                    # Validation des actions
├── handlers/                        # Handlers concrets
│   ├── __init__.py
│   ├── update_flag.py              # Modifier un checkbox
│   ├── update_ligne_prix.py        # Modifier le prix d'une ligne
│   ├── update_ligne_qte.py         # Modifier la quantité d'une ligne
│   └── ...                          # Autres handlers
└── README.md
```

## Types d'Actions Supportés

### 1. UPDATE_FLAG - Modifier un Flag/Checkbox

Modifie un checkbox (ex: solde, validé, bloqué).

```json
{
  "type": "UPDATE_FLAG",
  "target": { "bon_commande": "BC2024-00123" },
  "payload": { "flag": "solde", "value": true }
}
```

### 2. UPDATE_LIGNE_PRIX - Modifier le Prix d'une Ligne

Modifie le prix unitaire d'une ligne de BC.

```json
{
  "type": "UPDATE_LIGNE_PRIX",
  "target": {
    "bon_commande": "BC2024-00123",
    "ligne": 1,
    "article": "ART001"
  },
  "payload": {
    "ancien_prix": 100.0,
    "nouveau_prix": 95.5
  }
}
```

### 3. UPDATE_LIGNE_QTE - Modifier la Quantité d'une Ligne

Modifie la quantité commandée d'une ligne.

```json
{
  "type": "UPDATE_LIGNE_QTE",
  "target": {
    "bon_commande": "BC2024-00123",
    "ligne": 2,
    "article": "ART045"
  },
  "payload": {
    "ancienne_qte": 10,
    "nouvelle_qte": 15
  }
}
```

## Format de Tâche Complet

```json
{
  "id": "task_123",
  "task_type": "update_bon_commande",
  "email": "user@example.com",
  "bon_commande": {
    "numero": "BC2024-00123"
  },
  "mode": "permissif",
  "actions": [
    {
      "type": "UPDATE_FLAG",
      "target": { "bon_commande": "BC2024-00123" },
      "payload": { "flag": "solde", "value": true }
    },
    {
      "type": "UPDATE_LIGNE_PRIX",
      "target": { "bon_commande": "BC2024-00123", "ligne": 1, "article": "ART001" },
      "payload": { "ancien_prix": 100.0, "nouveau_prix": 95.5 }
    },
    {
      "type": "UPDATE_LIGNE_QTE",
      "target": { "bon_commande": "BC2024-00123", "ligne": 2, "article": "ART045" },
      "payload": { "ancienne_qte": 10, "nouvelle_qte": 15 }
    }
  ]
}
```

## Modes de Traitement

### Mode Permissif (défaut)

Continue le traitement même si certaines actions échouent.

```json
{ "mode": "permissif" }
```

- Continue malgré les erreurs
- Toutes les actions sont tentées
- Le rapport final indique les succès et échecs

### Mode Strict

Arrête le traitement à la première erreur.

```json
{ "mode": "strict" }
```

- Arrêt immédiat au premier échec
- Les actions suivantes ne sont pas exécutées
- Le BC n'est pas enregistré

## Utilisation

### Via le Worker RPA

Le robot est automatiquement lancé par `worker_rpa.py` quand une tâche de type `update_bon_commande` est trouvée dans la file.

```python
# Le worker détecte automatiquement et lance le robot
# Aucune action manuelle requise
```

### Utilisation Directe

```python
from modules.update_bon_commande.UpdateBonCommandeRobot import UpdateBonCommandeRobot

# Créer le robot
robot = UpdateBonCommandeRobot()

# Préparer la tâche
task_data = {
    "task_type": "update_bon_commande",
    "bon_commande": { "numero": "BC2024-00123" },
    "email": "user@example.com",
    "mode": "permissif",
    "actions": [
        {
            "type": "UPDATE_FLAG",
            "target": { "bon_commande": "BC2024-00123" },
            "payload": { "flag": "solde", "value": True }
        }
    ]
}

# Exécuter
robot.execute(task_data)
```

## Ajouter un Nouveau Type d'Action

### 1. Créer le Handler

Créer un fichier dans `handlers/`, ex: `update_date_livraison.py`

```python
# -*- coding: utf-8 -*-
from typing import Dict, Any
from selenium.webdriver.common.keys import Keys
import time

from ..action_handlers import ActionHandler

class UpdateDateLivraisonHandler(ActionHandler):
    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        payload = action['payload']
        nouvelle_date = payload['nouvelle_date']

        try:
            # 1. Trouver le champ date
            date_input = self.robot.get_input_by_label("Date de livraison")

            # 2. Modifier la date
            date_input.clear()
            date_input.send_keys(nouvelle_date)
            date_input.send_keys(Keys.TAB)
            time.sleep(1)

            return self.build_result(
                'UPDATE_DATE_LIVRAISON',
                'Succes',
                f'Date de livraison modifiée à {nouvelle_date}',
                nouvelle_date=nouvelle_date
            )
        except Exception as e:
            return self.handle_error('UPDATE_DATE_LIVRAISON', e, "Modification date")
```

### 2. Enregistrer dans la Factory

Dans `handler_factory.py`, ajouter:

```python
try:
    from .handlers.update_date_livraison import UpdateDateLivraisonHandler
    factory.register('UPDATE_DATE_LIVRAISON', UpdateDateLivraisonHandler)
except ImportError:
    pass
```

### 3. Ajouter la Validation

Dans `validators.py`, ajouter:

```python
REQUIRED_FIELDS['UPDATE_DATE_LIVRAISON'] = {
    'target': ['bon_commande'],
    'payload': ['nouvelle_date']
}
```

### 4. Utiliser

```json
{
  "type": "UPDATE_DATE_LIVRAISON",
  "target": { "bon_commande": "BC2024-00123" },
  "payload": { "nouvelle_date": "2024-12-31" }
}
```

## Format des Résultats

Le robot génère un rapport JSON avec tous les résultats:

```json
{
  "module": "update_bon_commande",
  "timestamp": "2024-01-15 10:30:00",
  "results": [
    {
      "type": "UPDATE_FLAG",
      "statut": "Succes",
      "flag": "solde",
      "value": true,
      "message": "Flag 'solde' modifié de False à True"
    },
    {
      "type": "UPDATE_LIGNE_PRIX",
      "statut": "Succes",
      "ligne": 1,
      "article": "ART001",
      "ancien_prix": 100.0,
      "nouveau_prix": 95.5,
      "message": "Prix de la ligne 1 modifié avec succès"
    },
    {
      "type": "BILAN_FINAL",
      "bc_numero": "BC2024-00123",
      "actions_reussies": 2,
      "actions_echouees": 0,
      "total_actions": 2,
      "statut": "SUCCES",
      "mode": "permissif",
      "message": "Traitement du BC BC2024-00123 terminé: 2/2 actions réussies"
    }
  ]
}
```

## Gestion des Erreurs

Le robot capture automatiquement:

- Screenshots en cas d'erreur
- Messages des popups Sage X3
- Traces d'exception complètes
- Contexte de l'erreur (action en cours, BC, ligne, etc.)

Tous les détails sont inclus dans le rapport final et peuvent être envoyés vers l'endpoint web.

## Logs

Les logs sont écrits dans `logs/update_bon_commande/`:

- `update_bon_commande_YYYYMMDD.log` - Log principal
- Rotation automatique par jour

## Tests

### Tester un Handler Individuellement

```python
from modules.update_bon_commande.UpdateBonCommandeRobot import UpdateBonCommandeRobot
from modules.update_bon_commande.handlers.update_flag import UpdateFlagHandler

# Créer le robot
robot = UpdateBonCommandeRobot()
robot.connect_sage()

# Créer le handler
handler = UpdateFlagHandler(robot)

# Tester
action = {
    "type": "UPDATE_FLAG",
    "target": { "bon_commande": "BC2024-00123" },
    "payload": { "flag": "solde", "value": True }
}

result = handler.execute(action)
print(result)

robot.disconnect_sage()
```

## Bonnes Pratiques

### Pour les Développeurs

1. **Toujours hériter de `ActionHandler`** pour créer un nouveau handler
2. **Utiliser `build_result()`** pour construire les résultats
3. **Utiliser `handle_error()`** pour gérer les exceptions
4. **Tester chaque handler indépendamment** avant de l'intégrer
5. **Documenter les champs requis** dans les docstrings

### Pour les Utilisateurs

1. **Valider le JSON** avant de soumettre une tâche
2. **Utiliser le mode strict** pour des opérations critiques
3. **Tester d'abord avec peu d'actions** avant les gros volumes
4. **Vérifier les résultats** dans le rapport JSON

## Dépendances

- `core.base_robot.BaseRobot` - Classe parent
- `core.web_result_mixin.WebResultMixin` - Envoi résultats web
- `selenium` - Automation navigateur
- Python 3.7+

## Support

Pour ajouter de nouveaux types d'actions ou reporter des bugs, contactez l'équipe de développement.
