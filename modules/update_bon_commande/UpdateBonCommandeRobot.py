# -*- coding: utf-8 -*-
"""
Module UpdateBonCommande - Robot pour mettre à jour des BCs existants
Utilise les patterns Strategy et Factory pour une architecture extensible
"""
from typing import Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

from core.base_robot import BaseRobot
from core.web_result_mixin import WebResultMixin
from .handler_factory import get_handler_factory
from .validators import ActionValidator


class UpdateBonCommandeRobot(BaseRobot, WebResultMixin):
    """
    Robot pour la mise à jour de bons de commande existants

    Supporte plusieurs types d'actions:
    - UPDATE_FLAG: Modifier un checkbox/flag
    - UPDATE_LIGNE_PRIX: Modifier le prix d'une ligne
    - UPDATE_LIGNE_QTE: Modifier la quantité d'une ligne
    - UPDATE_STATUT: Changer le statut du BC
    - Et plus selon les handlers enregistrés

    Utilise:
    - Strategy Pattern: Chaque type d'action a son propre handler
    - Factory Pattern: Création dynamique des handlers
    - Template Method: Structure fixe du traitement
    """

    def __init__(self, headless: bool = False):
        """
        Initialiser le robot de mise à jour de BC

        Args:
            headless: Mode sans interface
        """
        # Initialiser BaseRobot
        BaseRobot.__init__(self, 'update_bon_commande')

        # Initialiser WebResultMixin
        WebResultMixin.__init__(self)

        self.driver_manager.headless = headless

        # Factory pour créer les handlers
        self.factory = get_handler_factory()

        # Validator pour valider les actions
        self.validator = ActionValidator()

        # URLs des modules
        self.url_bon_commande = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESPOH%252F2%252F%252FM%252F"

        # Compteurs
        self.actions_reussies = 0
        self.actions_echouees = 0
        self.bc_numero = None
        self.mode = 'permissif'  # 'strict' ou 'permissif'

        self.logger.info(f"🤖 Robot Update Bon Commande initialisé")
        self.logger.info(f"📋 Types d'actions supportés: {', '.join(self.factory.get_supported_types())}")

    def execute(self, task_data: Dict[str, Any]):
        """
        Exécuter le traitement de mise à jour d'un BC (Template Method)

        Args:
            task_data: Données de la tâche contenant:
                - task_type: "update_bon_commande"
                - bon_commande: { "numero": "BC2024-00123" }
                - actions: [ {...}, {...} ]
                - email: "user@example.com" (optionnel)
                - mode: "strict" ou "permissif" (optionnel, défaut: permissif)
        """
        email = task_data.get('email', '')

        try:
            # 1. Pré-traitement et validation
            if not self._pre_process(task_data):
                self._post_process_error(email, "Validation échouée")
                return

            # 2. Connexion Sage
            self.connect_sage()

            # 3. Traitement principal
            self._process_actions(task_data)

            # 4. Post-traitement
            self._post_process(task_data, email)

        except Exception as e:
            self._handle_error(e, task_data, email)

        finally:
            self.disconnect_sage()

    def _pre_process(self, task_data: Dict[str, Any]) -> bool:
        """
        Validation et préparation (Phase 1 du Template Method)

        Args:
            task_data: Données de la tâche

        Returns:
            True si la validation réussit, False sinon
        """
        self.logger.info("="*80)
        self.logger.info("📋 VALIDATION DE LA TÂCHE")
        self.logger.info("="*80)

        # Valider la structure complète
        is_valid, error = self.validator.validate_task_data(task_data)

        if not is_valid:
            self.logger.error(f"❌ {error}")
            self.add_result({
                'type': 'VALIDATION',
                'statut': 'Echec',
                'message': error
            })
            return False

        # Extraire les informations
        self.bc_numero = task_data['bon_commande']['numero']
        self.mode = task_data.get('mode', 'permissif')
        actions_count = len(task_data['actions'])

        self.logger.info(f"✅ Validation réussie")
        self.logger.info(f"   BC: {self.bc_numero}")
        self.logger.info(f"   Actions à traiter: {actions_count}")
        self.logger.info(f"   Mode: {self.mode}")

        # Afficher les actions
        for idx, action in enumerate(task_data['actions'], 1):
            self.logger.info(f"   {idx}. {action['type']}")

        return True

    def _process_actions(self, task_data: Dict[str, Any]):
        """
        Traiter toutes les actions (Phase 2 du Template Method)

        Args:
            task_data: Données de la tâche
        """
        self.logger.info("="*80)
        self.logger.info(f"🔧 TRAITEMENT DU BC {self.bc_numero}")
        self.logger.info("="*80)

        actions = task_data['actions']

        # 1. Ouvrir le BC en modification
        if not self._ouvrir_bc_modification(self.bc_numero):
            raise Exception(f"Impossible d'ouvrir le BC {self.bc_numero}")

        # 2. Traiter chaque action
        for idx, action in enumerate(actions, 1):
            self.logger.info(f"{'─'*80}")
            self.logger.info(f"🎯 Action {idx}/{len(actions)}: {action['type']}")
            self.logger.info(f"{'─'*80}")

            result = self._execute_single_action(action)
            self.add_result(result)

            if result['statut'] == 'Succes':
                self.actions_reussies += 1
                self.logger.info(f"✅ Action {idx} réussie ({self.actions_reussies}/{len(actions)})")
            else:
                self.actions_echouees += 1
                self.logger.error(f"❌ Action {idx} échouée: {result['message']}")

                # Si mode strict, arrêter immédiatement
                if self.mode == 'strict':
                    self.logger.error("⛔ MODE STRICT: Arrêt du traitement")
                    raise Exception(f"Action {idx} échouée: {result['message']}")

            time.sleep(1)

        # 3. Enregistrer le BC
        self.logger.info(f"{'─'*80}")
        if self._enregistrer_bc():
            self.logger.info("✅ BC enregistré avec succès")
        else:
            raise Exception("Échec de l'enregistrement du BC")

    def _execute_single_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exécuter une action via le factory pattern

        Args:
            action: Dictionnaire de l'action

        Returns:
            Résultat de l'action
        """
        action_type = action['type']

        try:
            # Créer le handler approprié via la factory
            handler = self.factory.create(action_type, self)

            # Exécuter l'action
            return handler.execute(action)

        except ValueError as e:
            # Type d'action non supporté
            return {
                'type': action_type,
                'statut': 'Echec',
                'message': str(e)
            }
        except Exception as e:
            # Erreur inattendue
            return {
                'type': action_type,
                'statut': 'Echec',
                'message': f"Erreur inattendue: {str(e)}"
            }

    def _post_process(self, task_data: Dict[str, Any], email: str):
        """
        Finalisation et envoi des résultats (Phase 3 du Template Method)

        Args:
            task_data: Données de la tâche
            email: Email pour l'envoi des résultats
        """
        self.logger.info("="*80)
        self.logger.info("📊 BILAN FINAL")
        self.logger.info("="*80)

        total_actions = len(task_data['actions'])
        statut_final = 'SUCCES' if self.actions_echouees == 0 else 'PARTIEL'

        self.logger.info(f"✅ Actions réussies: {self.actions_reussies}/{total_actions}")
        self.logger.info(f"❌ Actions échouées: {self.actions_echouees}/{total_actions}")
        self.logger.info(f"📋 Statut final: {statut_final}")

        # Ajouter un résultat final
        self.add_result({
            'type': 'BILAN_FINAL',
            'bc_numero': self.bc_numero,
            'actions_reussies': self.actions_reussies,
            'actions_echouees': self.actions_echouees,
            'total_actions': total_actions,
            'statut': statut_final,
            'mode': self.mode,
            'message': f"Traitement du BC {self.bc_numero} terminé: {self.actions_reussies}/{total_actions} actions réussies"
        })

        # Sauvegarder le rapport
        self.save_report()

        # Envoyer vers l'endpoint web
        if email:
            self.logger.info("✨ Envoi des résultats vers l'endpoint web...")
            # self.send_results_to_web(email)

    def _post_process_error(self, email: str, error_message: str):
        """
        Post-traitement en cas d'erreur de validation

        Args:
            email: Email pour l'envoi des résultats
            error_message: Message d'erreur
        """
        self.save_report()

        if email:
            self.logger.info("✨ Envoi des résultats d'erreur vers l'endpoint web...")
            # self.send_results_to_web(email)

    def _handle_error(self, error: Exception, task_data: Dict[str, Any], email: str):
        """
        Gérer une erreur critique

        Args:
            error: Exception levée
            task_data: Données de la tâche
            email: Email pour l'envoi
        """
        self.logger.error(f"❌ ERREUR CRITIQUE: {error}")
        import traceback
        self.logger.error(traceback.format_exc())

        # Capturer screenshot et popup
        error_info = self.handle_error_with_screenshot(
            error_message=str(error),
            context="Erreur Critique - Execute"
        )

        # Ajouter un résultat d'erreur
        self.add_result({
            'type': 'BILAN_FINAL',
            'bc_numero': self.bc_numero,
            'phase': 'Erreur_Critique',
            'statut': 'ERREUR',
            'actions_reussies': self.actions_reussies,
            'actions_echouees': self.actions_echouees,
            'message': f"Erreur critique: {str(error)}",
            'error_info': error_info
        })

        self.save_report()

        if email:
            self.logger.info("✨ Envoi des résultats vers l'endpoint web malgré l'erreur...")
            # self.send_results_to_web(email)

    def _ouvrir_bc_modification(self, bc_numero: str) -> bool:
        """
        Ouvrir un BC en mode modification

        Args:
            bc_numero: Numéro du BC à ouvrir

        Returns:
            True si le BC est ouvert, False sinon
        """
        self.logger.info(f"📂 Ouverture du BC {bc_numero} en modification...")

        driver = self.driver_manager.driver

        try:
            # Naviguer vers le module BC
            self.navigate_to_module(self.url_bon_commande)
            self.wait_stabilite()

            self.handle_popup("OK", " ")
            self.wait_stabilite()

            # Trouver la section "Commandes d’achat" (apostrophe ’ ou ')
            bc_section = driver.find_element(
                By.XPATH,
                "//header[.//a[contains(normalize-space(.), 'Commandes d')"
                " and contains(normalize-space(.), 'achat')]]/following-sibling::div[1]"
            )
            table_head = bc_section.find_element(By.CLASS_NAME, "s-grid-table-head")

            # Trouver le champ de recherche par numéro
            filter_row = table_head.find_element(By.XPATH, ".//tr[2]")
            chercher_bc = filter_row.find_element(By.XPATH, ".//td[2]//input")

            # Rechercher le BC
            chercher_bc.click()
            self.wait_stabilite()
            chercher_bc.clear()
            chercher_bc.send_keys(bc_numero)
            chercher_bc.send_keys(Keys.TAB)
            self.wait_stabilite()

            # Cliquer sur le BC trouvé
            table_body = bc_section.find_element(By.CLASS_NAME, "s-grid-table-body")
            premier_ligne = table_body.find_element(By.XPATH, ".//tr[1]")
            premier_ligne.click()
            self.wait_stabilite()

            self.logger.info(f"✅ BC {bc_numero} ouvert")
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur ouverture BC: {e}")
            self.handle_error_with_screenshot(
                error_message=str(e),
                context=f"Ouverture BC {bc_numero}"
            )
            return False

    def _enregistrer_bc(self) -> bool:
        """
        Enregistrer les modifications du BC

        Returns:
            True si l'enregistrement réussit, False sinon
        """
        driver = self.driver_manager.driver

        try:
            self.logger.info("💾 Enregistrement du BC...")

            # Trouver le bouton save
            save_btn = driver.find_element(
                By.CSS_SELECTOR,
                "div.s_page_action_i.s_page_action_i_save"
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()
            time.sleep(2)

            # Attendre la fin du spinner si présent
            s_lock_spinners = driver.find_elements(By.CSS_SELECTOR, "div.s_lock_long_spin")
            if s_lock_spinners:
                WebDriverWait(driver, 30).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.s_lock_long_spin"))
                )
                self.logger.info("⏳ Attente de la fin du chargement...")

            self.logger.info("✅ BC enregistré")
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur enregistrement BC: {e}")
            self.handle_error_with_screenshot(
                error_message=str(e),
                context="Enregistrement BC"
            )
            return False
