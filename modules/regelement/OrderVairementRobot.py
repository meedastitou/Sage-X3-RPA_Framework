# ====================================================================
# Sage X3 RPA - Robot de ordre de virement
# Version 1 - 13/02/2026
# Objectif : Automatiser la création d'ordres de virement dans Sage X3
# ====================================================================

from __future__ import annotations
from typing import Dict, Any, List, TYPE_CHECKING
import pandas as pd
from core.logger import Logger

if TYPE_CHECKING:
    from modules.regelement.VairementRobot import VairementRobot

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time
from selenium import webdriver



class OrderVairementRobot:
    """
    Helper pour la création d'ordres de virement dans Sage X3.
    Utilise le sage_connector du robot parent (VairementRobot)
    pour partager la même session navigateur.
    """
        # Au niveau du module (ou comme attribut de classe) : construit une seule fois
    TYPES_OPERATION_VIREMENT = {
        1: "virement ordinaire",
        2: "virement permanent",
        3: "virement compte à compte",
        4: "versement",
        5: "Douane",
        6: "Virement STC",
        7: "Virement de masse",
    }

    def __init__(self, parent_robot: VairementRobot):
        self.logger = Logger.get_logger('OrderVairementRobot', 'order_virement')
        self.parent = parent_robot
        self.sage_connector = parent_robot.sage_connector

        self.url_order_virement = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESXOVIR%252F2%252F%252FM%252F"

    def get_numero_order_virement(self, df: pd.DataFrame) -> str:
        driver = None
        try:
            self.logger.info("🚀 Démarrage du OrderVairementRobot...")
            self.sage_connector.navigate_to_module(self.url_order_virement)
            driver = self.sage_connector.driver_manager.driver

            if not self._cree_order_vairement(driver):
                raise Exception("Impossible de créer un nouvel ordre de virement")
            self.parent.wait_for_spinner_to_disappear(driver, 120)

            if not self._saisir_champs(driver, df):
                raise Exception("Échec de la saisie des champs")

            input("⏸️ Vérifiez le formulaire dans Sage X3, puis appuyez sur Entrée pour enregistrer...")

            if not self._enregistrer_order_vairement(driver):   
                raise Exception("Échec de l'enregistrement")

            numero_ov = self.read_numero_order_virement(driver)
            if not numero_ov:
                raise Exception("Numéro d'ordre de virement introuvable")

            self.logger.info(f"✅ Numéro d'ordre de virement récupéré: {numero_ov}")
            return numero_ov

        except Exception as e:
            self.logger.exception("❌ Erreur dans get_numero_order_virement")
            raise Exception(f"Problème dans get_numero_order_virement : {e}") from e
        finally:
            if driver is not None:
                try:
                    self.parent.wait_for_spinner_to_disappear(driver, 120)
                    self.parent.close_module()
                    time.sleep(2)
                except Exception:
                    self.logger.exception("Erreur lors de la fermeture du module")
    
    def _cree_order_vairement(self, driver : webdriver.Chrome) -> bool:
        """Cliquer sur le bouton 'Créer order vairement'"""
        try:
            time.sleep(5)
            add_button = driver.find_element(By.CSS_SELECTOR, "a.s_page_action_add")

            if "s-disabled" in add_button.get_attribute("class"):
                # Bouton désactivé 
                self.logger.info(" Bouton Add désactivé, impossible de créer un nouveau ordre de virement")
                return False
            else:
                # Bouton activé
                self.logger.info("Nouvel ordre de virement créé")
                add_button.click()
                time.sleep(2)
                return True
        except Exception as e:
            self.logger.error(f" Erreur création ordre de virement: {e}")
            return False

    def select_operation_type(self, driver : webdriver.Chrome, value="virement ordinaire"):
        # 1. Ouvrir la liste déroulante
        field = driver.find_element(By.XPATH, "//label[contains(text(), 'Type')]/following::a[1]")
        field.click()
        
        # 2. Attendre et sélectionner
        wait = WebDriverWait(driver, 10)
        option = wait.until(
            EC.element_to_be_clickable((By.XPATH, f"//a[@title='{value}']"))
        )
        option.click()
        
        # 3. Vérifier que la valeur est sélectionnée
        input_value = driver.find_element(By.ID, "2-55-input").get_attribute("value")
        assert input_value == value, f"Erreur: {input_value} au lieu de {value}"
        
        return True
    
    def _switch_to_type_operation(self, type_vairement) -> str:
        """Convertit le code type_virement (Excel) en libellé du type d'opération Sage X3."""
        try:
            code = int(float(type_vairement))
        except (TypeError, ValueError):
            raise ValueError(f"type_virement invalide : {type_vairement!r}")

        try:
            return self.TYPES_OPERATION_VIREMENT[code]
        except KeyError:
            valides = ", ".join(str(k) for k in self.TYPES_OPERATION_VIREMENT)
            raise ValueError(f"type_virement inconnu : {code}. Valeurs possibles : {valides}")

    def _saisir_champs(self, driver: webdriver.Chrome, df: pd.DataFrame) -> bool:
        montant = df.iloc[0]['Montant']
        type_vairement = df.iloc[0]['type_virement']
        objet = df.iloc[0]['objet']
        codeFrs = df.iloc[0]['Code_Frs']

        objet_txt = str(objet).strip() if pd.notna(objet) else ""
        code_frs_txt = str(codeFrs).strip() if pd.notna(codeFrs) else ""

        try:
            type_operation = self._switch_to_type_operation(type_vairement)
            if not self.select_operation_type(driver, value=type_operation):
                self.logger.error(" Impossible de sélectionner le type d'opération")
                return False

            ref_input = self.parent.get_input_by_label("Réference")
            ref_input.send_keys(objet_txt)
            time.sleep(0.5)

            objet_input = self.parent.get_input_by_label("Objet")
            objet_input.send_keys(objet_txt)
            time.sleep(2)

            montant_input = self.parent.get_input_by_label("Montant")
            montant_input.send_keys(str(montant))
            time.sleep(1.5)

            codeFrs_input = self.parent.get_input_by_label("Société")
            codeFrs_input.send_keys(code_frs_txt)
            time.sleep(2)

            self.parent.wait_for_spinner_to_disappear(driver, 60)
            time.sleep(2)

            # Observation = textarea (maxlength 250)
            self.parent.saisir_observation(driver, objet_txt[:250])
            time.sleep(0.5)

        except Exception as e:
            self.logger.exception("❌ Erreur pendant la saisie des champs")
            self.parent.capture_error_screenshot()
            raise Exception(f"Problème à la création : {e}") from e

        return True

    def _enregistrer_order_vairement(self, driver) -> bool:
        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_check")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()
            time.sleep(3)
            self.parent.wait_for_spinner_to_disappear(driver, 120)
            time.sleep(1)

            # Un popup d'erreur X3 a-t-il bloqué l'enregistrement ?
            msg = self.parent.read_popup_message()
            if msg:
                self.logger.error(f"❌ Message X3 après enregistrement : {msg}")
                self.parent.capture_error_screenshot()
            return True
        except Exception as e:
            self.logger.error(f" Erreur enregistrement: {e}")
            return False
        
    def read_numero_order_virement(self, driver, label: str = "N°Demande", timeout: int = 20) -> str | None:
        try:
            self.parent.wait_for_spinner_to_disappear(driver, 120)

            xpath = (
                f"//label[contains(normalize-space(.), '{label}')]"
                "/ancestor::div[contains(@class,'s-field')][1]//input[contains(@class,'s-field-input')]"
            )

            def _valeur(d):
                for el in d.find_elements(By.XPATH, xpath):
                    if el.is_displayed():
                        v = (el.get_attribute("value") or "").strip()
                        if v:
                            return v
                return False

            numero = WebDriverWait(driver, timeout).until(_valeur)
            self.logger.info(f"✅ Numéro d'ordre de virement récupéré: {numero}")
            return numero
        except Exception as e:
            self.logger.error(f"❌ Numéro introuvable (label '{label}'): {e}")
            # Aide au diagnostic : liste des inputs visibles avec leur valeur
            for el in driver.find_elements(By.XPATH, "//input[contains(@class,'s-field-input')]"):
                if el.is_displayed():
                    self.logger.info(f"input id={el.get_attribute('id')} value={el.get_attribute('value')!r}")
            self.parent.capture_error_screenshot()
            return None