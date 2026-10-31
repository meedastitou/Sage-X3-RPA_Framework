# -*- coding: utf-8 -*-
"""
Handler pour UPDATE_LIGNE_PRIX - Modifier le prix d'une ligne
"""
from typing import Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

from ..action_handlers import ActionHandler


class UpdateLignePrixHandler(ActionHandler):
    """
    Handler pour modifier le prix unitaire d'une ligne de BC

    Exemple d'action:
    {
        "type": "UPDATE_LIGNE_PRIX",
        "target": {
            "bon_commande": "BC2024-00123",
            "ligne": 1,
            "article": "ART001"  # Optionnel, pour validation
        },
        "payload": {
            "ancien_prix": 100.0,  # Optionnel, pour validation
            "nouveau_prix": 95.5
        }
    }
    """

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modifier le prix d'une ligne

        Args:
            action: Action contenant le numéro de ligne et le nouveau prix

        Returns:
            Résultat de l'action
        """
        target = action['target']
        payload = action['payload']

        ligne_num = target['ligne']
        article = target.get('article', '')
        ancien_prix = payload.get('ancien_prix', None)
        nouveau_prix = payload['nouveau_prix']

        self.logger.info(f"💰 Modification du prix de la ligne {ligne_num}")
        if article:
            self.logger.info(f"   Article: {article}")
        self.logger.info(f"   Nouveau prix: {nouveau_prix}")

        try:
            # 1. Trouver la section des lignes de BC
            # Adapter selon la structure HTML de Sage X3
            lignes_section = self._find_lignes_section()

            if lignes_section is None:
                return self.build_result(
                    'UPDATE_LIGNE_PRIX',
                    'Echec',
                    "Section des lignes de BC introuvable",
                    ligne=ligne_num,
                    nouveau_prix=nouveau_prix
                )

            # 2. Naviguer vers la ligne spécifique
            ligne_row = self._find_ligne_by_number(lignes_section, ligne_num)

            if ligne_row is None:
                return self.build_result(
                    'UPDATE_LIGNE_PRIX',
                    'Echec',
                    f"Ligne {ligne_num} introuvable",
                    ligne=ligne_num,
                    nouveau_prix=nouveau_prix
                )

            # 3. Cliquer sur la ligne pour l'ouvrir
            ligne_row.click()
            time.sleep(1)

            # 4. Trouver le champ Prix
            prix_input = self.robot.get_input_by_label("Prix")

            if prix_input is None:
                return self.build_result(
                    'UPDATE_LIGNE_PRIX',
                    'Echec',
                    "Champ Prix introuvable",
                    ligne=ligne_num,
                    nouveau_prix=nouveau_prix
                )

            # 5. Capturer l'ancien prix si non fourni
            if ancien_prix is None:
                ancien_prix = prix_input.get_attribute('value')
                self.logger.info(f"   Prix actuel: {ancien_prix}")

            # 6. Modifier le prix
            prix_input.click()
            time.sleep(0.5)
            prix_input.clear()
            prix_input.send_keys(str(nouveau_prix))
            prix_input.send_keys(Keys.TAB)
            time.sleep(1)

            # 7. Vérifier s'il y a une erreur de validation
            if self._check_for_validation_error():
                error_msg = self._get_validation_error_message()
                return self.build_result(
                    'UPDATE_LIGNE_PRIX',
                    'Echec',
                    f"Erreur de validation: {error_msg}",
                    ligne=ligne_num,
                    nouveau_prix=nouveau_prix,
                    ancien_prix=ancien_prix
                )

            # 8. Succès
            self.logger.info(f"✅ Prix de la ligne {ligne_num} modifié: {ancien_prix} → {nouveau_prix}")
            return self.build_result(
                'UPDATE_LIGNE_PRIX',
                'Succes',
                f"Prix de la ligne {ligne_num} modifié avec succès",
                ligne=ligne_num,
                article=article,
                ancien_prix=ancien_prix,
                nouveau_prix=nouveau_prix
            )

        except Exception as e:
            return self.handle_error('UPDATE_LIGNE_PRIX', e, f"Ligne {ligne_num}")

    def _find_lignes_section(self):
        """Trouver la section des lignes du BC"""
        try:
            # Adapter selon la structure HTML de Sage X3
            # Exemple: chercher une section avec header "Lignes"
            return self.driver.find_element(
                By.XPATH,
                "//header[.//a[contains(text(), 'Lignes')]]/following-sibling::div[1]"
            )
        except:
            return None

    def _find_ligne_by_number(self, lignes_section, ligne_num: int):
        """Trouver une ligne par son numéro"""
        try:
            table_body = lignes_section.find_element(By.CLASS_NAME, "s-grid-table-body")
            # Les lignes commencent à l'index 1 en Selenium
            ligne_row = table_body.find_element(By.XPATH, f".//tr[{ligne_num}]")
            return ligne_row
        except:
            return None

    def _check_for_validation_error(self) -> bool:
        """Vérifier s'il y a une popup d'erreur"""
        try:
            error_elements = self.driver.find_elements(
                By.CSS_SELECTOR,
                "article.s_alertbox_content"
            )
            return len(error_elements) > 0
        except:
            return False

    def _get_validation_error_message(self) -> str:
        """Récupérer le message d'erreur de validation"""
        try:
            pre_elements = self.driver.find_elements(
                By.CSS_SELECTOR,
                "pre.s_alertbox_msg"
            )
            if pre_elements:
                return pre_elements[0].text
            return "Erreur inconnue"
        except:
            return "Impossible de lire le message d'erreur"
