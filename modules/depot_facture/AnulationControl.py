# -*- coding: utf-8 -*-
"""
Module anulation_control - Robot principal 
Anulation de Control dans depot de facture
Envoi automatique des résultats vers endpoint web
"""
from typing import Dict, Any, List
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from collections import defaultdict

from core.base_robot import BaseRobot
from core.web_result_mixin import WebResultMixin
from utils.excel_handler import ExcelHandler
from config.settings import SELENIUM_CONFIG
import re
import os
import glob


class AnulationControl(BaseRobot, WebResultMixin):
    """Robot pour l'anulation control d'un DFF """
    
    def __init__(self, headless: bool = False):
        """
        Initialiser le robot Anulation Control
        
        Args:
            headless: Mode sans interface
        """
        # Initialiser BaseRobot
        BaseRobot.__init__(self, 'anulation_control')
        
        # Initialiser WebResultMixin
        WebResultMixin.__init__(self)
        
        self.excel_handler = ExcelHandler()
        self.driver_manager.headless = headless

        # URLs des modules
        self.url_dff = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESXDEPFACT%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%279844eacb-4f96-4301-8b0c-dbe4f4d48e4d~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"
       
        # Compteurs pour validation stricte
        self.dff_traitees = 0
        self.dff_echec = 0


        self.logger.info(f"🤖 Robot Anulation Control Initialisee")

    def execute(self, excel_file: str, url: str = None):

        """
        Exécuter le traitement de anulation Control

        Args:
            excel_file: Chemin du fichier Excel
            url: URL DFF
        """

        email_achteur=""
        try:
            # 1. LIRE ET VALIDER L'EXCEL
            df = self._lire_et_valider_excel(excel_file)
            # email_achteur = df.iloc[0]['email_expediteur']
            print(df)
            # 2. AFFICHER LE RÉSUMÉ
            self._afficher_resume(df)

            # 4. CONNEXION SAGE
            self.connect_sage()

            self.wait_stabilite()

            self.navigate_to_module(url or self.url_dff)

            for index, dff in df.iterrows():
                print(dff)
                print(dff["DFF"])
                self._main_traintement(dff["DFF"])
        except:
            pass


    def _lire_et_valider_excel(self, excel_file: str) -> pd.DataFrame:
        """Lire et valider le fichier Excel"""
        self.logger.info("="*80)
        self.logger.info("📖 LECTURE DU FICHIER EXCEL")
        self.logger.info("="*80)
        
        df = self.excel_handler.read_excel(
            excel_file,
            required_columns=[
                'DFF', 
            ]
        )
        
        self.logger.info(f"{len(df)} lignes lues")
        
        # Vérifier les données vides
        lignes_invalides = []
        for idx, row in df.iterrows():
            colonnes_vides = []
            for col in ['DFF']:
                if pd.isna(row[col]) or str(row[col]).strip() == '':
                    colonnes_vides.append(col)
            
            if colonnes_vides:
                lignes_invalides.append(idx)
                self.logger.warning(f" Ligne {idx+1} ignorée - Colonnes vides: {', '.join(colonnes_vides)}")
        
        if lignes_invalides:
            df = df.drop(df.index[lignes_invalides])
            self.logger.warning(f" {len(lignes_invalides)} ligne(s) invalide(s) ignorée(s)")
        
        self.logger.info(f"{len(df)} lignes valides à traiter")
        return df
    

    def _afficher_resume(self, df: pd.DataFrame):
        """Afficher un résumé de la structure par fournisseur"""
        self.logger.info("="*80)
        self.logger.info(" RÉSUMÉ DU TRAITEMENT")
        self.logger.info("="*80)

        # for x in df:
        #     print(x.get)

    def _main_traintement(self, dff: str) -> dict[str, bool]:
        """
        Traiter un DFF (modifier input Anulation Control)
        
        Returns:
            Dictionnaire avec résultats
        """
        resultat = {
            'type': 'DFF',
            'DFF': dff,
            'statut': 'Echec',
            'message': ''
        }
        
        driver = self.driver_manager.driver

        
        try:
            print(dff)
            
            # 1. Trouver la section "Dépôt Factures" 
            dff_section = driver.find_element(By.XPATH, 
                "//header[.//a[contains(text(), 'Dépôt Factures')]]/following-sibling::div[1]"
            )
            table_head = dff_section.find_element(By.CLASS_NAME, "s-grid-table-head")

            # 2. Directement: trouver le premier input dans le deuxième tr
            filter_row = table_head.find_element(By.XPATH, ".//tr[2]")
            chercher_dff = filter_row.find_element(By.XPATH, ".//td[1]//input")

            # 3. Rechercher l'article
            chercher_dff.click()
            time.sleep(0.5)
            chercher_dff.clear()
            chercher_dff.send_keys(dff)
            chercher_dff.send_keys(Keys.TAB)
            time.sleep(1)
            self.wait_stabilite(timeout=90000)

            table_body = dff_section.find_element(By.CLASS_NAME, "s-grid-table-body")

            # 4. Cliquer sur l'article
            premier_ligne_recherche = table_body.find_element(By.XPATH, ".//tr[1]")
            click_on_dff = premier_ligne_recherche.find_element(By.XPATH, ".//td[1]//div")

            click_on_dff.click()
            time.sleep(1)
            self.wait_stabilite(timeout=90000)

            # verifier numero DFF
            numero_dff = self.get_input_by_label("N°Dossier")
            numero_dff.click()
            time.sleep(0.5)
            value_input_dff = numero_dff.get_attribute("value")
            if value_input_dff != dff : 
                resultat['message'] = 'N Dossier est different a ce que nous cherchons'
                return resultat
            
            time.sleep(1)
            self.wait_stabilite(timeout=90000)

            # verifier est ce que est deja verifier Annulation Control
            annulation_control_input = self.get_input_by_label("Annulation contrôle")
            annulation_control_label = driver.find_element(By.CSS_SELECTOR, f"label[for='{annulation_control_input.get_attribute('id')}']")
            if annulation_control_input.is_selected():
                self.logger.info("Annulation Control déjà cochée")
            else:
                annulation_control_label.click()
                self.logger.info("Annulation Control cochée")


            frs_endosse_input = self.get_input_by_label("Frs Endossé")
            frs_endosse_input_value = frs_endosse_input.get_attribute('value')
            if frs_endosse_input_value == '' or frs_endosse_input_value is None:
                code_frs_input = self.get_input_by_label("Code Frs")
                code_frs_input_value = code_frs_input.get_attribute('value')
                frs_endosse_input.clear()
                self.wait_stabilite()
                frs_endosse_input.send_keys(code_frs_input_value)
                frs_endosse_input.send_keys(Keys.TAB)
                self.wait_stabilite()

            if self.enregistrer_dff():
                resultat["statut"] = "success"
            else:
                resultat["message"] = "Error au mement d'enregister"
        except Exception as e :
            self.logger.error(e)

        
    def enregistrer_dff(self) -> bool:
        """Enregistrer les modifications de l'dff"""
        driver = self.driver_manager.driver
        #input("Appuyez sur Entrée pour enregistrer l'dff (pour debug)")
        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_save")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()

            self.wait_stabilite(timeout=6000)
            
            self.logger.info("💾 Enregistrement article...")
            return True
        except Exception as e:
            self.logger.error(f" Erreur enregistrement article: {e}")

            # Capturer screenshot et popup en cas d'erreur
            self.handle_error_with_screenshot(
                error_message=str(e),
                context="Enregistrement Article"
            )

            driver.save_screenshot("screenShots/error_enregistrement_article.png")
            return False