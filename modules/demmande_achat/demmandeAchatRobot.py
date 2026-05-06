# -*- coding: utf-8 -*-
"""
Module Demmande Achat - Robot pour demmande d'achat dans Sage X3

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

class DemmandeAchatRobot(BaseRobot, WebResultMixin):
    """
    Robot pour la demmande d'achat dans Sage X3
    """
    
    def __init__(self, header: bool = False):
        BaseRobot.__init__(self, "DemmandeAchatRobot")
        WebResultMixin.__init__(self)

        self.excel_handler = ExcelHandler()

        self.url_demmande_achat = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESPSH%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%2749243e27-9e2c-4345-8d2a-177a9f49da00~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~(KEY1~%27x3))"

        try:
            self.logger.info("Initialisation de la connexion a la base de données...")
            self.db = DBHandler()
            self.logger.info(f"Connexion à la base de données ettablie avec succès. {self.db}")
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
            self.db = None  
        
        self.logger.info("Robot DemmandeAchatRobot initialisé avec succès.")
    
    def execute(self, excel_file : str, url: str = None) :
        """
        Exécute le robot de demmande d'achat

        Args:
            excel_file: Chemin vers le fichier Excel d'entrée
            url: URL de la page de demmande d'achat (optionnel, sinon pris dans la config)

        Returns:
            Résultats de l'exécution
        """
        email_f = None
        execution_id = None
        try:
            
            # Charger les données depuis Excel
            self.logger.info(f"📥 Chargement des données depuis Excel: {excel_file}")
            df = self._lire_et_valider_excel(excel_file)

            # regrouper par demandeur
            grouped = df.groupby('Demandeur')
            
            # recuperer email si il existe
            email_f = df.iloc[0]['email_expediteur'] if ('email_expediteur' in df.columns and not df.empty) else None
            
            # Se connecter à la page de demmande d'achat
            self.logger.info("Connexion a Sage X3...")
            self.connect_sage()

            # Démarrer l'exécution en base de données
            if self.db:
                self.logger.info("Demmarage de l'exécution en base de données...")
                exectution_id = self.db.start_execution(
                    module="DemmandeAchat",
                    fichier_excel=excel_file
                )
                self.db.log(exectution_id, 
                            "Info",
                            f"Execution du robot DemmandeAchatRobot avec le fichier {excel_file}",
                            context="execute"
                )
            
            numero_demmande_achat = [] # Liste pour stocker les numéros de demmande d'achat créées

            # Traiter chaque groupe de demandeur
            for demandeur, data in grouped:
                self.logger.info(f"Traitement du demandeur: {demandeur} avec {len(data)} lignes")

                # naviguer vers la page de demmande d'achat
                self.navigate_to_module(self.url_demmande_achat)

                # Enregistrer la demmande d'achat dans la base de données avant de la traiter
                if self.db and exectution_id:
                    da_id = self.db.log_demmande_achat(execution_id=exectution_id,
                                                        demandeur=demandeur,
                                                        observation=data['Observation'].iloc[0] if 'Observation' in data.columns else '')
                                        
                # recuperer le numero de la demmande d'achat créée
                num = None
                
                # traiter la demande
                res = self._traiter_demande(demandeur, data)
                self.logger.info(res)
                if res['status']:
                    num = res['resultat']
                    # num = self._recuperer_numero_demmande_achat()
                    numero_demmande_achat.append(num)
                else:
                    self.logger.info(f"Resulat de {demandeur} : {res['resultat']}")
                
                # Mettre à jour la base de données avec le numéro de la demmande d'achat créée
                if self.db and exectution_id and da_id:

                    self.db.update_demmande_achat(da_id=da_id, 
                                                  statut= "Succès" if num != None else "Échec",
                                                  numero_da=num if num != None else "")
                    
                    self.db.log(execution_id=exectution_id, 
                                level='INFO' if num != None else 'ERROR',
                                message=f"Numéro de la demmande d'achat: {num}",
                                context="execute",
                                entity_type="DemmandeAchat",
                                entity_id=da_id
                    )
                
            self.logger.info(f"Numéros de demmande d'achat créées: {numero_demmande_achat}")        

            # Envoyer les résultats par email
            self.send_results_to_web(email_f)


            # Cloturer la session en DB
            if self.db and execution_id:
                statut_final = 'SUCCES' if len(numero_demmande_achat) == len(grouped) else 'PARTIEL'
                self.db.end_execution(
                    execution_id=execution_id,
                    statut=statut_final,
                    nb_succes=len(numero_demmande_achat),
                    nb_echec=len(grouped)-len(numero_demmande_achat),
                    message='test'
                )

        except Exception as e:
            self.logger.error(f"Erreur lors de l'exécution du robot: {e}")
            # TODO: Mettre à jour la base de données en cas d'erreur critique
        # TODO: Ajouter une section finally pour deconnecter le driver et faire le nettoyage nécessaire
            
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
            'Demandeur',
            'Observation',
            'code_article',
            'quantite'
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
    
    def _traiter_demande(self, demandeur: str, data: pd.DataFrame) -> dict[bool, Union[bool,str]]:
        """
        Traiter les données pour un demandeur donné

        Args:
            demandeur: Nom du demandeur
            data: DataFrame contenant les données du demmande d'achat pour ce demandeur
        Returns:
            status: success | echec 
            resultat: numero de la DA ou message d'error
        """
        self.logger.info(f"Traitement du demandeur: {demandeur}")
        self.logger.info(f"Données:\n{data}")

        # cree nouveulle demmande d'achat
        if not self._creer_demmande_achat():
            self.logger.error("Échec de la création de la demmande d'achat.")
            return {'status': False, "resultat": "error de creation"}

        # saisir les données de l'entête de la demmande d'achat
        res_entete = self._saisir_entete_demmande_achat(data)
        if not res_entete['status']:
            self.logger.error("Échec de la saisie de l'entête de la demmande d'achat.")
            return {'status': False, "resultat": f"error au momant entete{res_entete['resultat']}"}

        # saisir les lignes de la demmande d'achat
        res_ligne = self._saisir_lignes_demmande_achat(data)
        if not res_ligne['status']:
            self.logger.error("Échec de la saisie des lignes de la demmande d'achat.")
            return {'status': False, "resultat": f"error au momant detail {res_ligne['resultat']}"}

        input("Appuyez sur Entrée pour continuer...")
        # enregistrer la demmande d'achat
        # if not self._enregistrer_demmande_achat():
        #     self.logger.error("Échec de l'enregistrement de la demmande d'achat.")
            # return
        # recuperer le numero de la demmande d'achat créée
        numero = self._recuperer_numero_demmande_achat()
        if numero == "N/A":
            self.logger.error("Échec de la récupération du numéro de la demmande d'achat.")
    
    def _saisir_entete_demmande_achat(self, data: pd.DataFrame) -> dict[bool, Union[bool,str]]:
        try:
            driver = self.driver_manager.driver
            self.logger.info("Saisie de l'entête de la demmande d'achat...")
            libelle_input = self.get_input_by_label("Libellé")
            libelle_input.click()
            time.sleep(0.3)
            libelle_input.send_keys(data['Observation'].iloc[0])
            libelle_input.send_keys(Keys.TAB)
            time.sleep(1)
            
            observation_input = self.get_input_by_label("Observation")
            observation_input.click()
            time.sleep(0.3)
            observation_input.send_keys(data['Observation'].iloc[0])
            observation_input.send_keys(Keys.TAB)
            time.sleep(1)
            
            # type_projet_label = driver.find_element(By.XPATH, "//label[text()='Nouveau Projet']") # Trouver le label avec le texte "Normal"
            # type_projet_label.click() # Cliquer sur le label pour sélectionner l'option "Normal"
            # time.sleep(1)

            if self.read_popup_message(): # si il y a un message d'erreur qui s'affiche, alors que il y a une probleme avec la saisie de l'entête
                return {'status' : False, "resultat" : self.popup_messages[-1]}
            
            return {'status' : True, "resultat" : ""}
        except Exception as e:
            self.logger.error(f"Erreur lors de la saisie de l'entête de la demmande d'achat: {e}")
            if self.read_popup_message(): 
                return {'status' : False, "resultat" : self.popup_messages[-1]}
            
            return {'status' : False, "resultat" : "probleme au momant de saisi l'entete"}

    def _saisir_lignes_demmande_achat(self, data: pd.DataFrame) -> dict[bool, Union[bool,str]]:
        
        driver = self.driver_manager.driver
        try:
            
            for index, article in data.iterrows():

                # Récupérer les lignes de la table
                rows_fixed = driver.find_elements(By.CSS_SELECTOR, ".s-page-content-slot .s-grid-slot-table-fixed .s-grid-fixed-table-body tr.s-grid-row")
                
                # Prendre la ligne correspondante à l'index de l'article
                target_row = rows_fixed[index]
                cells_fixed = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
                
                self.logger.info("Remplissage Code Article...")
                cell_article = cells_fixed[0]
                cell_article.click()
                time.sleep(3)
                cell_article.clear()
                cell_article.send_keys(article['code_article'])
                cell_article.send_keys(Keys.TAB)
                time.sleep(0.3)


                rows_scrool = driver.find_elements(By.CSS_SELECTOR, ".s-page-content-slot .s-grid-slot-table-scroll .s-grid-table-body tr.s-grid-row")
                
                target_row = rows_scrool[index]
                cells_scrool = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
                
                # Remplissage Date souhaitée ( date d'Aujourd'hui ) 
                self.logger.info(f"Remplissage Date souhaitée {time.strftime('%d/%m/%Y')}...") 
                cell_date_souhaitee = cells_scrool[2] 
                cell_date_souhaitee.click()
                time.sleep(0.3)
                cell_date_souhaitee.clear()
                cell_date_souhaitee.send_keys(time.strftime('%d/%m/%Y'))
                cell_date_souhaitee.send_keys(Keys.TAB)
                time.sleep(0.3)
                
                # Remplissage Quantité ( effectif )
                self.logger.info(f"Remplissage Quantité {article['quantite']}...")
                cell_quantite = cells_scrool[4]
                cell_quantite.click()
                time.sleep(1)
                cell_quantite.clear()
                cell_quantite.send_keys(str(article['quantite']))
                cell_quantite.send_keys(Keys.TAB)
                time.sleep(0.3)
                
                # Remplissage Demmandeur 
                self.logger.info(f"Remplissage Demandeur {article['Demandeur']}...")
                cell_demmandeur = cells_scrool[7]
                cell_demmandeur.click()
                time.sleep(1)
                cell_demmandeur.clear()
                cell_demmandeur.send_keys(str(article['Demandeur']))
                cell_demmandeur.send_keys(Keys.TAB)
                time.sleep(0.3)

                # Remplissage Affectation 
                self.logger.info(f"Remplissage Affectation Administration...")
                cell_affectation = cells_scrool[8]
                cell_affectation.click()
                time.sleep(1)
                cell_affectation.clear()
                cell_affectation.send_keys(str("ADMINISTRATION"))
                cell_affectation.send_keys(Keys.TAB)
                time.sleep(0.3)
                
                # Remplissage Marque 
                self.logger.info(f"Remplissage Marque PAIE 07/25...")
                cell_marque = cells_scrool[9]
                cell_marque.click()
                time.sleep(1)
                cell_marque.clear()
                cell_marque.send_keys("PAIE 07/25")
                cell_marque.send_keys(Keys.TAB)
                time.sleep(3)
                
                # # Remplissage Compte 
                # self.logger.info(f"Remplissage Compte 61221000...")
                # cell_compte = cells_scrool[15]
                # cell_compte.click()
                # time.sleep(1)
                # cell_compte.clear()
                # cell_compte.send_keys("61221000")
                # cell_compte.send_keys(Keys.TAB)
                # time.sleep(3)
                
                # Remplissage Service 
                self.logger.info(f"Remplissage Service ...") 
                cell_service = cells_scrool[25]
                cell_service.click()
                time.sleep(5)
                cell_service.clear()
                cell_service.send_keys("ADMINS006")
                cell_service.send_keys(Keys.TAB) 
                time.sleep(3)
                # Récupérer les lignes de la table
                rows_fixed = driver.find_elements(By.CSS_SELECTOR, ".s-page-content-slot .s-grid-slot-table-fixed .s-grid-fixed-table-body tr.s-grid-row")
                
                # Prendre la ligne correspondante à l'index de l'article
                target_row = rows_fixed[index]
                cells_fixed = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
                

                # utilise driver pour sleep
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(cells_fixed[0])
                )
            

            return {'status' : True, "resultat" : ""}
        except Exception as e:
            self.logger.error(f"Erreur lors de la saisie des lignes de la demmande d'achat: {e}")
            if self.read_popup_message(): 
                return {'status' : False, "resultat" : self.popup_messages[-1]}
            
            return {'status' : False, "resultat" : "probleme au momant de saisi l'entete"}

    def _creer_demmande_achat(self) -> bool:
        """
        Créer une nouvelle demmande d'achat
        """
        driver = self.driver_manager.driver
        self.logger.info("Création d'une nouvelle demmande d'achat...")
        try:
            wait = WebDriverWait(driver, 2000000)
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a.s_page_action_add")))
            cree = driver.find_element(By.CSS_SELECTOR, "a.s_page_action_add")
            cree.click()
            time.sleep(2)
            self.wait_for_spinner_to_disappear(driver, 90000)

            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la création de la demmande d'achat: {e}")
            return False

    def _recuperer_numero_demmande_achat(self) -> str:
        """
        Récupérer le numéro de la demmande d'achat créée

        Returns:
            Numéro de la demmande d'achat
        """
        self.logger.info("Récupération du numéro de la demmande d'achat...")
        try:
            input_element = self.get_input_by_label("No demande")
            numero = input_element.get_attribute("value")
            self.logger.info(f"Numéro de la demmande d'achat récupéré: {numero}")
            return numero
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération du numéro de la demmande d'achat: {e}")
            return "N/A"

        return "N/A"

    def _enregistrer_demmande_achat(self) -> bool:
        """ Enregistrer la demmande d'achat """
        driver = self.driver_manager.driver
        self.logger.info("Enregistrement de la demmande d'achat...")
        try:
            enregistrer = driver.find_element(By.CSS_SELECTOR, "a.s_page_action_check")
            enregistrer.click()
            time.sleep(2)
            self.wait_for_spinner_to_disappear(driver, 90000)

            if self.read_popup_message(): # si il y a un message d'erreur qui s'affiche, alors que il y a une probleme avec la saisie de l'entête ou des lignes
                return False

            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enregistrement de la demmande d'achat: {e}")
            return False    