0# -*- coding: utf-8 -*-
"""
Gestionnaire centralisé de Selenium WebDriver
Supporte Chrome (par défaut) et Firefox, selon le paramètre `browser`.
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import os
from config.settings import SELENIUM_CONFIG
from core.logger import Logger


class DriverManager:
    """Gestionnaire de WebDriver Selenium (Chrome ou Firefox)"""

    def __init__(self, headless: bool = None, profile_path: str = None, browser: str = None):
        """
        Initialiser le gestionnaire de driver

        Args:
            headless: Mode sans interface graphique
            profile_path: Chemin du profil navigateur
            browser: 'chrome' (défaut) ou 'firefox'
        """
        self.logger = Logger.get_logger('DriverManager', 'core')
        self.driver = None
        self.headless = headless if headless is not None else SELENIUM_CONFIG['headless']
        self.profile_path = profile_path or SELENIUM_CONFIG['profile_path']
        self.page_load_timeout = SELENIUM_CONFIG['page_load_timeout']
        self.browser = (browser or SELENIUM_CONFIG.get('browser', 'chrome')).lower()

    def start(self):
        """
        Démarrer le navigateur (Chrome ou Firefox selon self.browser)

        Returns:
            Instance de WebDriver
        """
        if self.driver:
            self.logger.warning("Driver déjà démarré")
            return self.driver

        try:
            if self.browser == 'firefox':
                self.driver = self._start_firefox()
            else:
                self.driver = self._start_chrome()

            self.driver.set_page_load_timeout(self.page_load_timeout)
            self.driver.maximize_window()

            self.logger.info(f"✅ Driver {self.browser.capitalize()} démarré (headless={self.headless})")
            return self.driver

        except Exception as e:
            self.logger.error(f"❌ Erreur démarrage driver ({self.browser}): {e}")
            raise

    # ------------------------------------------------------------------
    # CHROME
    # ------------------------------------------------------------------
    def _start_chrome(self):
        """Démarrer Chrome (comportement original, inchangé)"""
        options = self._get_chrome_options()
        driver = webdriver.Chrome(options=options)

        # Téléchargement automatique via CDP (spécifique à Chrome)
        download_dir = os.path.join(SELENIUM_CONFIG['document_genere'], "downloads")
        os.makedirs(download_dir, exist_ok=True)

        driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": download_dir
        })
        driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": download_dir,
            "eventsEnabled": True
        })

        self.logger.info(f"📁 Téléchargements configurés: {download_dir}")
        return driver

    def _get_chrome_options(self) -> ChromeOptions:
        """Configurer les options Chrome"""
        options = ChromeOptions()

        # Profil utilisateur
        if self.profile_path:
            os.makedirs(self.profile_path, exist_ok=True)
            options.add_argument(f"user-data-dir={self.profile_path}")

        # Mode headless
        if self.headless:
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

        options.add_argument("--disable-notifications")

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        download_dir = os.path.join(SELENIUM_CONFIG['document_genere'], "downloads")
        prefs = {
            "profile.password_manager_enabled": False,
            "credentials_enable_service": False,
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False,
            "safebrowsing.disable_download_protection": True,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "plugins.always_open_pdf_externally": True,
            "profile.managed_default_content_settings.images": 1,
            "profile.default_content_setting_values.insecure_content": 1,
        }
        options.add_experimental_option("prefs", prefs)

        options.add_argument("--safebrowsing-disable-download-protection")
        options.add_argument("--disable-features=SafeBrowsing")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--ignore-certificate-errors")
        options.add_experimental_option("detach", True)

        return options

    # ------------------------------------------------------------------
    # FIREFOX
    # ------------------------------------------------------------------
    def _start_firefox(self):
        """Démarrer Firefox (équivalent fonctionnel de _start_chrome)"""
        options = self._get_firefox_options()
        driver = webdriver.Firefox(options=options)

        download_dir = os.path.join(SELENIUM_CONFIG['document_genere'], "downloads")
        self.logger.info(f"📁 Téléchargements configurés: {download_dir}")
        return driver

    def _get_firefox_options(self) -> FirefoxOptions:
        """Configurer les options Firefox (équivalent des prefs Chrome ci-dessus)"""
        options = FirefoxOptions()

        if self.headless:
            options.add_argument("--headless")

        # ⚠️ Ne PAS réutiliser self.profile_path ici : c'est un dossier de profil
        # Chrome, incompatible avec Firefox. On laisse geckodriver créer son propre
        # profil temporaire (comportement par défaut, fiable).

        download_dir = os.path.join(SELENIUM_CONFIG['document_genere'], "downloads")
        os.makedirs(download_dir, exist_ok=True)

        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.dir", download_dir)
        options.set_preference("browser.download.useDownloadDir", True)
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference(
            "browser.helperApps.neverAsk.saveToDisk",
            "application/pdf,application/octet-stream,application/vnd.ms-excel,"
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        options.set_preference("pdfjs.disabledForcePDFOpen", True)
        options.set_preference("pdfjs.disabled", True)
        options.set_preference("dom.webnotifications.enabled", False)
        options.set_preference("dom.https_only_mode", False)
        options.accept_insecure_certs = True

        return options


    def wait_for_element(self, by: By, value: str, timeout: int = 10):
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except Exception as e:
            self.logger.error(f" Élément non trouvé: {value}")
            raise

    def wait_for_clickable(self, by: By, value: str, timeout: int = 10):
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            return element
        except Exception as e:
            self.logger.error(f" Élément non cliquable: {value}")
            raise

    def safe_click(self, element, use_js: bool = False):
        try:
            if use_js:
                self.driver.execute_script("arguments[0].click();", element)
            else:
                element.click()
        except Exception:
            self.logger.warning(f"⚠️ Clic normal échoué, tentative JavaScript")
            self.driver.execute_script("arguments[0].click();", element)

    def scroll_to_element(self, element):
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            element
        )

    def refresh_page(self):
        self.driver.refresh()
        self.logger.info("🔄 Page actualisée")

    def take_screenshot(self, filename: str):
        try:
            filepath = SELENIUM_CONFIG['download_dir'] + f"/{filename}"
            self.driver.save_screenshot(filepath)
            self.logger.info(f"📸 Screenshot: {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f" Erreur screenshot: {e}")
            return None

    def stop(self):
        """Arrêter le navigateur (Chrome ou Firefox)"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info(f"✅ Driver {self.browser.capitalize()} arrêté")
            except Exception as e:
                self.logger.error(f" Erreur arrêt driver: {e}")
            finally:
                self.driver = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()