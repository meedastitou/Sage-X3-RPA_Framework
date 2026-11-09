# -*- coding: utf-8 -*-
"""
Handler pour UPDATE_FLAG - Modifier un flag/checkbox
"""
from typing import Dict, Any
from selenium.webdriver.common.by import By
import time

from ..action_handlers import ActionHandler


class UpdateFlagHandler(ActionHandler):
    """
    Handler pour modifier un flag (checkbox) du BC

    Exemple d'action:
    {
        "type": "UPDATE_FLAG",
        "target": { "bon_commande": "BC2024-00123" },
        "payload": { "flag": "solde", "value": true }
    }
    """

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modifier un flag (checkbox)

        Args:
            action: Action contenant le nom du flag et la valeur

        Returns:
            Résultat de l'action
        """
        payload = action['payload']
        flag_name = payload['flag']
        value = payload['value']

        self.logger.info(f"🔄 Modification du flag '{flag_name}' à {value}")

        try:
            # 1. Trouver le button par son text
            button_solder_commande = self.driver.find_element(
                By.XPATH,
                "//a[contains(text(), 'Solder commande')]"
            )

            if button_solder_commande is None:
                return self.build_result(
                    'UPDATE_FLAG',
                    'Echec',
                    f"Button '{flag_name}' introuvable",
                    flag=flag_name,
                    value=value
                )

            input(f"Appuyez sur Entrée pour continuer après avoir modifié le flag '{flag_name}' dans l'interface...")
        except Exception as e:
            return self.handle_error('UPDATE_FLAG', e, f"Modification flag '{flag_name}'")
