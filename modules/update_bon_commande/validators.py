# -*- coding: utf-8 -*-
"""
Validators - Validation des actions et données
"""
from typing import Dict, Any, Tuple


class ActionValidator:
    """
    Validateur pour les actions de mise à jour de BC

    Définit les champs requis pour chaque type d'action
    et fournit des méthodes de validation
    """

    # Champs requis pour chaque type d'action
    REQUIRED_FIELDS = {
        'UPDATE_FLAG': {
            'target': ['bon_commande'],
            'payload': ['flag', 'value']
        },
        'UPDATE_LIGNE_PRIX': {
            'target': ['bon_commande', 'ligne'],
            'payload': ['nouveau_prix']
        },
        'UPDATE_LIGNE_QTE': {
            'target': ['bon_commande', 'ligne'],
            'payload': ['nouvelle_qte']
        },
        'UPDATE_LIGNE_REMISE': {
            'target': ['bon_commande', 'ligne'],
            'payload': ['nouvelle_remise']
        },
        'UPDATE_STATUT': {
            'target': ['bon_commande'],
            'payload': ['statut']
        },
        'UPDATE_DATE_LIVRAISON': {
            'target': ['bon_commande'],
            'payload': ['nouvelle_date']
        },
        'UPDATE_COMMENTAIRE': {
            'target': ['bon_commande'],
            'payload': ['commentaire']
        },
        'DELETE_LIGNE': {
            'target': ['bon_commande', 'ligne'],
            'payload': []
        },
        'ADD_LIGNE': {
            'target': ['bon_commande'],
            'payload': ['article', 'quantite', 'prix']
        }
    }

    @classmethod
    def validate(cls, action: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Valider une action

        Args:
            action: Dictionnaire de l'action à valider

        Returns:
            Tuple (is_valid, error_message)
            - is_valid: True si l'action est valide
            - error_message: Message d'erreur si invalide, "" sinon
        """
        # Vérifier le type
        if 'type' not in action:
            return False, "Champ 'type' manquant dans l'action"

        action_type = action['type']

        if action_type not in cls.REQUIRED_FIELDS:
            supported_types = ', '.join(cls.REQUIRED_FIELDS.keys())
            return False, f"Type d'action inconnu: '{action_type}'. Types supportés: {supported_types}"

        required = cls.REQUIRED_FIELDS[action_type]

        # Vérifier target
        if 'target' not in action:
            return False, f"Champ 'target' manquant pour action '{action_type}'"

        for field in required['target']:
            if field not in action['target']:
                return False, f"Champ 'target.{field}' manquant pour action '{action_type}'"

        # Vérifier payload
        if 'payload' not in action:
            return False, f"Champ 'payload' manquant pour action '{action_type}'"

        for field in required['payload']:
            if field not in action['payload']:
                return False, f"Champ 'payload.{field}' manquant pour action '{action_type}'"

        return True, ""

    @classmethod
    def validate_task_data(cls, task_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Valider la structure complète d'une tâche

        Args:
            task_data: Données de la tâche

        Returns:
            Tuple (is_valid, error_message)
        """
        # Vérifier task_type
        if 'task_type' not in task_data:
            return False, "Champ 'task_type' manquant"

        if task_data['task_type'] != 'update_bon_commande':
            return False, f"Type de tâche incorrect: '{task_data['task_type']}' (attendu: 'update_bon_commande')"

        # Vérifier bon_commande
        if 'bon_commande' not in task_data:
            return False, "Champ 'bon_commande' manquant"

        if 'numero' not in task_data['bon_commande']:
            return False, "Champ 'bon_commande.numero' manquant"

        # Vérifier actions
        if 'actions' not in task_data:
            return False, "Champ 'actions' manquant"

        if not isinstance(task_data['actions'], list):
            return False, "Le champ 'actions' doit être une liste"

        if len(task_data['actions']) == 0:
            return False, "La liste 'actions' est vide, au moins une action est requise"

        # Valider chaque action
        for idx, action in enumerate(task_data['actions'], 1):
            is_valid, error = cls.validate(action)
            if not is_valid:
                return False, f"Action #{idx} invalide: {error}"

        return True, ""

    @classmethod
    def get_supported_action_types(cls):
        """
        Retourner la liste des types d'actions supportés

        Returns:
            Liste des types d'actions supportés
        """
        return list(cls.REQUIRED_FIELDS.keys())
