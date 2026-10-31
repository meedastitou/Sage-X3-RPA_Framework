# -*- coding: utf-8 -*-
"""
Action Handlers - Strategy Pattern
Classe de base abstraite pour tous les handlers d'actions
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .UpdateBonCommandeRobot import UpdateBonCommandeRobot


class ActionHandler(ABC):
    """
    Interface abstraite pour tous les handlers d'actions

    Chaque type d'action (UPDATE_FLAG, UPDATE_LIGNE_PRIX, etc.)
    doit implémenter cette interface
    """

    def __init__(self, robot: 'UpdateBonCommandeRobot'):
        """
        Initialiser le handler avec le robot parent

        Args:
            robot: Instance du UpdateBonCommandeRobot
        """
        self.robot = robot
        self.driver = robot.driver_manager.driver
        self.logger = robot.logger

    @abstractmethod
    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exécuter l'action et retourner le résultat

        Args:
            action: Dictionnaire contenant type, target, payload

        Returns:
            Dictionnaire avec le résultat de l'action
            {
                'type': str,
                'statut': 'Succes' | 'Echec',
                'message': str,
                ... autres champs spécifiques
            }
        """
        pass

    def build_result(self, action_type: str, statut: str, message: str, **extra) -> Dict[str, Any]:
        """
        Helper pour construire un résultat standardisé

        Args:
            action_type: Type d'action (ex: 'UPDATE_FLAG')
            statut: 'Succes' ou 'Echec'
            message: Message descriptif
            **extra: Champs additionnels spécifiques à l'action

        Returns:
            Dictionnaire de résultat formaté
        """
        return {
            'type': action_type,
            'statut': statut,
            'message': message,
            **extra
        }

    def handle_error(self, action_type: str, error: Exception, context: str = "") -> Dict[str, Any]:
        """
        Gérer une erreur et construire un résultat d'échec

        Args:
            action_type: Type d'action
            error: Exception levée
            context: Contexte de l'erreur

        Returns:
            Dictionnaire de résultat d'échec
        """
        error_message = f"{context}: {str(error)}" if context else str(error)
        self.logger.error(f"❌ Erreur {action_type}: {error_message}")

        # Capturer screenshot et popup
        error_info = self.robot.handle_error_with_screenshot(
            error_message=error_message,
            context=f"{action_type} - {context}"
        )

        return self.build_result(
            action_type,
            'Echec',
            error_message,
            error_info=error_info
        )
