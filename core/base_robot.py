# -*- coding: utf-8 -*-
"""
Classe de base pour tous les robots RPA
"""
from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import Dict, Any, Optional, List
import pandas as pd
from pathlib import Path
import base64

from core.sage_connector import SageConnector
from core.driver_manager import DriverManager
from core.logger import Logger
from config.settings import OUTPUT_DIR
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class BaseRobot(ABC):
    """Classe de base abstraite pour tous les robots"""
    
    def __init__(self, module_name: str):
        """
        Initialiser le robot
        
        Args:
            module_name: Nom du module (lettrage, facturation, etc.)
        """
        self.module_name = module_name
        self.logger = Logger.get_logger(self.__class__.__name__, module_name)
        
        # Composants réutilisables
        self.driver_manager = DriverManager()
        self.sage_connector = SageConnector(self.driver_manager)
        
        # Données
        self.resultats = []
        self.rapport_path = None
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Gestion des erreurs (optionnel)
        self.error_screenshot = None
        self.popup_messages = []

        self.logger.info(f"🤖 Initialisation robot: {self.__class__.__name__}")
    
    @abstractmethod
    def execute(self, *args, **kwargs):
        """
        Méthode principale à implémenter par chaque robot
        
        Cette méthode doit contenir la logique métier principale
        """
        
        pass
    
    def connect_sage(self) -> bool:
        """
        Connexion à Sage X3
        
        Returns:
            True si connexion réussie
        """
        return self.sage_connector.connect()

    def disconnect_sage(self) -> bool:
        """
        Connexion à Sage X3
        
        Returns:
            True si déconnexion réussie
        """
        return self.sage_connector.disconnect()

    def navigate_to_module(self, url: str) -> bool:
        """
        Naviguer vers un module Sage

        Args:
            url: URL du module

        Returns:
            True si navigation réussie
        """
        return self.sage_connector.navigate_to_module(url)

    def close_module(self, confirm_abandon: bool = False) -> bool:
        """
        Fermer le module actuel en cours (sortie propre)

        Args:
            confirm_abandon: Si True, gère la popup "Continuer et abandonner votre création ?"

        Returns:
            True si fermeture réussie
        """
        driver = self.driver_manager.driver

        try:
            from selenium.webdriver.common.keys import Keys
            import time

            self.logger.info("🔒 Fermeture du module en cours...")

            # Envoyer ESCAPE pour sortir des formulaires/champs
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

            # Cliquer sur le bouton de fermeture de page
            s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
            s_page_close.click()
            time.sleep(1)

            # Gérer la popup de confirmation si nécessaire
            if confirm_abandon:
                try:
                    WebDriverWait(driver, 2).until(
                        EC.visibility_of_element_located((By.XPATH, "//pre[@class='s_alertbox_msg' and contains(text(), 'Continuer et abandonner votre création ?')]"))
                    )
                    # Cliquer sur "Oui"
                    oui_button = driver.find_element(By.XPATH, "//a[@aria-label='Oui']")
                    oui_button.click()
                    self.logger.info("Confirmation abandon cliquée")
                    time.sleep(1)
                except:
                    # Pas de popup ou autre type de popup
                    pass

            self.logger.info("Module fermé avec succès")
            return True

        except Exception as e:
            self.logger.error(f" Erreur fermeture module: {e}")
            return False

    def add_result(self, result: Dict[str, Any]):
        """
        Ajouter un résultat à la liste
        
        Args:
            result: Dictionnaire contenant les résultats
        """
        self.resultats.append(result)
        self.logger.debug(f"Résultat ajouté: {result}")
    
    def save_report(self, filename: str = None, incremental: bool = False) -> Path:
        """
        Sauvegarder le rapport Excel
        
        Args:
            filename: Nom personnalisé (optionnel)
            incremental: Mode sauvegarde incrémentale
        
        Returns:
            Chemin du fichier sauvegardé
        """
        try:
            # Créer le nom de fichier
            if not filename:
                if incremental and self.rapport_path:
                    filename = self.rapport_path.name
                else:
                    filename = f"rapport_{self.module_name}_{self.timestamp}.xlsx"
            
            # Chemin complet
            if not self.rapport_path or not incremental:
                self.rapport_path = OUTPUT_DIR / 'rapports' / filename
            
            # Créer DataFrame
            df = pd.DataFrame(self.resultats)
            
            # Sauvegarder
            self.rapport_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_excel(self.rapport_path, index=False)
            
            self.logger.info(f"💾 Rapport sauvegardé: {self.rapport_path} ({len(self.resultats)} ligne(s))")
            return self.rapport_path
            
        except Exception as e:
            self.logger.error(f" Erreur sauvegarde rapport: {e}")
            return None
    
    def generate_summary(self) -> Dict[str, Any]:
        """
        Générer un résumé des résultats
        
        Returns:
            Dictionnaire avec statistiques
        """
        if not self.resultats:
            return {'total': 0, 'succes': 0, 'echecs': 0}
        
        df = pd.DataFrame(self.resultats)
        
        summary = {
            'total': len(df),
            'succes': len(df[df.get('statut', '') == 'Succes']) if 'statut' in df.columns else 0,
            'echecs': len(df[df.get('statut', '') != 'Succes']) if 'statut' in df.columns else 0,
            'timestamp': self.timestamp,
            'module': self.module_name,
        }
        
        return summary
    
    def log_summary(self):
        """Afficher le résumé dans les logs"""
        summary = self.generate_summary()
        
        self.logger.info("\n" + "="*80)
        self.logger.info(" RÉSUMÉ FINAL")
        self.logger.info("="*80)
        self.logger.info(f"Total: {summary['total']}")
        self.logger.info(f"Succès: {summary['succes']}")
        self.logger.info(f" Échecs: {summary['echecs']}")
        
        if summary['total'] > 0:
            taux = (summary['succes'] / summary['total']) * 100
            self.logger.info(f"📈 Taux de réussite: {taux:.1f}%")
        
        self.logger.info("="*80)
    
    def wait_for_spinner_to_disappear(self, driver, timeout: int = 60):
        """
        Attendre que le spinner de chargement disparaisse

        Args:
            driver: Instance du driver Selenium
            timeout: Temps maximum d'attente en secondes
        """


        try:
            self.logger.info("⏳ Attente disparition du spinner...")
            WebDriverWait(driver, timeout).until(
                EC.invisibility_of_element_located((By.ID, "s_lock_long_spin"))
            )
        except Exception as e:
            pass

    def wait_for_element_to_appear(self, driver, by, value, timeout=30000):
        """Attendre qu'un élément soit visible"""
        wait = WebDriverWait(driver, timeout / 1000)
        wait.until(EC.visibility_of_element_located((by, value)))   

    def get_input_by_label(self, label_name: str, for_id: int = None):
        """
        Retourne l'élément input associé à un label

        Args:
            label_name: Le texte du label à chercher

        Returns:
            WebElement: L'élément input trouvé

        Raises:
            Exception: Si le label ou l'input n'est pas trouvé
        """
        driver = self.driver_manager.driver
        conditional_for = ""
        if for_id is not None:
            conditional_for = f" and contains(@for, '{for_id}-input')"
        try:
            input_element = driver.find_element(By.XPATH,
                f"//label[contains(@class, 's-field-title') and contains(text(), '{label_name}'){conditional_for}]/following::input[1]"
            )
            return input_element
        except Exception as e:
            self.logger.error(f" Erreur: impossible de trouver l'input pour le label '{label_name}': {e}")
            raise

    def handle_popup(self, button_text: str, message: str) -> bool:
        """
        Gérer une popup en cliquant sur un bouton spécifique
        
        Args:
            button_text: Texte du bouton à cliquer
            message: Message attendu dans la popup
        """
            
        driver = self.driver_manager.driver
        try:
            WebDriverWait(driver, 2).until(
                EC.visibility_of_element_located((By.XPATH, f"//pre[@class='s_alertbox_msg' and contains(text(), '{message}')]"))
            )
            popup_button = driver.find_element(By.XPATH, f"//a[@aria-label='{button_text}']")
            popup_button.click()
            time.sleep(1)
            return True
        except:
            # Pas de popup ou autre type de popup
            return False

    def cleanup(self):
        """Nettoyage et déconnexion"""
        try:
            if self.sage_connector:
                self.sage_connector.disconnect()
            self.logger.info("Nettoyage terminé")
        except Exception as e:
            self.logger.error(f"Erreur nettoyage: {e}")
    
    def run(self, *args, **kwargs):
        """
        Exécuter le robot avec gestion d'erreur
        
        Template Method Pattern
        """
        try:
            self.logger.info(f"Démarrage: {self.__class__.__name__}")
            
            # Exécuter la logique métier
            result = self.execute(*args, **kwargs)
            
            # Générer le rapport final
            self.log_summary()
            self.save_report()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Erreur fatale: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise
        
        finally:
            self.cleanup()
    
    def __enter__(self):
        """Context manager: entrée"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: sortie"""
        self.cleanup()

    def capture_error_screenshot(self) -> Optional[str]:
        """
        Capturer une capture d'écran en cas d'erreur et la convertir en base64

        Returns:
            Screenshot en base64 ou None
        """
        try:
            driver = self.driver_manager.driver
            if driver:
                # Prendre le screenshot
                screenshot_png = driver.get_screenshot_as_png()
                # Convertir en base64
                screenshot_b64 = base64.b64encode(screenshot_png).decode('utf-8')
                self.error_screenshot = screenshot_b64
                self.logger.info("📸 Screenshot capturé avec succès")
                return screenshot_b64
        except Exception as e:
            self.logger.error(f" Erreur lors de la capture screenshot: {e}")
            return None

    def read_popup_message(self) -> Optional[str]:
        """
        Lire le message d'une popup si elle existe (format Sage X3)

        Returns:
            Message de la popup ou None
        """
        try:
            driver = self.driver_manager.driver
            popup_message = None

            # Essayer de trouver une popup avec le message d'erreur (format Sage)
            try:
                from selenium.webdriver.common.by import By
                pre_elements = driver.find_elements(By.CSS_SELECTOR, "pre.s_alertbox_msg")
                if pre_elements and len(pre_elements) > 0:
                    popup_message = pre_elements[0].text
                    self.logger.info(f"📋 Message popup trouvé: {popup_message}")
            except:
                pass

            # Essayer d'autres sélecteurs de popup
            if not popup_message:
                try:
                    from selenium.webdriver.common.by import By
                    alert_elements = driver.find_elements(By.CSS_SELECTOR, "article.s_alertbox_content")
                    if alert_elements and len(alert_elements) > 0:
                        popup_message = alert_elements[0].text
                        self.logger.info(f"📋 Message popup trouvé (alertbox): {popup_message}")
                except:
                    pass

            # Essayer les alertes JavaScript
            if not popup_message:
                try:
                    alert = driver.switch_to.alert
                    popup_message = alert.text
                    self.logger.info(f"📋 Message alert JavaScript trouvé: {popup_message}")
                except:
                    pass

            if popup_message:
                self.popup_messages.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'message': popup_message
                })

            return popup_message

        except Exception as e:
            self.logger.error(f" Erreur lors de la lecture popup: {e}")
            return None

    def handle_error_with_screenshot(self, error_message: str, context: str = "") -> Dict[str, Any]:
        """
        Gérer une erreur en capturant le screenshot et en lisant la popup

        Args:
            error_message: Message d'erreur
            context: Contexte de l'erreur (article, DA, etc.)

        Returns:
            Dictionnaire avec les informations d'erreur
        """
        # Capturer le screenshot
        screenshot = self.capture_error_screenshot()

        # Lire le message popup
        popup_msg = self.read_popup_message()

        error_info = {
            'error_message': error_message,
            'context': context,
            'screenshot': screenshot,
            'popup_message': popup_msg,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        self.logger.error(f"Erreur capturée - Contexte: {context}")
        if popup_msg:
            self.logger.error(f"Message popup: {popup_msg}")

        return error_info
