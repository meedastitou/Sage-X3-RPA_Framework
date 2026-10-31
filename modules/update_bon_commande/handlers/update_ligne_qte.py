# -*- coding: utf-8 -*-
"""
Handler pour UPDATE_LIGNE_QTE - Modifier la quantité d'une ligne
"""
from typing import Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

from ..action_handlers import ActionHandler


class UpdateLigneQteHandler(ActionHandler):
    """
    Handler pour modifier la quantité d'une ligne de BC

    Exemple d'action:
    {
        "type": "UPDATE_LIGNE_QTE",
        "target": {
            "bon_commande": "BC2024-00123",
            "ligne": 2,
            "article": "ART045"  # Optionnel
        },
        "payload": {
            "ancienne_qte": 10,  # Optionnel, pour validation
            "nouvelle_qte": 15
        }
    }
    """

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modifier la quantité d'une ligne

        Args:
            action: Action contenant le numéro de ligne et la nouvelle quantité

        Returns:
            Résultat de l'action
        """
        target = action['target']
        payload = action['payload']

        ligne_num = target['ligne']
        article = target.get('article', '')
        ancienne_qte = payload.get('ancienne_qte', None)
        nouvelle_qte = payload['nouvelle_qte']

        self.logger.info(f"📦 Modification de la quantité de la ligne {ligne_num}")
        if article:
            self.logger.info(f"   Article: {article}")
        self.logger.info(f"   Nouvelle quantité: {nouvelle_qte}")

        try:
            # 1. Trouver la section des lignes de BC
            lignes_section = self._find_lignes_section()

            if lignes_section is None:
                return self.build_result(
                    'UPDATE_LIGNE_QTE',
                    'Echec',
                    "Section des lignes de BC introuvable",
                    ligne=ligne_num,
                    nouvelle_qte=nouvelle_qte
                )

            # 2. Naviguer vers la ligne spécifique
            ligne_row = self._find_ligne_by_number(lignes_section, ligne_num)

            if ligne_row is None:
                return self.build_result(
                    'UPDATE_LIGNE_QTE',
                    'Echec',
                    f"Ligne {ligne_num} introuvable",
                    ligne=ligne_num,
                    nouvelle_qte=nouvelle_qte
                )

            # 3. Cliquer sur la ligne pour l'ouvrir
            ligne_row.click()
            time.sleep(1)

            # 4. Trouver le champ Quantité
            # Adapter selon le label exact dans Sage X3
            qte_input = self.robot.get_input_by_label("Quantité")

            if qte_input is None:
                # Essayer avec d'autres labels possibles
                qte_input = self.robot.get_input_by_label("Qté")

            if qte_input is None:
                return self.build_result(
                    'UPDATE_LIGNE_QTE',
                    'Echec',
                    "Champ Quantité introuvable",
                    ligne=ligne_num,
                    nouvelle_qte=nouvelle_qte
                )

            # 5. Capturer l'ancienne quantité si non fournie
            if ancienne_qte is None:
                ancienne_qte = qte_input.get_attribute('value')
                self.logger.info(f"   Quantité actuelle: {ancienne_qte}")

            # 6. Modifier la quantité
            qte_input.click()
            time.sleep(0.5)
            qte_input.clear()
            qte_input.send_keys(str(nouvelle_qte))
            qte_input.send_keys(Keys.TAB)
            time.sleep(1)

            # 7. Vérifier s'il y a une erreur de validation
            if self._check_for_validation_error():
                error_msg = self._get_validation_error_message()
                return self.build_result(
                    'UPDATE_LIGNE_QTE',
                    'Echec',
                    f"Erreur de validation: {error_msg}",
                    ligne=ligne_num,
                    nouvelle_qte=nouvelle_qte,
                    ancienne_qte=ancienne_qte
                )

            # 8. Succès
            self.logger.info(f"✅ Quantité de la ligne {ligne_num} modifiée: {ancienne_qte} → {nouvelle_qte}")
            return self.build_result(
                'UPDATE_LIGNE_QTE',
                'Succes',
                f"Quantité de la ligne {ligne_num} modifiée avec succès",
                ligne=ligne_num,
                article=article,
                ancienne_qte=ancienne_qte,
                nouvelle_qte=nouvelle_qte
            )

        except Exception as e:
            return self.handle_error('UPDATE_LIGNE_QTE', e, f"Ligne {ligne_num}")

    def _find_lignes_section(self):
        """Trouver la section des lignes du BC"""
        try:
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
