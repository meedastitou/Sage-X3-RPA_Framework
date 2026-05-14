# -*- coding: utf-8 -*-
"""
Module Imputation - Robot pour imputer les règlements avec les factures Sage X3

"""
from typing import Dict, Any, List
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

from core.base_robot import BaseRobot
from core.web_result_mixin import WebResultMixin
from utils.excel_handler import ExcelHandler
from utils.db_handler import DBHandler
from datetime import datetime

class ImputationRobot(BaseRobot, WebResultMixin):
    """
    Robot pour imputer les règlements avec les factures Sage X3
    """

    def __init__(self, headless: bool = False):
        BaseRobot.__init__(self, 'imputation')
        WebResultMixin.__init__(self)

        self.excel_handler = ExcelHandler()

        self.url_imputation = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FPREPROD%2F%24sessions%3Ff%3DIPTACPTFOU%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%2754edbf16-8938-46d0-bd92-a4f5e0d8f4f1~ep~%2764a56978-56ab-46f1-8d83-ed18f7fa6484~appConn~())"
        
        try:
            self.logger.info("Initialisation de la connexion a la base de donnees...")
            self.db = DBHandler()
            self.logger.info(f"Connexion a la base de donnees etablie {self.db}")

        except Exception as e:
            self.logger.warning(f"DB non disponible (mode sans base de donnees): {e}")
            self.db = None

        self.logger.info("Robot Imputation initialise")

    # ------------------------------------------------------------------
    # Point d'entree principal
    # ------------------------------------------------------------------
    def execute(self, excel_file: str, url: str = None):
        """
        Executer ImputationRobot pour imputer les reglements avec les factures Sage X3

        Args:
            excel_file: Chemin du fichier Excel
            url: URL du module Sage X3 (optionnel, remplace l'URL par defaut)
        """
        driver = self.driver_manager.driver
        email_f = ""
        execution_id = None

        try:

            # Charger les données Excel
            self.logger.info("📂 Chargement du fichier Excel...")
            df = self._lire_et_valider_excel(excel_file)
            # recuperer email si il existe
            email_f = df.iloc[0]['email_expediteur'] if ('email_expediteur' in df.columns and not df.empty) else None

            # Se connecter à Sage X3
            self.logger.info("🔐 Connexion à Sage X3...")
            self.connect_sage()
            
            for idx, row in df.iterrows():
                code_frs = row['CodeFrs']
                n_bc = row['N_BC']
                reglement = row['Reglement']
                facture = row['Facture']
                
                # Naviguer vers le module de Imputation
                self.logger.info("Navigation vers le module de Imputation...")
                self.navigate_to_module(self.url_imputation)


                self.logger.info(f"Traitement de la ligne {idx+1}: CodeFrs={code_frs}, N_BC={n_bc}, Reglement={reglement}, Facture={facture}")
                if self._traiter_ligne_imputation(code_frs, n_bc, reglement, facture):
                    self.logger.info(f"Ligne {idx+1} : {code_frs}, {reglement}, {facture} traitée avec succès")
                    self.add_result({reglement + " , " + facture : True})
                    
                else:
                    self.logger.error(f" Erreur lors du traitement de la ligne {idx+1} : {code_frs}, {reglement}, {facture}")
                    self.add_result({reglement + " , " + facture : False})
 
            self.logger.info(self.resultats) 
            for res in self.resultats:
                for clef, valeur in res.items():
                    # Il faut parser la chaîne pour extraire reglement et facture
                    self.logger.info(clef)
                    self.logger.info(valeur)
                
            self.send_results_to_web(email_f)

        except Exception as e:
            self.logger.info({e})
            pass
        finally:
            self.logger.info("🔒 Fermeture de la session Sage X3...")
            self.disconnect_sage()
            self.logger.info("Robot Imputation terminé.")
    
    def _lire_et_valider_excel(self, excel_file: str) -> pd.DataFrame:
        """
        Lire et valider les données du fichier Excel

        Args:
            excel_file: Chemin du fichier Excel
        """
        """Lire et valider le fichier Excel"""
        self.logger.info("="*80)
        self.logger.info("📖 LECTURE EXCEL")
        self.logger.info("="*80)
        
        colonnes_requises = [
            'CodeFrs',
            'N_BC',
            'Reglement',
            'Facture'
        ]
        
        df = self.excel_handler.read_excel(excel_file, required_columns=colonnes_requises)
        
        self.logger.info(f"{len(df)} ligne(s) lues")
        
        # Validation des colonnes importantes
        lignes_invalides = []
        for idx, row in df.iterrows():
            colonnes_vides = []
            for col in ['CodeFrs', 'N_BC', 'Reglement', 'Facture']:
                if pd.isna(row[col]) or str(row[col]).strip() == '':
                    colonnes_vides.append(col)

            if colonnes_vides:
                lignes_invalides.append(idx)
                self.logger.warning(f" Ligne {idx+1} ignorée - Colonnes vides: {', '.join(colonnes_vides)}")
        
        if lignes_invalides:
            df = df.drop(df.index[lignes_invalides])
            self.logger.warning(f" {len(lignes_invalides)} ligne(s) invalide(s) ignorée(s)")
        
        self.logger.info(f"{len(df)} ligne(s) valides à traiter")
        return df
    
    def _traiter_ligne_imputation(self, code_frs: str, n_bc: str, reglement: str, facture: str):
        """
        Traiter une ligne d'imputation

        Args:
            code_frs: Code du fournisseur
            n_bc: Numéro de la commande d'achat
            reglement: Référence du règlement
            facture: Référence de la facture
        """
        self.logger.info(f"Traitement de l'imputation pour CodeFrs={code_frs}, N_BC={n_bc}, Reglement={reglement}, Facture={facture}")
        try:
            # Saisi code fournisseur
            self.logger.info(f"Saisie du code fournisseur: {code_frs}")
            fournisseur_input = self.get_input_by_label("Tiers Payeur")
            fournisseur_input.click()
            time.sleep(0.5)
            fournisseur_input.clear()
            fournisseur_input.send_keys(code_frs)
            fournisseur_input.send_keys(Keys.TAB)
            time.sleep(1)

            # sleep jusqu'à ce que presece de ce element "s-field-input-ref-desc" 
            WebDriverWait(self.driver_manager.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "s-field-input-ref-desc"))
            )
            
            #<a href="#" title="Recherche" class="s-mn-list-btn s-mn-link s-fonticon-btn s-btn-search"></a>
            # fait la recherche de Reglement / clique sur le bouton de recherche
            self.logger.info(f"Recherche du règlement: {reglement}")
            #clique sur le bouton de recherche
            search_btn = self.driver_manager.driver.find_element(By.CSS_SELECTOR, "a.s-mn-list-btn.s-mn-link.s-fonticon-btn.s-btn-search")
            search_btn.click()
            # voici input de recherche qui apparait : <input type="text" autocomplete="off" spellcheck="false" autocorrect="off" class="s-inplace-input s-array-search-field" id="2-58-input">
            input_search = WebDriverWait(self.driver_manager.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input.s-inplace-input.s-array-search-field"))
            )
            time.sleep(1)
            input_search.clear()
            input_search.send_keys(reglement)
            input_search.send_keys(Keys.ENTER)
            time.sleep(1)

            # selectionne le reglement trouvé
            WebDriverWait(self.driver_manager.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-grid-cell-value-edit.s-inplace-value-edit.s-readonly.s-x3mode-command.s-focus"))
            )
            reglement_row = self.driver_manager.driver.find_element(By.CSS_SELECTOR, "div.s-grid-cell-value-edit.s-inplace-value-edit.s-readonly.s-x3mode-command.s-focus")
            
            # Get parent element 'tr' of the selected reglement
            parent_tr = reglement_row.find_element(By.XPATH, "./ancestor::tr")

            # Get first input in the same row (tr) as the selected reglement
            element_a = parent_tr.find_element(By.CSS_SELECTOR, "div.s-grid-cell-value-edit.s-inplace-value-edit a")
            element_a.click()
            time.sleep(0.5)
            facture_element = self.driver_manager.driver.find_element(By.XPATH, '//*[@id="s_app_over"]/div[2]/div/div/div[2]/ul/li[2]/a')
            facture_element.click()
            time.sleep(0.5)

            type_input = parent_tr.find_element(By.XPATH, ".//td[2]/div/input")
            type_input.click()
            type_input.clear()
            type_input.send_keys("FAFOU")
            type_input.send_keys(Keys.TAB)
            time.sleep(0.5)

            code_facture_input = parent_tr.find_element(By.XPATH, ".//td[3]/div/input")
            code_facture_input.click()
            code_facture_input.clear()
            code_facture_input.send_keys(facture)
            code_facture_input.send_keys(Keys.TAB)
            time.sleep(0.5)

            # verifie si la facture est existe ou non

            montant_inpute_input = parent_tr.find_element(By.XPATH, ".//td[6]/div/input")
            montant_inpute_input.send_keys(Keys.TAB)
            time.sleep(0.5)

            # Verifier si un popup est apparu (le montant de la facture est inferieur au montant du reglement) 
            message_pop = self.read_popup_message()

            if message_pop and "Sur-règlement" in message_pop:
                # recupere le montant du facture ( apartir du message du popup)

                self.handle_popup("OK","Sur-règlement")

                montant_facture = self.extract_amount_from_message(message_pop)
                if montant_facture:
                    self.logger.info(f"Montant de la facture extrait du message: {montant_facture}")
                    montant_inpute_input.clear()
                    montant_inpute_input.send_keys(montant_facture)
                    montant_inpute_input.send_keys(Keys.TAB)
                    time.sleep(0.5)
                else:
                    self.logger.error("Impossible d'extraire le montant de la facture du message du popup.")

            # si y a un autre popup retourne fasle et arrete le traitement de cette ligne
            if self.read_popup_message():
                return False

            # enregistre l'imputation
            self.clique_enregistrer()

            # confirmation d'enregistrement
            self.confirmation_enregistrement()

            self.close_module(confirm_abandon=False)
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement de la ligne d'imputation: {e}")
            self.close_module(confirm_abandon=True)
            return False
        
    def extract_amount_from_message(self, message):
        """
        Extraire le montant du message du popup

        Args:
            message: Message du popup
        """
        # Exemple de message : "Sur-règlement non autorisé 300.50"
        import re
        match = re.search(r"Sur-règlement non autorisé ([\d.]+)", message)
        if match:
            montant_str = match.group(1).replace(".", ",")
            try:
                return montant_str
            except ValueError:
                self.logger.error(f"Erreur lors de la conversion du montant: {montant_str}")
                return None
        else:
            self.logger.error(f"Impossible d'extraire le montant du message: {message}")
            return None
        
    def clique_enregistrer(self):
        driver = self.driver_manager.driver

        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_save")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()
            time.sleep(5)
            self.wait_for_spinner_to_disappear(driver, 900000000)
        except Exception as e:
            self.logger.error(f"Erreur enregistrement: {e}")

    def confirmation_enregistrement(self):
        driver = self.driver_manager.driver

        try:
            # Version 1 : Attendre que le bouton soit cliquable directement
            ok_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "article.s_modal_page a.s-mn-main-link[title='OK']"))
            )
            ok_btn.click()
            time.sleep(1)
        except Exception as e:
            self.logger.error(f"Erreur confirmation enregistrement: {e}")