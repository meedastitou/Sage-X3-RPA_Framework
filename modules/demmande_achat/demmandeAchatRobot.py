# -*- coding: utf-8 -*-
"""
Module Demmande Achat - Robot pour demmande d'achat dans Sage X3

"""
from abc import abstractmethod
import json
import os
from typing import Dict, Any, List
import pandas as pd
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
import time
from typing import Union
from core.base_robot import BaseRobot
from core.web_result_mixin import WebResultMixin
from utils.excel_handler import ExcelHandler
from utils.db_handler import DBHandler
from datetime import datetime

from config.settings import DA_CHARGE_FIXE


STATUS_CHARGE_FIXE = "charge_fixe"
class DemmandeAchatRobot(BaseRobot, WebResultMixin):
    """
    Robot pour la demmande d'achat dans Sage X3
    """
    
    def __init__(self, header: bool = False):
        BaseRobot.__init__(self, "DemmandeAchatRobot")
        WebResultMixin.__init__(self)

        self.excel_handler = ExcelHandler()

        self.url_demmande_achat = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESPSH%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%2749243e27-9e2c-4345-8d2a-177a9f49da00~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~(KEY1~%27x3))"

        self.webhook_url  = os.path.join(DA_CHARGE_FIXE['URL_WEBHOOK_CHARGE_FIXE'])
        try:
            self.logger.info("Initialisation de la connexion a la base de données...")
            # self.db = DBHandler()
            self.logger.info(f"Connexion à la base de données ettablie avec succès. {self.db}")
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
            self.db = None  
        
        self.logger.info("Robot DemmandeAchatRobot initialisé avec succès.")
    
    def execute(self, excel_file: str, url: str = None):
        """
        Exécute le robot de demande d'achat
 
        Args:
            excel_file: Chemin vers le fichier Excel d'entrée
            url: URL de la page de demande d'achat (optionnel, sinon pris dans la config)
        """
        email_f = None
        execution_id = None
        numero_demmande_achat = []  # numéros de DA créées
        grouped = None
 
        try:
            # Charger les données depuis Excel
            self.logger.info(f"📥 Chargement des données depuis Excel: {excel_file}")
            df = self._lire_et_valider_excel(excel_file)
 
            # regrouper par demandeur
            grouped = df.groupby('Demandeur')
 
            # récupérer l'email s'il existe
            email_f = df.iloc[0]['email_expediteur'] if ('email_expediteur' in df.columns and not df.empty) else None
 
            # Se connecter à Sage X3
            self.logger.info("Connexion a Sage X3...")
            self.connect_sage()
 
            # Démarrer l'exécution en base de données
            if self.db:
                self.logger.info("Démarrage de l'exécution en base de données...")
                execution_id = self.db.start_execution(
                    module="DemmandeAchat",
                    fichier_excel=excel_file
                )
                self.db.log(
                    execution_id,
                    "Info",
                    f"Execution du robot DemmandeAchatRobot avec le fichier {excel_file}",
                    context="execute"
                )
 
            # Traiter chaque groupe de demandeur
            for demandeur, data in grouped:
                self.logger.info(f"Traitement du demandeur: {demandeur} avec {len(data)} lignes")
 
                # naviguer vers la page de demande d'achat
                self.navigate_to_module(self.url_demmande_achat)
 
                # Enregistrer la DA en base avant de la traiter
                da_id = None
                if self.db and execution_id:
                    da_id = self.db.log_demmande_achat(
                        execution_id=execution_id,
                        demandeur=demandeur,
                        observation=data['Observation'].iloc[0] if 'Observation' in data.columns else ''
                    )
 
                # status éventuel (colonne optionnelle)
                status_da = self._extraire_status(data)
                id_da = self._extraire_id_da(data)
 
                # traiter la demande
                num = None
                res = self._traiter_demande(demandeur, data)
                self.logger.info(res)
 
                if res['status']:
                    num = res['resultat']
                    numero_demmande_achat.append(num)
 
                    # ✅ NOUVEAU : envoi du numéro DA si status == charge_fixe
                    if status_da == STATUS_CHARGE_FIXE:
                        res_hook = self._envoyer_numero_da(
                            numero_da=num,
                            demandeur=demandeur,
                            data=data,
                            status=status_da,
                            id_da=id_da,
                            execution_id=execution_id,
                        )
                        if self.db and execution_id:
                            self.db.log(
                                execution_id=execution_id,
                                level='INFO' if res_hook['status'] else 'ERROR',
                                message=(f"Webhook charge_fixe DA {num}: "
                                         f"{'envoyé' if res_hook['status'] else res_hook['resultat']}"),
                                context="webhook_charge_fixe",
                                entity_type="DemmandeAchat",
                                entity_id=da_id
                            )
                else:
                    self.logger.info(f"Résultat de {demandeur} : {res['resultat']}")
 
                # Mise à jour de la base avec le numéro de DA
                if self.db and execution_id and da_id:
                    self.db.update_demmande_achat(
                        da_id=da_id,
                        statut="Succès" if num is not None else "Échec",
                        numero_da=num if num is not None else ""
                    )
                    self.db.log(
                        execution_id=execution_id,
                        level='INFO' if num is not None else 'ERROR',
                        message=f"Numéro de la demande d'achat: {num}",
                        context="execute",
                        entity_type="DemmandeAchat",
                        entity_id=da_id
                    )
 
            self.logger.info(f"Numéros de demande d'achat créées: {numero_demmande_achat}")
 
            # Envoyer les résultats
            self.send_results_to_web(email_f)
 
            # Clôturer la session en DB
            if self.db and execution_id:
                nb_succes = len(numero_demmande_achat)
                nb_total = len(grouped)
                self.db.end_execution(
                    execution_id=execution_id,
                    statut='SUCCES' if nb_succes == nb_total else 'PARTIEL',
                    nb_succes=nb_succes,
                    nb_echec=nb_total - nb_succes,
                    message=f"{nb_succes}/{nb_total} DA créées"
                )
 
        except Exception as e:
            self.logger.error(f"Erreur lors de l'exécution du robot: {e}", exc_info=True)
            # Clôture en erreur (vérifiez que 'ERREUR' est accepté par votre colonne statut)
            if self.db and execution_id:
                try:
                    self.db.end_execution(
                        execution_id=execution_id,
                        statut='ERREUR',
                        nb_succes=len(numero_demmande_achat),
                        nb_echec=(len(grouped) - len(numero_demmande_achat)) if grouped is not None else 0,
                        message=str(e)[:500]
                    )
                except Exception as db_err:
                    self.logger.error(f"Impossible de clôturer l'exécution en base: {db_err}")
        finally:
            # laisser Sage X3 finir l'enregistrement (overlay s_lock_long) avant de se déconnecter
            self._attendre_fin_chargement(timeout=30)
            self.logger.info("Deconnexion du robot...")
            try:
                self.disconnect_sage()
            except Exception as e:
                self.logger.error(f"Erreur lors de la déconnexion: {e}")
 
    # ------------------------------------------------------------------
    # Lecture / validation Excel
    # ------------------------------------------------------------------
    @staticmethod
    def _normaliser_colonne_status(df: pd.DataFrame) -> pd.DataFrame:
        """
        Colonne `status` optionnelle :
        - absente  -> créée vide
        - présente -> nom normalisé en 'status' (insensible à la casse) et valeurs
                      normalisées ('Charge Fixe', 'CHARGE-FIXE' -> 'charge_fixe')
        """
        col_status = next((c for c in df.columns if str(c).strip().lower() == 'status'), None)
 
        if col_status is None:
            df['status'] = ''
            return df
 
        if col_status != 'status':
            df = df.rename(columns={col_status: 'status'})
 
        df['status'] = (
            df['status']
            .fillna('')
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(r'[\s\-]+', '_', regex=True)
        )
        return df

    @staticmethod
    def _normaliser_colonne_id_da(df: pd.DataFrame) -> pd.DataFrame:
        """
        Colonne `id_da` optionnelle :
        - absente  -> créée vide
        - présente -> nom normalisé en 'id_da', valeurs nettoyées (NaN -> '')
        """
        col = next((c for c in df.columns if str(c).strip().lower() == 'id_da'), None)

        if col is None:
            df['id_da'] = ''
            return df

        if col != 'id_da':
            df = df.rename(columns={col: 'id_da'})

        df['id_da'] = df['id_da'].fillna('').astype(str).str.strip()
        return df
            
    def _lire_et_valider_excel(self, excel_file: str) -> pd.DataFrame:
        """
        Lire et valider les données du fichier Excel
 
        Args:
            excel_file: Chemin du fichier Excel
        """
        self.logger.info("=" * 80)
        self.logger.info(f"📥 Lecture du fichier Excel: {excel_file}")
        self.logger.info("=" * 80)
 
        # `status` n'est volontairement PAS dans les colonnes requises (optionnelle)
        colonnes_requises = [
            'Demandeur',
            'Observation',
            'code_article',
            'quantite'
        ]
 
        df = self.excel_handler.read_excel(excel_file, required_columns=colonnes_requises)
        self.logger.info(f"{len(df)} lignes lues depuis Excel.")
 
        # ✅ NOUVEAU : gérer la colonne status (présente ou non)
        df = self._normaliser_colonne_status(df)
        df = self._normaliser_colonne_id_da(df) 
        lignes_invalides = []
        for idx, row in df.iterrows():
            colonnes_vides = [
                col for col in colonnes_requises
                if pd.isna(row[col]) or str(row[col]).strip() == ''
            ]
            if colonnes_vides:
                lignes_invalides.append(idx)
                self.logger.warning(f"⚠️ Ligne {idx} invalide (vides: {colonnes_vides}): {row.to_dict()}")
 
        if lignes_invalides:
            df = df.drop(index=lignes_invalides)  # idx = labels, pas positions
            self.logger.info(f"{len(lignes_invalides)} lignes supprimées en raison de données invalides.")
 
        self.logger.info(f"📊 {len(df)} lignes valides après validation:\n{df}")
        return df

    def _extraire_status(self, data: pd.DataFrame) -> str:
        """Retourne le status (normalisé) d'un groupe de demandeur, '' si absent."""
        if 'status' not in data.columns:
            return ''
        valeurs = [v for v in data['status'].unique() if v]
        if len(valeurs) > 1:
            self.logger.warning(
                f"Plusieurs status pour un même demandeur: {valeurs} -> "
                f"utilisation de '{valeurs[0]}'"
            )
        return valeurs[0] if valeurs else ''
    
    def _extraire_id_da(self, data: pd.DataFrame) -> str:
        """Retourne l'id_da d'un groupe de demandeur, '' si absent."""
        if 'id_da' not in data.columns:
            return ''
        valeurs = [v for v in data['id_da'].unique() if v]
        if len(valeurs) > 1:
            self.logger.warning(
                f"Plusieurs id_da pour un même demandeur: {valeurs} -> "
                f"utilisation de '{valeurs[0]}'"
            )
        return valeurs[0] if valeurs else ''


    # ------------------------------------------------------------------
    # Traitement d'une DA
    # ------------------------------------------------------------------
    def _traiter_demande(self, demandeur: str, data: pd.DataFrame) -> dict:
        """
        Traiter les données pour un demandeur donné
 
        Returns:
            {'status': True,  'resultat': numero_da}
            {'status': False, 'resultat': message_erreur}
        """
        self.logger.info(f"Traitement du demandeur: {demandeur}")
        self.logger.info(f"Données:\n{data}")
 
        # créer une nouvelle DA
        if not self._creer_demmande_achat():
            self.logger.error("Échec de la création de la demande d'achat.")
            return {'status': False, 'resultat': "erreur de création"}
 
        # entête
        res_entete = self._saisir_entete_demmande_achat(data)
        if not res_entete['status']:
            self.logger.error("Échec de la saisie de l'entête de la demande d'achat.")
            return {'status': False, 'resultat': f"erreur au moment de l'entête: {res_entete['resultat']}"}
 
        # lignes
        res_ligne = self._saisir_lignes_demmande_achat(data)
        if not res_ligne['status']:
            self.logger.error("Échec de la saisie des lignes de la demande d'achat.")
            return {'status': False, 'resultat': f"erreur au moment du détail: {res_ligne['resultat']}"}
 
        time.sleep(10)
 
        # enregistrer la DA
        if not self._enregistrer_demmande_achat():
            self.logger.error("Échec de l'enregistrement de la demande d'achat.")
            return {'status': False, 'resultat': "erreur d'enregistrement"}
 
        # récupérer le numéro de la DA créée (retourne "N/A" en cas d'échec)
        numero = self._recuperer_numero_demmande_achat()
        if not numero or numero == "N/A":
            self.logger.error("Échec de la récupération du numéro de la demande d'achat.")
            return {'status': False, 'resultat': "numéro de DA introuvable"}
 
        return {'status': True, 'resultat': numero}

    # ------------------------------------------------------------------
    # Webhook
    # ------------------------------------------------------------------
    def _envoyer_numero_da(self, numero_da: str, demandeur: str, data: pd.DataFrame,
                           status: str,id_da: str = '', execution_id=None) -> dict:
        """
        Envoie le numéro de DA au webhook/API (cas status == 'charge_fixe').
        Un échec du webhook ne fait pas échouer la DA (déjà créée dans Sage X3).
 
        Returns:
            {'status': bool, 'resultat': code HTTP ou message d'erreur}
        """
        if not getattr(self, 'webhook_url', None):
            self.logger.error("Webhook charge_fixe: URL non configurée (webhook_url).")
            return {'status': False, 'resultat': "URL webhook non configurée"}
 
        colonnes_lignes = [c for c in ('code_article', 'quantite', 'marque') if c in data.columns]
        payload = {
            "id_da": id_da,
            "numero_da": numero_da,
            "demandeur": demandeur,
            "status": status,
            "observation": data['Observation'].iloc[0] if 'Observation' in data.columns else '',
            "email_expediteur": (data['email_expediteur'].iloc[0]
                                 if 'email_expediteur' in data.columns else None),
            "execution_id": execution_id,
            # to_json gère NaN -> null et les types numpy
            "lignes": json.loads(data[colonnes_lignes].to_json(orient='records', force_ascii=False)),
        }
 
        headers = {"Content-Type": "application/json"}
        token = getattr(self, 'webhook_token', None)
        if token:
            headers["Authorization"] = f"Bearer {token}"
 
        derniere_erreur = ""
        for tentative in range(1, 4):
            try:
                r = requests.post(self.webhook_url, json=payload, headers=headers, timeout=30)
                if r.ok:
                    self.logger.info(f"Webhook charge_fixe OK pour DA {numero_da} (id_da={id_da}, HTTP {r.status_code})")
                    return {'status': True, 'resultat': r.status_code}
                derniere_erreur = f"HTTP {r.status_code}: {r.text[:200]}"
                if 400 <= r.status_code < 500:  # erreur client : inutile de réessayer
                    break
            except requests.RequestException as e:
                derniere_erreur = str(e)
 
            self.logger.warning(f"Webhook charge_fixe tentative {tentative}/3 échouée: {derniere_erreur}")
            time.sleep(2 * tentative)
 
        self.logger.error(f"Webhook charge_fixe KO pour DA {numero_da}: {derniere_erreur}")
        return {'status': False, 'resultat': derniere_erreur}


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
                print(article)
                time.sleep(1)
                self.handle_popup("OK", "Zone obligatoire")

                # Récupérer les lignes de la table
                rows_fixed = driver.find_elements(By.CSS_SELECTOR, ".s-page-content-slot .s-grid-slot-table-fixed .s-grid-fixed-table-body tr.s-grid-row")
                
                # Prendre la ligne correspondante à l'index de l'article
                target_row = rows_fixed[index]
                cells_fixed = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
                
                self.logger.info("Remplissage Code Article...")
                cell_article = cells_fixed[0]
                cell_article.click()
            
                time.sleep(5)
                cell_article.clear()
                cell_article.send_keys(article['code_article'])
                cell_article.send_keys(Keys.TAB)
                time.sleep(3)


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
                self.logger.info(f"Remplissage Marque {article['marque']}...")
                cell_marque = cells_scrool[9]
                cell_marque.click()
                time.sleep(1)
                cell_marque.clear()
                cell_marque.send_keys(str(article.get('marque')))
                cell_marque.send_keys(Keys.TAB)
                time.sleep(3)
                
                grid_body = self.driver_manager.driver.find_element(By.CSS_SELECTOR, "div.s-grid-slot-table-scroll")
                # write grid_body to file
                with open("grid_body.html", "w", encoding="utf-8") as f:
                    f.write(grid_body.get_attribute("outerHTML"))

                # self.scroll_horizontal(grid_body, 500)


                # Remplissage Compte 
                # self.logger.info(f"Remplissage Compte 61221000...")
                # cell_compte = cells_scrool[16]
                # cell_compte.click()
                # time.sleep(3)
                # Remplissage Service 
                
                if article['code_article'] == "A14884":
                    input("hhhh")
                    target_row.find_element(By.XPATH, "./td[16]/div/a").click()
                    element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/article/div[3]/div[2]/div/div/div[2]/ul/li[3]/a"))
                    )
                    time.sleep(2) 
                    element.click()
                    target_row.find_element(By.XPATH, "./td[16]/div/input").send_keys(Keys.TAB)
                    self.wait_stabilite()  
                    element_oui = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="s_app_over"]/div/div/article/div[2]/a[1]'))
                    )
                    element_oui.click()
                    self.wait_stabilite()
                i=1

                while i==1:
                    self.logger.info(f"Remplissage Service ...") 
                    cell_service = cells_scrool[25]
                    cell_service.click()
                    time.sleep(2)
                    cell_service.clear()
                    cell_service.send_keys("ADMINS006")
                    time.sleep(2)
                    if cell_service.get_attribute("value") == "ADMINS006":
                        self.logger.info(f"Service rempli avec succès.{ cell_service.get_attribute('value') } ")
                        cell_service.send_keys(Keys.TAB) 
                        time.sleep(3)
                        i=0
                driver.find_element(By.XPATH, "/html/body/div[1]/article/div[1]/div/article/div[2]/div[2]/div/div/div[3]/section/div/div/div/section/div/div/div[1]/section/div/div/div/section/div/div/div/div/article/div[2]/div[1]/div/div[2]/div[2]/table/tr/td[50]/div/input").send_keys(Keys.TAB)
                time.sleep(3)
                # Récupérer les lignes de la table
                rows_fixed = driver.find_elements(By.CSS_SELECTOR, ".s-page-content-slot .s-grid-slot-table-fixed .s-grid-fixed-table-body tr.s-grid-row")
                # WebDriverWait(driver, 20).until(
                #     EC.text_to_be_present_in_element_value(cells_scrool[25], "ADMINS006") # Attendre que le spinner de chargement disparaisse
                # )
                # Prendre la ligne correspondante à l'index de l'article
                target_row = rows_fixed[(index+1)]
                cells_fixed = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
                cell_article = cells_fixed[0]
                cell_article.click()
                time.sleep(5)
                cell_article.clear()
                cell_article.send_keys(Keys.ESCAPE)
                WebDriverWait(driver, 20).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.s_overlay")) # Attendre que le spinner de chargement disparaisse
                )
                # utilise driver pour sleep
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(cells_fixed[0])
                )
                self.handle_popup("OK", "Zone obligatoire")

            
            
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

    def _recuperer_numero_demmande_achat(self, timeout: int = 60) -> str:
        """
        Récupérer le numéro de la demande d'achat créée.
        Le champ "No demande" est rempli par Sage X3 après l'enregistrement :
        on le relit jusqu'à ce qu'il soit non vide.
    
        Returns:
            Numéro de la DA, ou "N/A" si toujours vide après `timeout` secondes.
        """
        self.logger.info("Récupération du numéro de la demmande d'achat...")
        fin = time.time() + timeout
        derniere_erreur = None
    
        while time.time() < fin:
            try:
                input_element = self.get_input_by_label("No demande")
                numero = (input_element.get_attribute("value") or "").strip()
                if numero:
                    self.logger.info(f"Numéro de la demmande d'achat récupéré: {numero}")
                    return numero
            except Exception as e:
                derniere_erreur = e  # élément pas encore rendu / stale : on réessaie
            time.sleep(1)
    
        self.logger.error(
            f"Numéro de DA toujours vide après {timeout}s (dernière erreur: {derniere_erreur})"
        )
        return "N/A"


    
    def scroll_horizontal(self, element, pixels: int = 100):
        """
        Scroll horizontalement un élément
        
        Args:
            element: WebElement à scroller
            pixels: Nombre de pixels à scroller (positif = droite, négatif = gauche)
        """
        self.driver_manager.driver.execute_script(
            f"arguments[0].scrollLeft += {pixels};", 
            element
        )

    def _attendre_fin_chargement(self, timeout: int = 60) -> bool:
        """
        Attend qu'aucun overlay Sage X3 (div.s_overlay, ex: s_lock_long pendant un
        enregistrement) ne soit visible.
    
        Returns:
            True si l'écran est libre, False si le délai est dépassé.
        """
        try:
            driver = self.driver_manager.driver
    
            def _ecran_libre(d):
                return not any(
                    o.is_displayed()
                    for o in d.find_elements(By.CSS_SELECTOR, "div.s_overlay")
                )
    
            WebDriverWait(
                driver, timeout, poll_frequency=0.5,
                ignored_exceptions=[StaleElementReferenceException]
            ).until(_ecran_libre)
            return True
        except TimeoutException:
            self.logger.warning(f"⚠️ Overlay Sage X3 toujours visible après {timeout}s")
            return False
        except Exception as e:
            self.logger.warning(f"⚠️ Attente de fin de chargement impossible: {e}")
            return False


    def _enregistrer_demmande_achat(self) -> bool:
        """ Enregistrer la demande d'achat et attendre la fin réelle du traitement """
        driver = self.driver_manager.driver
        self.logger.info("Enregistrement de la demmande d'achat...")
        try:
            enregistrer = driver.find_element(By.CSS_SELECTOR, "a.s_page_action_check")
            enregistrer.click()
            time.sleep(2)
            self.wait_for_spinner_to_disappear(driver, 90000)
    
            # ✅ Sage X3 garde un overlay (s_lock_long) tant que l'enregistrement
            # n'est pas terminé : sans cette attente le numéro est lu trop tôt (vide)
            # et la déconnexion échoue (click intercepted).
            self._attendre_fin_chargement(timeout=90)
    
            # message d'erreur éventuel (contrôle bloquant, zone obligatoire, ...)
            if self.read_popup_message():
                return False
    
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enregistrement de la demmande d'achat: {e}")
            return False
  