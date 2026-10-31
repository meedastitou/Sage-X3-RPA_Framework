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
            # 1. Trouver le checkbox par son label
            checkbox = self.robot.get_input_by_label(flag_name)

            if checkbox is None:
                return self.build_result(
                    'UPDATE_FLAG',
                    'Echec',
                    f"Checkbox '{flag_name}' introuvable",
                    flag=flag_name,
                    value=value
                )

            # 2. Vérifier l'état actuel
            is_checked = checkbox.is_selected()
            self.logger.info(f"État actuel du flag '{flag_name}': {is_checked}")

            # 3. Si l'état est déjà correct, ne rien faire
            if is_checked == value:
                self.logger.info(f"✅ Flag '{flag_name}' déjà à la valeur souhaitée: {value}")
                return self.build_result(
                    'UPDATE_FLAG',
                    'Succes',
                    f"Flag '{flag_name}' déjà à la valeur {value} (aucune modification nécessaire)",
                    flag=flag_name,
                    value=value,
                    modified=False
                )

            # 4. Cliquer sur le label pour changer l'état
            label = self.driver.find_element(
                By.CSS_SELECTOR,
                f"label[for='{checkbox.get_attribute('id')}']"
            )
            label.click()
            time.sleep(0.5)

            # 5. Vérifier que le changement a bien été appliqué
            new_state = checkbox.is_selected()
            if new_state == value:
                self.logger.info(f"✅ Flag '{flag_name}' modifié avec succès à {value}")
                return self.build_result(
                    'UPDATE_FLAG',
                    'Succes',
                    f"Flag '{flag_name}' modifié de {is_checked} à {value}",
                    flag=flag_name,
                    value=value,
                    modified=True,
                    ancien_etat=is_checked
                )
            else:
                return self.build_result(
                    'UPDATE_FLAG',
                    'Echec',
                    f"Le flag '{flag_name}' n'a pas changé (état: {new_state}, attendu: {value})",
                    flag=flag_name,
                    value=value
                )

        except Exception as e:
            return self.handle_error('UPDATE_FLAG', e, f"Modification flag '{flag_name}'")
