# -*- coding: utf-8 -*-
"""
Module Articles - Robot pour changer le tarif d'un article dans Sage X3

"""
from abc import abstractmethod
from typing import Dict, Any, List
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from typing import Union
from core.base_robot import BaseRobot
from core.web_result_mixin import WebResultMixin
from utils.excel_handler import ExcelHandler
from utils.db_handler import DBHandler
from datetime import datetime

class ChangeTarifRobot(BaseRobot, WebResultMixin):
    """
    Robot pour changer le tarif d'un article dans Sage X3
    """
    
    def __init__(self, header: bool = False):
        BaseRobot.__init__(self, "ChangeTarifRobot")
        WebResultMixin.__init__(self)

        self.excel_handler = ExcelHandler()

        self.url_article = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESITM%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%279844eacb-4f96-4301-8b0c-dbe4f4d48e4d~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"

        try:
            self.logger.info("Initialisation de la connexion a la base de données...")
            # self.db = DBHandler()
            self.logger.info(f"Connexion à la base de données ettablie avec succès. {self.db}")
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
            self.db = None  
        
        self.logger.info("Robot ChangeTarifRobot initialisé avec succès.")


    def execute(self, excel_file : str, url: str = None) :
        """
        Exécute le robot de changement de tarif d'article dans Sage X3.

        Args:
            excel_file: Chemin vers le fichier Excel d'entrée

        Returns:
            Résultats de l'exécution
        """
        email_f = None
        execution_id = None
        try:
            # 1 - Charger les donnees depuis le fichier Excel
            self.logger.info(f"Chargement des données depuis le fichier Excel: {excel_file}")
            data = self._lire_et_valider_excel(excel_file)


            # 2 - Se connecter à Sage x3
            self.logger.info("Connexion a Sage X3...")
            self.connect_sage()
            

            # 3 - naviguer vers la page de l'article
            self.logger.info("Navigation vers la page de l'article...")
            self.navigate_to_module(self.url_article)


            # 4 - appeler la fonction de traitement des articles
            self.logger.info("Traitement des articles...")
            if self._traiter_articles(data):
                self.logger.info("Traitement des articles terminé avec succès.")

        except :
            pass


    def _lire_et_valider_excel(self, excel_file: str) -> pd.DataFrame:
        """
        Lire et valider les données du fichier Excel

        Args:
            excel_file: Chemin du fichier Excel
        """
        """Lire et valider le fichier Excel"""
        self.logger.info("="*80)
        self.logger.info(f"📥 Lecture du fichier Excel: {excel_file}")
        self.logger.info("="*80)

        colonnes_requises = [
            'code_article',
            'tarif_achat',
        ]

        df = self.excel_handler.read_excel(excel_file,required_columns=colonnes_requises)
        self.logger.info(f"{len(df)} lignes lues depuis Excel.")

        lignes_invalides = []
        for idx, row in df.iterrows():
            colonnes_vides = []
            for col in colonnes_requises:
                if pd.isna(row[col]) or str(row[col]).strip() == '':
                    colonnes_vides.append(col)
            if colonnes_vides:
                lignes_invalides.append(idx)
                self.logger.warning(f"⚠️ Ligne {idx} invalide: {row.to_dict()}")
        if lignes_invalides:
            df = df.drop(df.index[lignes_invalides])
            self.logger.info(f"{len(lignes_invalides)} lignes supprimées en raison de données invalides.")
        
        self.logger.info(f"📊 {len(df)} lignes valides après validation:\n{df}")
        return df
    

    def _traiter_articles(self, data: pd.DataFrame) -> bool:
        """
        Traiter les articles pour changer leur tarif

        Args:
            data: DataFrame contenant les données des articles
        """
      
        driver = self.driver_manager.driver
        for idx, row in data.iterrows():

            try:
                code_article = row['code_article']
                tarif_achat = row['tarif_achat']
                self.logger.info(f"Traitement de l'article {code_article} avec le tarif {tarif_achat}...")

                self.wait_stabilite()

                result = self._traiter_article(code_article, tarif_achat)

                if result['statut'] == 'Echec':
                    self.logger.error(f"Erreur lors du traitement de l'article {code_article}: {result['message']}")
                    return False

            except Exception as e:
                self.logger.error(f"Erreur lors du traitement de l'article {code_article}: {e}")
                return False

        return True

    def _traiter_article(self, code_article: str, tarif_achat: Union[float, int]) -> dict:
        """
        Traiter un article pour changer son tarif

        Args:
            code_article: Code de l'article
            tarif_achat: Nouveau tarif d'achat
        """
        driver = self.driver_manager.driver
        resultat = {
                    'type': 'Article',
                    'code_article': code_article,
                    'statut': 'Echec',
                    'message': ''
                }
        
        try:
            # 1 - chercher l'article dans Sage X3
            self.logger.info(f"Recherche de l'article {code_article} dans Sage X3...")  
            webdriver_wait = WebDriverWait(driver, 90).until(
                EC.presence_of_element_located((By.XPATH, "//header[.//a[contains(text(), 'Articles')]]/following-sibling::div[1]"))
            )
            
            # 1.1 Trouver la section "Articles" 
            articles_section = driver.find_element(By.XPATH, 
                "//header[.//a[contains(text(), 'Articles')]]/following-sibling::div[1]"
            )
            webdriver_wait = WebDriverWait(driver, 90).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "s-grid-table-head"))
                        )
            table_head = articles_section.find_element(By.CLASS_NAME, "s-grid-table-head")

            # 1.2 Directement: trouver le premier input dans le deuxième tr
            filter_row = table_head.find_element(By.XPATH, ".//tr[2]")
            chercher_article = filter_row.find_element(By.XPATH, ".//td[1]//input")

            # 1.3 Rechercher l'article
            chercher_article.click()
            time.sleep(0.5)
            chercher_article.clear()
            chercher_article.send_keys(code_article)
            chercher_article.send_keys(Keys.TAB)
            time.sleep(1)
            self.wait_stabilite(timeout=90000)

            table_body = articles_section.find_element(By.CLASS_NAME, "s-grid-table-body")

            # 1.4 Cliquer sur l'article
            try:
                premier_ligne_recherche = table_body.find_element(By.XPATH, ".//tr[1]")
                click_on_article = premier_ligne_recherche.find_element(By.XPATH, ".//td[1]//div")
            except:
                resultat['message'] = f"l\'article {code_article} n\'est pas existe"
                return resultat

            click_on_article.click()
            time.sleep(1)
            self.wait_stabilite(timeout=90000)

            # 2 - clique sur detail tarif
            self.logger.info(f"Accès aux détails du tarif de l'article {code_article}...")
            # 2.1 clique sur le lien "Tarifs achat"
            tarif_achat_link = driver.find_element(By.XPATH, "//div[@class='s_page_header_component']//a[@title='Tarifs achat']")
            tarif_achat_link.click()
            self.wait_stabilite()
            # 2.2 clique sur detail du tarif
            self.get_input_by_label("Article").send_keys(Keys.TAB)  # Fermer le clavier virtuel si ouvert
            self.wait_stabilite()
            detail_tarif_link = WebDriverWait(driver, 90).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='s_page_header_component']//a[@title='Détail tarif']"))
            )
            # detail_tarif_link = driver.find_element(By.XPATH, "//div[@class='s_page_header_component']//a[@title='Détail tarif']")
            detail_tarif_link.click()
            self.wait_stabilite()
            # 2.3 clique sur saisie tarifs
            saisie_tarif_link = WebDriverWait(driver, 90).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='s_page_header_component']//a[@title='Saisie tarifs']"))
            )
            saisie_tarif_link.click()
            self.wait_stabilite()
            # 3 - changer le tarif
            self.logger.info(f"Changement du tarif de l'article {code_article} à {tarif_achat}...")
            # 3.1. Trouver la section avec le titre "Prix produit"
            section_prix = driver.find_element(By.XPATH,
            "//div[@class='s-h2-titles-h2-title-text' and text()='Prix produit']/ancestor::section[@class='s-h2']"
            )

            # 3.2. Dans cette section, trouver le tableau scrollable
            table_scroll = section_prix.find_element(By.CSS_SELECTOR, "table.s-grid-table-body")

            # 3.3. Récupérer toutes les lignes du tableau
            prix_input = table_scroll.find_element(By.XPATH, ".//tr[1]/td[8]/div/input")
            prix_input.click()
            time.sleep(0.5)
            prix_input.clear()
            prix_input.send_keys(str(tarif_achat))
            prix_input.send_keys(Keys.TAB)
            self.wait_stabilite()            

            # 4 - sauvegarder les modifications
            self.logger.info(f"Sauvegarde des modifications pour l'article {code_article}...")
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_save")
            save_btn.click()
            self.wait_stabilite()

            # 5 - retour à la liste des articles
            self.logger.info(f"Retour à la liste des articles après traitement de l'article {code_article}...")
            try:
                for i in range(3):  # Essayer de cliquer jusqu'à 3 fois
                    retour_btn = WebDriverWait(driver, 90).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.s_page_close"))
                    )
                    retour_btn.click()
                    self.wait_stabilite()
            except:
                self.logger.warning("Le bouton de retour n'est pas cliquable, tentative de navigation alternative...")
                # Si le bouton n'est pas cliquable, essayer d'utiliser la navigation du navigateur
                self.navigate_to_module(self.url_article)
                self.wait_stabilite()


            resultat['statut'] = 'Succès'
            resultat['message'] = f"Le tarif de l'article {code_article} a été changé avec succès à {tarif_achat}."
            return resultat
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement de l'article {code_article}: {e}")
            resultat['message'] = str(e)
            return resultat