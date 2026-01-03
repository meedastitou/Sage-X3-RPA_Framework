# -*- coding: utf-8 -*-
"""
Module BonneCommand - Robot principal
Intégration complète du code de bonne de command dans le framework
"""
from typing import Dict, Any
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

from core.base_robot import BaseRobot
from utils.excel_handler import ExcelHandler


class BonneCommandeRobot(BaseRobot):
    """Robot pour le facturation automatique des fournisseurs"""
    
    def __init__(self, headless: bool = False):
        """
        Initialiser le robot facturation
        
        Args:
            headless: Mode sans interface
        """
        super().__init__('facturation')
        self.excel_handler = ExcelHandler()
        
        self.logger.info(f"🤖 Robot Lettrage initialisé")
    
    def execute(self, excel_file: str, url: str):
        """
        Exécuter le lettrage
        
        Args:
            excel_file: Chemin du fichier Excel
            url: URL du module Sage X3
        """
        # Lire Excel
        df = self.excel_handler.read_excel(
            excel_file,
            required_columns=['Numero_DA', 
                              'Acheteur', 
                              'Code_Fournisseur',
                              'Email_Fournisseur',
                              'TEL_Fournisseu', 
                              'Code_Article', 
                              'Montant']
        )
        
        self.logger.info(f"📊 {len(df)} lignes à traiter")
        
        # Connexion Sage
        self.connect_sage()
        
        url_article = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESITM%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%278ecdb3d1-8ca7-40ca-af08-76cb58c70740~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"
        url_demmande_achat = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESPSH%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%278ecdb3d1-8ca7-40ca-af08-76cb58c70740~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"
        # Traiter chaque ligne
        self.navigate_to_module(url_article) # Naviguer vers le module article
        for idx, row in df.iterrows():

            self.logger.info(f"\n{'='*80}")
            self.logger.info(f"📌 LIGNE {idx+1}/{len(df)}")
            self.logger.info(f"{'='*80}")
            Numero_DA = str(row['Numero_DA'])
            Acheteur = str(row['Acheteur'])
            Code_Fournisseur = str(row['Code_Fournisseur'])
            Email_Fournisseur = str(row['Email_Fournisseur'])
            TEL_Fournisseu= str(row['TEL_Fournisseu'])
            Code_Article = str(row['Code_Article'])
            Montant = str(row['Montant'])
            
            self.logger.info(f"\n{'='*80}")
            self.logger.info(f"📌 LIGNE {idx+1}/{len(df)}")
            self.logger.info(f"{'='*80}")
            self.logger.info(f"🔍 Traiter: DA={Numero_DA}, Acheteur={Acheteur}, Fournisseur={Code_Fournisseur}, Article={Code_Article}, Montant={Montant}")
            time.sleep(1)
            resultat = self.traiter_articles(Code_Article, Code_Fournisseur, Montant)
        

        self.navigate_to_module(url_demmande_achat) # Naviguer vers le module demande achat
        for idx, row in df.iterrows():

            self.logger.info(f"\n{'='*80}")
            self.logger.info(f"📌 LIGNE {idx+1}/{len(df)}")
            self.logger.info(f"{'='*80}")
            Numero_DA = str(row['Numero_DA'])
            Acheteur = str(row['Acheteur'])
            Code_Fournisseur = str(row['Code_Fournisseur'])
            Email_Fournisseur = str(row['Email_Fournisseur'])
            TEL_Fournisseu= str(row['TEL_Fournisseu'])
            Code_Article = str(row['Code_Article'])
            Montant = str(row['Montant'])
            
            self.logger.info(f"\n{'='*80}")
            self.logger.info(f"📌 LIGNE {idx+1}/{len(df)}")
            self.logger.info(f"{'='*80}")
            self.logger.info(f"🔍 Traiter: DA={Numero_DA}, Acheteur={Acheteur}, Fournisseur={Code_Fournisseur}, Article={Code_Article}, Montant={Montant}")
            time.sleep(1)
            resultat = self.traiter_demmande_achat(Numero_DA)
           
    def enregistrer_article(self):
        driver = self.driver_manager.driver

        try:
            save_btn = driver.find_element(By.CLASS_NAME, "s_page_action_i.s_page_action_i_save")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()
            self.logger.info("✅ Enregistrement clique")
            confirmation_msg = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "s_alertbox_title"))
            )
            confirmation_msg_text = confirmation_msg.text

            if "Avertissement" in confirmation_msg_text or "Mibilisation" in confirmation_msg_text:
                self.logger.error(f"❌ Erreur enregistrement: {confirmation_msg_text}")
                raise Exception(confirmation_msg_text)  
            
            self.logger.info(f"✅ Enregistrement reussi: {confirmation_msg.text}")
            time.sleep(3)
        except Exception as e:
            self.logger.error(f"❌ Erreur enregistrement: {e}")
            driver.save_screenshot("ScreenShot/error_enregistrement.png")

    def traiter_articles(self, Code_Article, Code_Fournisseur, Montant):

        
        resultat = {
            'Code_Fournisseur': Code_Fournisseur,
            'Code_Article': Code_Article,
            'Montant': Montant,
            'statut': 'Echec',
            'ecritures_trouvees': 0,
            'facturation_effectue': False,
            'message': ''
        }
        
        driver = self.driver_manager.driver

        try:
            chercher_article = driver.find_element(By.ID, "2-565-input") # Article

            chercher_article.click()
            time.sleep(0.5)
            chercher_article.clear()
            chercher_article.send_keys(Code_Article)
            chercher_article.send_keys(Keys.TAB)
            time.sleep(1)

            click_onArticle = driver.find_element(By.CSS_SELECTOR, f"div.s-inplace-value-read") # Click on article
            click_onArticle.click()
            time.sleep(1)

            changer_fournisseur = driver.find_element(By.ID, "4-179-input") # Fournisseur
            changer_fournisseur.click()
            time.sleep(0.5)
            changer_fournisseur.clear()
            changer_fournisseur.send_keys(Code_Fournisseur)
            changer_fournisseur.send_keys(Keys.TAB)
            # check if the fournisseur is changed
            time.sleep(1)
            fournisseur_value = changer_fournisseur.get_attribute('value')  
            if fournisseur_value != Code_Fournisseur:
                resultat['message'] = f'Fournisseur non trouvé ou non modifiable (attendu: {Code_Fournisseur}, trouvé: {fournisseur_value})'
                self.logger.error(f"❌ Fournisseur non trouvé ou non modifiable (attendu: {Code_Fournisseur}, trouvé: {fournisseur_value})")
                return resultat

            change_tarif = driver.find_element(By.ID, "4-181-input") # Montant
            change_tarif.click()
            time.sleep(0.5)
            change_tarif.clear()
            change_tarif.send_keys(Montant)
            change_tarif.send_keys(Keys.TAB)
            # check if the tarif is changed
            time.sleep(1)
            tarif_value = change_tarif.get_attribute('value')  
            if tarif_value != Montant:
                resultat['message'] = f'Tarif non trouvé ou non modifiable (attendu: {Montant}, trouvé: {tarif_value})'
                self.logger.error(f"❌ Tarif non trouvé ou non modifiable (attendu: {Montant}, trouvé: {tarif_value})")
                return resultat
            

            self.enregistrer_article()
        except Exception as e:
            resultat['message'] = f'Erreur recherche article: {str(e)}'
            self.logger.error(f"❌ Erreur recherche article: {e}")
            return resultat
        
        return resultat
    
    def enregistrer_demmande_achat(self):
        driver = self.driver_manager.driver

        try:
            save_btn = driver.find_element(By.CLASS_NAME, "s_page_action_i.s_page_action_i_save")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()
            self.logger.info("✅ Enregistrement clique")
            confirmation_msg = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "s_alertbox_title"))
            )
            confirmation_msg_text = confirmation_msg.text

            if "Avertissement" in confirmation_msg_text or "Mibilisation" in confirmation_msg_text:
                self.logger.error(f"❌ Erreur enregistrement: {confirmation_msg_text}")
                raise Exception(confirmation_msg_text)  
            
            self.logger.info(f"✅ Enregistrement reussi: {confirmation_msg.text}")
            time.sleep(3)
        except Exception as e:
            self.logger.error(f"❌ Erreur enregistrement: {e}")
            driver.save_screenshot("ScreenShot/error_enregistrement.png")

    def traiter_demmande_achat(self, Numero_DA):
        resultat = {
            'Numero_DA': Numero_DA,
            'statut': 'Echec',
            'ecritures_trouvees': 0,
            'facturation_effectue': False,
            'message': ''
        }
        
        driver = self.driver_manager.driver

        try:
            chercher_DA = driver.find_element(By.ID, "5-109-input") # numéro DA

            chercher_DA.click()
            time.sleep(0.5)
            chercher_DA.clear()
            chercher_DA.send_keys(Numero_DA)
            chercher_DA.send_keys(Keys.TAB)
            time.sleep(1)

            click_onDA = driver.find_element(By.CSS_SELECTOR, f"div.s-inplace-value-read") # Click on DA
            click_onDA.click()
            time.sleep(1)

            validation_acheteur = driver.find_element(By.ID, "5-80-input") # validation Acheteur
            validation_acheteur.click()
            time.sleep(1)

            

            self.enregistrer_demmande_achat()
        except Exception as e:
            resultat['message'] = f'Erreur recherche article: {str(e)}'
            self.logger.error(f"❌ Erreur recherche article: {e}")
            return resultat
        
        return resultat
    
