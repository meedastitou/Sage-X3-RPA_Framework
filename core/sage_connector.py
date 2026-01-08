# -*- coding: utf-8 -*-
"""
Connecteur réutilisable pour Sage X3
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from config.settings import SAGE_CONFIG, SAGE_CONFIG_TEST
from core.driver_manager import DriverManager
from core.logger import Logger
from selenium.webdriver.common.keys import Keys

class SageConnector:
    """Gestion de la connexion à Sage X3"""
    
    def __init__(self, driver_manager: DriverManager = None):
        """
        Initialiser le connecteur
        
        Args:
            driver_manager: Instance de DriverManager (optionnel)
        """
        self.logger = Logger.get_logger('SageConnector', 'core')
        self.driver_manager = driver_manager or DriverManager()
        self.driver = None
        self.is_connected = False
    
    def connect(self) -> bool:
        """
        Se connecter à Sage X3
        
        Returns:
            True si connexion réussie
        """
        try:
            # Démarrer le driver si pas déjà fait
            if not self.driver:
                self.driver = self.driver_manager.start()
            
            # Naviguer vers Sage X3
            self.logger.info(f"🔗 Connexion à: {SAGE_CONFIG['url']}")
            self.driver.get(SAGE_CONFIG['url'])
            time.sleep(2)
            
            # Remplir le formulaire de connexion
            username_field = self.driver.find_element(By.NAME, "login")
            password_field = self.driver.find_element(By.NAME, "password")
            
            username_field.send_keys(SAGE_CONFIG['username'])
            password_field.send_keys(SAGE_CONFIG['password'])
            
            # Cliquer sur le bouton de connexion
            login_button = self.driver.find_element(By.ID, "go-basic")
            login_button.click()
            time.sleep(3)
            
            # Gérer la popup éventuelle
            try:
                ok_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[text()='OK']"))
                )
                ok_button.click()
                self.logger.info("✅ Popup fermée")
            except:
                pass
            
            time.sleep(2)
            self.is_connected = True
            self.logger.info("✅ Connexion Sage X3 réussie")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur connexion Sage X3: {e}")
            self.is_connected = False
            return False
    
    def navigate_to_module(self, url: str, wait_time: int = 10) -> bool:
        """
        Naviguer vers un module Sage X3
        
        Args:
            url: URL du module
            wait_time: Temps d'attente après navigation
        
        Returns:
            True si navigation réussie
        """
        try:
            self.logger.info(f"🔗 Navigation vers le module")
            self.driver.get(url)
            time.sleep(wait_time)
            
            # Attendre que la page soit chargée
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            
            self.logger.info("✅ Module chargé")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur navigation module: {e}")
            return False
    
    def handle_refresh_popup(self) -> bool:
        """
        Gérer la popup 'Actualiser le site Web ?'
        
        Returns:
            True si popup gérée
        """
        try:
            actualiser_btn = WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Actualiser')]"))
            )
            actualiser_btn.click()
            self.logger.info("✅ Popup 'Actualiser' cliquée")
            time.sleep(2)
            return True
        except:
            return False
    
    def refresh_with_popup_handling(self, max_attempts: int = 3) -> bool:
        """
        Actualiser la page en gérant la popup
        
        Args:
            max_attempts: Nombre max de tentatives
        
        Returns:
            True si actualisation réussie
        """
        for attempt in range(1, max_attempts + 1):
            try:
                self.logger.info(f"🔄 Actualisation (tentative {attempt}/{max_attempts})")
                
                self.driver.refresh()
                time.sleep(2)
                
                # Gérer la popup
                self.handle_refresh_popup()
                
                # Attendre le chargement
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                )
                
                self.logger.info(f"✅ Actualisation réussie (tentative {attempt})")
                return True
                
            except Exception as e:
                self.logger.warning(f"⚠️ Échec tentative {attempt}: {e}")
                if attempt < max_attempts:
                    time.sleep(3)
                else:
                    self.logger.error(f"❌ Échec après {max_attempts} tentatives")
                    return False
        
        return False
    
    def disconnect(self):
        """Se déconnecter et fermer le navigateur"""
        driver = self.driver_manager.driver

        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.5)
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(1)
        logout_button = driver.find_element(By.XPATH, f"//a[contains(text(), '{SAGE_CONFIG['titular']}')]")
        logout_button.click()
        time.sleep(1)
        logout_button = driver.find_element(By.XPATH, "//a[contains(text(), 'Déconnexion')]")
        logout_button.click()
        time.sleep(2)

        self.click_oui_if_popup(driver)        

        if self.driver_manager:
            self.driver_manager.stop()
        self.is_connected = False
        self.logger.info("✅ Déconnexion Sage X3")
    
    def click_oui_if_popup(self,driver, timeout=3):
        """Clique sur Oui si un popup avec bouton Oui apparaît"""
        try:
            # Vérifier d'abord si le popup est présent
            popup = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, "s_alertbox_footer"))
            )
            
            # Chercher le bouton Oui dans le popup
            oui_button = popup.find_element(By.XPATH, ".//a[@aria-label='Oui']")
            oui_button.click()
            
        except:
            # Si le popup n'est pas trouvé, ne rien faire
            pass


    def __enter__(self):
        """Context manager: entrée"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: sortie"""
        self.disconnect()
