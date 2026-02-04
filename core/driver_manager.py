# -*- coding: utf-8 -*-
"""
Gestionnaire centralisé de Selenium WebDriver
"""
from pandas import options
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import os
from config.settings import SELENIUM_CONFIG
from core.logger import Logger

class DriverManager:
    """Gestionnaire de WebDriver Selenium"""
    
    def __init__(self, headless: bool = None, profile_path: str = None):
        """
        Initialiser le gestionnaire de driver
        
        Args:
            headless: Mode sans interface graphique
            profile_path: Chemin du profil Chrome
        """
        self.logger = Logger.get_logger('DriverManager', 'core')
        self.driver = None
        self.headless = headless if headless is not None else SELENIUM_CONFIG['headless']
        self.profile_path = profile_path or SELENIUM_CONFIG['profile_path']
        self.page_load_timeout = SELENIUM_CONFIG['page_load_timeout']
    
    def start(self) -> webdriver.Chrome:
        """
        Démarrer le navigateur Chrome

        Returns:
            Instance de WebDriver
        """
        if self.driver:
            self.logger.warning("Driver déjà démarré")
            return self.driver

        try:
            options = self._get_chrome_options()
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_page_load_timeout(self.page_load_timeout)

            # Configurer le téléchargement automatique via CDP (Chrome DevTools Protocol)
            download_dir = os.path.join(SELENIUM_CONFIG['document_genere'], "downloads")
            os.makedirs(download_dir, exist_ok=True)

            # Permettre les téléchargements sans confirmation
            self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": download_dir
            })

            # Désactiver les avertissements de téléchargement dangereux
            self.driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": download_dir,
                "eventsEnabled": True
            })

            self.logger.info(f"✅ Driver Chrome démarré (headless={self.headless})")
            self.logger.info(f"📁 Téléchargements configurés: {download_dir}")
            return self.driver

        except Exception as e:
            self.logger.error(f"❌ Erreur démarrage driver: {e}")
            raise
    
    def _get_chrome_options(self) -> Options:
        """Configurer les options Chrome"""
        options = Options()
        
        # Profil utilisateur
        if self.profile_path:
            os.makedirs(self.profile_path, exist_ok=True)
            options.add_argument(f"user-data-dir={self.profile_path}")
        
        # Mode headless
        if self.headless:
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
        
        # Désactiver les notifications
        options.add_argument("--disable-notifications")
        
        # Désactiver la détection d'automation
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Préférences
        download_dir = os.path.join(SELENIUM_CONFIG['document_genere'], "downloads")
        prefs = {
            "profile.password_manager_enabled": False,
            "credentials_enable_service": False,
            # Téléchargement automatique sans confirmation
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            # Désactiver SafeBrowsing pour les téléchargements
            "safebrowsing.enabled": False,
            "safebrowsing.disable_download_protection": True,
            # Permettre les téléchargements multiples
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.automatic_downloads": 1,
            # PDF: télécharger au lieu d'afficher
            "plugins.always_open_pdf_externally": True,
            "profile.managed_default_content_settings.images": 1,
            "profile.default_content_setting_values.insecure_content": 1, # Autorise le contenu mixte
        }
        options.add_experimental_option("prefs", prefs)

        # Désactiver les avertissements de téléchargement non sécurisé
        options.add_argument("--safebrowsing-disable-download-protection")
        options.add_argument("--disable-features=SafeBrowsing")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--ignore-certificate-errors")
        # Garder le navigateur ouvert
        options.add_experimental_option("detach", True)
        
        return options
    
    def wait_for_element(self, by: By, value: str, timeout: int = 10):
        """
        Attendre qu'un élément soit présent
        
        Args:
            by: Type de sélecteur (By.ID, By.XPATH, etc.)
            value: Valeur du sélecteur
            timeout: Timeout en secondes
        
        Returns:
            WebElement trouvé
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except Exception as e:
            self.logger.error(f"❌ Élément non trouvé: {value}")
            raise
    
    def wait_for_clickable(self, by: By, value: str, timeout: int = 10):
        """
        Attendre qu'un élément soit cliquable
        
        Args:
            by: Type de sélecteur
            value: Valeur du sélecteur
            timeout: Timeout en secondes
        
        Returns:
            WebElement cliquable
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            return element
        except Exception as e:
            self.logger.error(f"❌ Élément non cliquable: {value}")
            raise
    
    def safe_click(self, element, use_js: bool = False):
        """
        Cliquer sur un élément de manière sûre
        
        Args:
            element: WebElement à cliquer
            use_js: Utiliser JavaScript pour le clic
        """
        try:
            if use_js:
                self.driver.execute_script("arguments[0].click();", element)
            else:
                element.click()
        except Exception as e:
            # Fallback sur JavaScript
            self.logger.warning(f"⚠️ Clic normal échoué, tentative JavaScript")
            self.driver.execute_script("arguments[0].click();", element)
    
    def scroll_to_element(self, element):
        """
        Scroller jusqu'à un élément
        
        Args:
            element: WebElement cible
        """
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            element
        )
    
    def refresh_page(self):
        """Actualiser la page"""
        self.driver.refresh()
        self.logger.info("🔄 Page actualisée")
    
    def take_screenshot(self, filename: str):
        """
        Prendre une capture d'écran
        
        Args:
            filename: Nom du fichier
        """
        try:
            filepath = SELENIUM_CONFIG['download_dir'] + f"/{filename}"
            self.driver.save_screenshot(filepath)
            self.logger.info(f"📸 Screenshot: {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f"❌ Erreur screenshot: {e}")
            return None
    
    def stop(self):
        """Arrêter le navigateur"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("✅ Driver Chrome arrêté")
            except Exception as e:
                self.logger.error(f"❌ Erreur arrêt driver: {e}")
            finally:
                self.driver = None
    
    def __enter__(self):
        """Context manager: entrée"""
        return self.start()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: sortie"""
        self.stop()
