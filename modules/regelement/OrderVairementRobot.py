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

    def __init__(self, parent_robot: VairementRobot):
        self.logger = Logger.get_logger('OrderVairementRobot', 'order_virement')
        self.parent = parent_robot
        self.sage_connector = parent_robot.sage_connector

        self.url_order_virement = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESXOVIR%252F2%252F%252FM%252F"

    def get_numero_order_virement(self, df: pd.DataFrame) -> str:
        """Récupérer le numéro d'ordre de virement depuis le DataFrame"""

        try:
            self.logger.info("🚀 Démarrage du OrderVairementRobot pour récupérer le numéro d'ordre de virement...")
            self.sage_connector.navigate_to_module(self.url_order_virement)
            driver = self.sage_connector.driver_manager.driver

            self._cree_order_vairement(driver)
            self.parent.wait_for_spinner_to_disappear(driver, 120)

            self._saisir_champs(driver, df)

            input("wait befor enregistrer")
            self._enregistrer_order_vairement(driver)

            input("wait befor read")
            numero_ov = self.read_numero_order_virement(driver)
            if numero_ov is not None:
                self.logger.info(f"✅ Numéro d'ordre de virement récupéré: {numero_ov}")
            else :
                raise Exception("se ne trouve pas le numero order de vairement")
        except:
            raise Exception("Brobleme dans la fonction get_numero_order_virement")    
        finally:
            self.parent.wait_for_spinner_to_disappear(driver, 120)
            self.parent.close_module()
            time.sleep(2)

        return numero_ov
    
    def _cree_order_vairement(self, driver : webdriver.Chrome) -> bool:
        """Cliquer sur le bouton 'Créer order vairement'"""
        try:
            time.sleep(5)
            add_button = driver.find_element(By.CSS_SELECTOR, "a.s_page_action_add")

            if "s-disabled" in add_button.get_attribute("class"):
                # Bouton désactivé 
                self.logger.info("❌ Bouton Add désactivé, impossible de créer un nouveau ordre de virement")
                return False
            else:
                # Bouton activé
                self.logger.info("✅ Nouvel ordre de virement créé")
                add_button.click()
                time.sleep(2)
                return True
        except Exception as e:
            self.logger.error(f"❌ Erreur création ordre de virement: {e}")
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

    def _saisir_champs(self, driver : webdriver.Chrome, df: pd.DataFrame) -> bool:
        # Exemple de saisie du champ "Montant"
        montant = df.iloc[0]['Montant'] if 'Montant' in df.columns else 1234.56  # Récupérer le montant depuis le DataFrame ou utiliser une valeur par défaut
        type_vairement = df.iloc[0]['type_virement'] if 'type_virement' in df.columns else "virement ordinaire"  # Récupérer le type de virement depuis le DataFrame ou utiliser une valeur par défaut
        objet = df.iloc[0]['objet'] if 'objet' in df.columns else "Paiement facture"  # Récupérer l'objet depuis le DataFrame ou utiliser une valeur par défaut
        codeFrs = df.iloc[0]['Code_Frs'] if 'Code_Frs' in df.columns else "T1234"  # Récupérer le code fournisseur depuis le DataFrame ou utiliser une valeur par défaut

        try:
            
            if not self.select_operation_type(driver, value="virement ordinaire"):
                self.logger.error("❌ Impossible de sélectionner le type d'opération")
                return False
            ref_input = self.parent.get_input_by_label("Réference")
            ref_input.send_keys(objet)
            time.sleep(0.5)

            objet_input = self.parent.get_input_by_label("Objet")
            objet_input.send_keys(objet)
            time.sleep(0.5)
            
            montant_input = self.parent.get_input_by_label("Montant")
            montant_input.send_keys(str(montant))
            time.sleep(0.5)
            
            codeFrs_input = self.parent.get_input_by_label("Société")
            codeFrs_input.send_keys(codeFrs)
            time.sleep(0.5)
            self.parent.wait_for_spinner_to_disappear(driver, 60)
            time.sleep(0.5)

            observation_input = self.parent.get_input_by_label("Observation")
            observation_input.send_keys(objet) 
            time.sleep(0.5)
        except:
            raise Exception('une probleme au mement de creation ')


        return True

    def _enregistrer_order_vairement(self, driver : webdriver.Chrome) -> bool:
        """Enregistrer le order de vairement"""

        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_check")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()

            time.sleep(5)
            
            self.parent.wait_for_spinner_to_disappear(driver, timeout=120000000)
            try:
                self.parent.wait_for_element_to_appear(driver, By.CSS_SELECTOR, "a.s_page_close", timeout=1000000)
                s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
                s_page_close.click()
                time.sleep(2)
            except:
                pass
            
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur enregistrement: {e}")
            return False
        
    def read_numero_order_virement(self, driver) -> str:
        """Lire le numéro d'ordre de virement affiché à l'écran après création"""
        try:
            # attend le spinner desppeare
            self.parent.wait_for_spinner_to_disappear(driver, 120)

            numero_ov_element = self.parent.get_input_by_label("N°Demande")
            numero_ov = numero_ov_element.text.strip()
            self.logger.info(f"✅ Numéro d'ordre de virement récupéré: {numero_ov}")
            return numero_ov
        except Exception as e:
            self.logger.error(f"❌ Erreur récupération numéro d'ordre de virement: {e}")
            return None