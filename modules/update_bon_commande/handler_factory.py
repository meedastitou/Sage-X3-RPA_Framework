# -*- coding: utf-8 -*-
"""
Handler Factory - Factory Pattern
Crée et gère les handlers d'actions
"""
from typing import Dict, Type, TYPE_CHECKING

from .action_handlers import ActionHandler

if TYPE_CHECKING:
    from .UpdateBonCommandeRobot import UpdateBonCommandeRobot


class ActionHandlerFactory:
    """
    Factory pour créer les handlers d'actions

    Utilise le pattern Factory pour créer dynamiquement
    les handlers appropriés selon le type d'action
    """

    def __init__(self):
        """Initialiser la factory avec un registre vide"""
        self._handlers: Dict[str, Type[ActionHandler]] = {}

    def register(self, action_type: str, handler_class: Type[ActionHandler]):
        """
        Enregistrer un nouveau type d'action et son handler

        Args:
            action_type: Type d'action (ex: 'UPDATE_FLAG')
            handler_class: Classe du handler (doit hériter de ActionHandler)
        """
        if not issubclass(handler_class, ActionHandler):
            raise TypeError(f"Handler class must inherit from ActionHandler, got {handler_class}")

        self._handlers[action_type] = handler_class

    def create(self, action_type: str, robot: 'UpdateBonCommandeRobot') -> ActionHandler:
        """
        Créer une instance du handler approprié

        Args:
            action_type: Type d'action
            robot: Instance du robot parent

        Returns:
            Instance du handler approprié

        Raises:
            ValueError: Si le type d'action n'est pas supporté
        """
        if action_type not in self._handlers:
            supported_types = ', '.join(self._handlers.keys())
            raise ValueError(
                f"Type d'action non supporté: '{action_type}'. "
                f"Types disponibles: {supported_types}"
            )

        handler_class = self._handlers[action_type]
        return handler_class(robot)

    def is_supported(self, action_type: str) -> bool:
        """
        Vérifier si un type d'action est supporté

        Args:
            action_type: Type d'action à vérifier

        Returns:
            True si le type est supporté, False sinon
        """
        return action_type in self._handlers

    def get_supported_types(self):
        """
        Obtenir la liste des types d'actions supportés

        Returns:
            Liste des types d'actions enregistrés
        """
        return list(self._handlers.keys())


# Instance globale de la factory (Singleton pattern)
_global_factory = None


def get_handler_factory() -> ActionHandlerFactory:
    """
    Obtenir l'instance globale de la factory (Singleton)

    Returns:
        Instance globale de ActionHandlerFactory
    """
    global _global_factory

    if _global_factory is None:
        _global_factory = ActionHandlerFactory()
        _register_default_handlers(_global_factory)

    return _global_factory


def _register_default_handlers(factory: ActionHandlerFactory):
    """
    Enregistrer tous les handlers par défaut

    Cette fonction importe et enregistre tous les handlers disponibles
    dans le module handlers/

    Args:
        factory: Instance de la factory
    """
    # Import des handlers concrets
    # Note: Les imports sont faits ici pour éviter les imports circulaires
    try:
        from .handlers.update_flag import UpdateFlagHandler
        factory.register('UPDATE_FLAG', UpdateFlagHandler)
    except ImportError:
        pass

    try:
        from .handlers.update_ligne_prix import UpdateLignePrixHandler
        factory.register('UPDATE_LIGNE_PRIX', UpdateLignePrixHandler)
    except ImportError:
        pass

    try:
        from .handlers.update_ligne_qte import UpdateLigneQteHandler
        factory.register('UPDATE_LIGNE_QTE', UpdateLigneQteHandler)
    except ImportError:
        pass

    # try:
    #     from .handlers.update_ligne_remise import UpdateLigneRemiseHandler
    #     factory.register('UPDATE_LIGNE_REMISE', UpdateLigneRemiseHandler)
    # except ImportError:
    #     pass

    # try:
    #     from .handlers.update_statut import UpdateStatutHandler
    #     factory.register('UPDATE_STATUT', UpdateStatutHandler)
    # except ImportError:
    #     pass

    # try:
    #     from .handlers.update_date_livraison import UpdateDateLivraisonHandler
    #     factory.register('UPDATE_DATE_LIVRAISON', UpdateDateLivraisonHandler)
    # except ImportError:
    #     pass

    # try:
    #     from .handlers.update_commentaire import UpdateCommentaireHandler
    #     factory.register('UPDATE_COMMENTAIRE', UpdateCommentaireHandler)
    # except ImportError:
    #     pass

    # try:
    #     from .handlers.delete_ligne import DeleteLigneHandler
    #     factory.register('DELETE_LIGNE', DeleteLigneHandler)
    # except ImportError:
    #     pass

    # try:
    #     from .handlers.add_ligne import AddLigneHandler
    #     factory.register('ADD_LIGNE', AddLigneHandler)
    # except ImportError:
    #     pass
