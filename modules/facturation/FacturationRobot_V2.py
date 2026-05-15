# -*- coding: utf-8 -*-
"""
Module Facturation V2 - Robot principal
Groupement par FactureFournisseur avec sélection de tous les codes réception associés
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


class FacturationRobotV2(BaseRobot, WebResultMixin):
    """
    Robot Facturation V2
    Logique : groupe les lignes Excel par FactureFrs.
    Pour chaque groupe → une seule facture avec TOUS les codes réception (BR) du groupe.
    Les colonnes Code, DFF, Date sont prises depuis la première ligne du groupe.
    """

    def __init__(self, headless: bool = False):
        BaseRobot.__init__(self, 'facturation')
        WebResultMixin.__init__(self)

        self.excel_handler = ExcelHandler()

        self.url_facturation = (
            "http://192.168.1.241:8124/syracuse-main/html/main.html"
            "?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESPIH%252F2%252F%252FM%252F"
            "%26profile%3D~(loc~%27fr-FR~role~%278ecdb3d1-8ca7-40ca-af08-76cb58c70740"
            "~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"
        )

        self.factures_traitees = 0
        self.factures_echec = 0

        try:
            self.logger.info("Initialisation de la connexion a la base de donnees...")
            self.db = DBHandler()
            self.logger.info(f"Connexion a la base de donnees etablie {self.db}")

        except Exception as e:
            self.logger.warning(f"DB non disponible (mode sans base de donnees): {e}")
            self.db = None

        self.logger.info("Robot Facturation V2 initialise")

    # ------------------------------------------------------------------
    # Point d'entree principal
    # ------------------------------------------------------------------

    def execute(self, excel_file: str, url: str = None):
        """
        Executer la facturation V2 (groupement par FactureFrs)

        Args:
            excel_file: Chemin du fichier Excel
            url: URL du module Sage X3 (optionnel, remplace l'URL par defaut)
        """
        driver = self.driver_manager.driver
        email_f = ""
        execution_id = None

        try:
            df = self.excel_handler.read_excel(
                excel_file,
                required_columns=['Code', 'DFF', 'FactureFrs', 'Date', 'BR']
            )

            if 'email_expediteur' in df.columns:
                email_f = df.iloc[0]['email_expediteur']

            self.logger.info(f"{len(df)} lignes lues depuis l'Excel")

            # Normaliser FactureFrs avant groupement (supprimer espaces, normaliser casse)
            df['FactureFrs'] = df['FactureFrs'].astype(str).str.strip()

            # --- Groupement par FactureFrs ---
            groupes = df.groupby('FactureFrs', sort=False)
            self.logger.info(f"{groupes.ngroups} facture(s) fournisseur distincte(s) trouvee(s)")

            self.connect_sage()

            # Demarrer la session en base de donnees
            if self.db:
                self.logger.info("Demarrage de l'execution en base de donnees...")
                execution_id = self.db.start_execution('facturation', excel_file)
                self.db.log(execution_id, 'INFO',
                            f"{groupes.ngroups} facture(s) a traiter depuis {excel_file}",
                            context='execute')

            for facture_frs, groupe in groupes:
                self.navigate_to_module(url or self.url_facturation)
                time.sleep(1)
                self.wait_for_spinner_to_disappear(driver, 600000)

                self.logger.info(f"\n{'='*80}")
                self.logger.info(f"FACTURE FOURNISSEUR : {facture_frs}")
                self.logger.info(f"{'='*80}")

                # Colonnes fixes : prendre la premiere ligne du groupe
                first_row = groupe.iloc[0]
                code = str(first_row['Code'])
                dff = str(first_row['DFF'])
                facture_frs_str = str(facture_frs)
                nom = str(first_row.get('Nom', ''))
                type_f = str(first_row['TypeF']).strip() if 'TypeF' in first_row and str(first_row.get('TypeF', '')).strip() != '' else 'FAF'

                try:
                    if pd.api.types.is_numeric_dtype(type(first_row['Date'])):
                        date_obj = pd.Timestamp('1899-12-30') + pd.Timedelta(days=float(first_row['Date']))
                    else:
                        date_obj = pd.to_datetime(first_row['Date'], dayfirst=True)
                    date = date_obj.strftime('%d/%m/%Y')
                except Exception as e:
                    self.logger.error(f"Erreur conversion date: {e}")
                    date = ""

                # Liste de tous les codes reception du groupe
                list_br = [str(r['BR']) for _, r in groupe.iterrows()]
                self.logger.info(f"Codes reception a selectionner : {list_br}")

                # Enregistrer la facture en DB avant traitement
                facture_id = None
                if self.db and execution_id:
                    facture_id = self.db.log_facture(
                        execution_id=execution_id,
                        facture_frs=facture_frs_str,
                        code_fournisseur=code,
                        codes_reception=list_br,
                        nom_fournisseur=nom,
                        dff=dff,
                        date_facture=date,
                    )

                resultat = self.traiter_fournisseur(
                    url=url,
                    codeFournisseur=code,
                    factureFournisseur=facture_frs_str,
                    DFF=dff,
                    Date=date,
                    list_codeReception=list_br,
                    nom=nom,
                    typeF=type_f
                )

                # Mettre a jour le resultat en DB apres traitement
                if self.db and execution_id and facture_id:
                    statut_db = 'SUCCES' if resultat.get('statut') == 'Succes' else 'ECHEC'
                    self.db.update_facture(
                        facture_id=facture_id,
                        statut=statut_db,
                        message=resultat.get('message', ''),
                        numero_piece=resultat.get('numero_piece'),
                        screenshot_path=resultat.get('error_info', {}).get('screenshot') if resultat.get('error_info') else None,
                    )
                    self.db.log(execution_id, 'INFO' if statut_db == 'SUCCES' else 'ERROR',
                                f"Facture {facture_frs_str} : {resultat.get('message', '')}",
                                context='execute',
                                entity_type='facturation',
                                entity_id=facture_id)

                if resultat.get('statut') == 'Succes':
                    self.factures_traitees += 1
                else:
                    self.factures_echec += 1
                    error_info = self.handle_error_with_screenshot(
                        error_message=resultat.get('message', 'Erreur inconnue'),
                        context=f"Fournisseur {code} - Facture {facture_frs_str}"
                    )
                    resultat['error_info'] = error_info

                self.add_result(resultat)
                self.save_report(incremental=True)

                time.sleep(2)

            # Bilan final
            self.add_result({
                'type': 'BILAN_FINAL',
                'statut': 'SUCCES' if self.factures_echec == 0 else 'PARTIEL',
                'factures_traitees': self.factures_traitees,
                'factures_echec': self.factures_echec,
                'message': f'{self.factures_traitees} facture(s) traitee(s), {self.factures_echec} echec(s)'
            })

            self.save_report()
            self.send_results_to_web(email_f)

            # Cloturer la session en DB
            if self.db and execution_id:
                statut_final = 'SUCCES' if self.factures_echec == 0 else 'PARTIEL'
                self.db.end_execution(
                    execution_id=execution_id,
                    statut=statut_final,
                    nb_succes=self.factures_traitees,
                    nb_echec=self.factures_echec,
                    message=f'{self.factures_traitees} traitee(s), {self.factures_echec} echec(s)'
                )

            self.logger.info("="*80)
            self.logger.info("PROCESSUS TERMINE")
            self.logger.info(f"{self.factures_traitees} facture(s) traitee(s)")
            self.logger.info(f"{self.factures_echec} facture(s) en echec")
            self.logger.info("="*80)

        except Exception as e:
            self.logger.error(f"ERREUR CRITIQUE: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

            if self.db and execution_id:
                self.db.end_execution(
                    execution_id=execution_id,
                    statut='ECHEC',
                    nb_succes=self.factures_traitees,
                    nb_echec=self.factures_echec,
                    message=str(e)
                )

            self.add_result({
                'type': 'ERREUR',
                'statut': 'ECHEC',
                'message': str(e)
            })

            self.save_report()
            self.send_results_to_web(email_f)

        finally:
            try:
                s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
                s_page_close.click()
                time.sleep(2)
            except Exception:
                pass
            finally:
                self.wait_for_spinner_to_disappear(driver, 600000)
                self.disconnect_sage()
                if self.db:
                    self.db.close()

    # ------------------------------------------------------------------
    # Selection de PLUSIEURS receptions
    # ------------------------------------------------------------------

    def selection_multiple_receptions(self, list_codeReception: List[str],
                                       typeF: str = "FAF") -> Dict[str, bool]:
        """
        Ouvre la section "Selection receptions" (FAF) ou "Selection retours" (AVR),
        puis coche la checkbox de chaque code de la liste.

        Args:
            list_codeReception: Liste des codes a selectionner
            typeF: 'AVR' → Sélection retours, sinon → Sélection réceptions

        Returns:
            dict {code: True/False} indiquant le succes pour chaque code
        """
        driver = self.driver_manager.driver
        resultats = {br: False for br in list_codeReception}

        if typeF == 'AVR':
            btn_title = "Sélection retours"
        else:
            btn_title = "Sélection réceptions"

        try:
            # 1. Ouvrir la section (une seule fois)
            reception_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//a[@title='{btn_title}']"))
            )
            reception_btn.click()
            self.logger.info(f"Section '{btn_title}' ouverte")
            time.sleep(1)

            # 2. Attendre le tableau
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "s-grid-table-body"))
            )
            
            # 3. Pour chaque code de reception, chercher et cocher
            for codeReception in list_codeReception:
                self.wait_stabilite()
                self._set_in_first_page()
                self._get_page_of_receiption(codeReception=codeReception)
                self.logger.info(f"Recherche de la reception: {codeReception}")
                succes = self._cocher_reception(driver, codeReception)
                resultats[codeReception] = succes
                if succes:
                    self.logger.info(f"Reception {codeReception} selectionnee")
                else:
                    self.logger.error(f"Echec selection reception {codeReception}")

        except Exception as e:
            self.logger.error(f"Erreur lors de l'ouverture de la section receptions: {e}")
            import traceback
            traceback.print_exc()

        return resultats

    def _cocher_reception(self, driver, codeReception: str) -> bool:
        """
        Trouve une ligne de reception par son code et coche sa checkbox.
        La section "Selection receptions" doit deja etre ouverte.

        Returns:
            True si succes, False sinon
        """
        try:
            all_rows = driver.find_elements(
                By.CSS_SELECTOR,
                ".s-grid-table-body tr.s-grid-row.s-grid-navig-row"
            )
            self.logger.info(f"{len(all_rows)} lignes dans le tableau")

            target_row = None
            for row in all_rows:
                try:
                    desc_div = row.find_element(By.CSS_SELECTOR, ".s-tree-node-desc-value")
                    text = desc_div.text.strip()
                    if text.startswith(codeReception):
                        target_row = row
                        self.logger.info(f"Ligne trouvee: {text}")
                        break
                except Exception:
                    continue

            if not target_row:
                self.logger.error(f"Reception {codeReception} non trouvee dans la liste")
                return False

            # Gerer les lignes cachees (expansion arbre)
            style = target_row.get_attribute("style") or ""
            is_hidden = "display: none" in style or "display:none" in style
            if is_hidden:
                self.logger.warning(f"Reception {codeReception} cachee, tentative d'expansion...")
                try:
                    parent_rows = driver.find_elements(
                        By.CSS_SELECTOR,
                        ".s-grid-table-body tr.s-grid-row.s-grid-navig-row"
                    )
                    for i, pr in enumerate(parent_rows):
                        if i + 1 < len(parent_rows) and parent_rows[i + 1] == target_row:
                            picker = pr.find_element(By.CSS_SELECTOR, ".s-tree-node-picker")
                            if picker.is_displayed():
                                picker.click()
                                self.logger.info("Ligne expandee")
                                time.sleep(0.5)
                                break
                except Exception as e:
                    self.logger.warning(f"Impossible d'expander: {e}")

            # Cocher la checkbox
            checkbox = target_row.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
            checkbox_id = checkbox.get_attribute("id")

            if checkbox.is_selected():
                self.logger.info(f"Reception {codeReception} deja selectionnee")
            else:
                try:
                    label = target_row.find_element(By.CSS_SELECTOR, f"label[for='{checkbox_id}']")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label)
                    time.sleep(0.3)
                    label.click()
                    self.logger.info(f"Checkbox cochee via label pour {codeReception}")
                except Exception:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                    time.sleep(0.3)
                    driver.execute_script("arguments[0].click();", checkbox)
                    self.logger.info(f"Checkbox cochee via JavaScript pour {codeReception}")

            # Gerer la popup "Voulez-vous remplacer les donnees..."
            time.sleep(1)
            try:
                popup = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".s_alertbox_content"))
                )
                popup_text = popup.find_element(By.CSS_SELECTOR, ".s_alertbox_msg").text
                if "remplacer les donnees" in popup_text or "document d'origine" in popup_text:
                    oui_btn = popup.find_element(By.XPATH, "//a[@aria-label='Oui']")
                    oui_btn.click()
                    self.logger.info("Clique sur 'Oui' dans la popup")
                    time.sleep(1)
            except Exception:
                self.logger.info("Pas de popup de confirmation")

            return True

        except Exception as e:
            self.logger.error(f"Erreur cochage checkbox {codeReception}: {e}")
            return False

    # -----------------------------------------------------------------
    # Chercher du BR 
    # -----------------------------------------------------------------
    
    def _get_page_of_receiption(self, codeReception: str) -> dict[bool, str]:
        """
        chercher sur le BR dans les pages
        """

        driver = self.driver_manager.driver
        target_row = None
        attempt=0
        while not target_row  and  attempt<10:
            all_rows = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".s-grid-table-body tr.s-grid-row.s-grid-navig-row"
                )
            self.logger.info(f"{len(all_rows)} lignes dans le tableau {attempt+1}")
            for row in all_rows:
                try:
                    desc_div = row.find_element(By.CSS_SELECTOR, ".s-tree-node-desc-value")
                    text = desc_div.text.strip()
                    if text.startswith(codeReception):
                        target_row = row
                        self.logger.info(f"Ligne trouvee: {text}")
                        break
                except Exception:
                    continue
            
            if not target_row:
                self.logger.info("passe a page suivant ...")
                next_button = driver.find_element(By.XPATH, '//*[@id="s_app_body"]/div/article/div[1]/div[2]/div[4]/div/article/div[1]/div[2]/div/a[3]')
                next_button.click()
                time.sleep(1)
            
            attempt = attempt + 1

    
    def _set_in_first_page(self):
        """
        Retourner a page paremier 
        """
        driver = self.driver_manager.driver
        
        WebDriverWait(driver, 10).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.s_overlay"))
        )
        next_button = driver.find_element(By.XPATH, '//*[@id="s_app_body"]/div/article/div[1]/div[2]/div[4]/div/article/div[1]/div[2]/div/a[2]')
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(next_button)
        )
        for i in range(6):
            time.sleep(0.5)
            next_button.click()
        time.sleep(1)

    # ------------------------------------------------------------------
    # Saisie des informations de la facture
    # ------------------------------------------------------------------

    def saisi_information(self, typeF, codeFournisseur, factureFournisseur, DFF, Date,
                          list_codeReception: List[str], nom=""):
        """
        Saisit les informations de la facture et selectionne TOUS les codes reception.

        Args:
            list_codeReception: Liste de codes BR a cocher (ex: ["BR189847", "BR189850"])
        """
        self.logger.info(
            f"Saisir: Type={typeF}, Tier={codeFournisseur}, Receptions={list_codeReception}, "
            f"Facture={factureFournisseur}, Date={Date}"
        )
        driver = self.driver_manager.driver

        try:
            wait = WebDriverWait(driver, 2000000)
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a.s_page_action_add")))
            cree = driver.find_element(By.CSS_SELECTOR, "a.s_page_action_add")
            cree.click()
            time.sleep(2)
            self.wait_for_spinner_to_disappear(driver, 90000)

            # Type facture
            cf = self.get_input_by_label("Type facture")
            cf.click()
            time.sleep(0.5)
            cf.clear()
            cf.send_keys(typeF)
            cf.send_keys(Keys.TAB)
            time.sleep(1)

            # Fournisseur
            cf2 = self.get_input_by_label("Fournisseur")
            cf2.click()
            time.sleep(0.5)
            cf2.clear()
            cf2.send_keys(codeFournisseur)
            cf2.send_keys(Keys.TAB)
            time.sleep(2)

            # Ancien Code (facture fournisseur)
            AncienCode_input = self.get_input_by_label("Ancien Code")
            AncienCode_input.click()
            time.sleep(0.5)
            AncienCode_input.clear()
            AncienCode_input.send_keys(factureFournisseur)
            AncienCode_input.send_keys(Keys.TAB)
            time.sleep(1)

            # N°Depot (DFF)
            DFF_input = self.get_input_by_label("N°Dépôt")
            DFF_input.click()
            time.sleep(0.5)
            DFF_input.clear()
            DFF_input.send_keys(DFF)
            DFF_input.send_keys(Keys.TAB)
            time.sleep(1)
            # check if popup appears after DFF input 
            try:
                popup = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".s_alertbox_content"))
                )   
                popup_text = popup.find_element(By.CSS_SELECTOR, ".s_alertbox_msg").text
                if "Maj N°Facture et date fournisseur" in popup_text :
                    self.logger.info("Popup de changement de dépôt détectée, clique sur 'OK'")
                    oui_btn = popup.find_element(By.XPATH, "//a[@aria-label='OK']")
                    oui_btn.click()
                    time.sleep(1)   
            except Exception:
                self.logger.info("Pas de popup de changement de dépôt après saisie du DFF")

            # Selectionner TOUS les codes reception (ou retours si AVR)
            resultats_selection = self.selection_multiple_receptions(list_codeReception, typeF=typeF)
            echecs = [br for br, ok in resultats_selection.items() if not ok]
            if echecs:
                self.logger.warning(f"Receptions non selectionnees: {echecs}")
                # On continue quand meme avec les receptions qui ont reussi
                if all(not ok for ok in resultats_selection.values()):
                    self.logger.error("Aucune reception n'a pu etre selectionnee")
                    return False

            time.sleep(2)

            # HT calcule -> HT saisi
            HT_input = self.get_input_by_label("HT calculé")
            ht_value = HT_input.get_attribute('value')
            time.sleep(1)

            HT_saisi_input = self.get_input_by_label("HT saisi")
            HT_saisi_input.click()
            time.sleep(0.5)
            HT_saisi_input.clear()
            HT_saisi_input.send_keys(ht_value)
            HT_saisi_input.send_keys(Keys.TAB)
            time.sleep(1)

            # Ecart taxes -> Total taxes saisi
            Taxe = self.get_input_by_label("Ecart taxes")
            taxe_value = Taxe.get_attribute('value')
            if taxe_value and taxe_value.startswith('-'):
                taxe_value = taxe_value.lstrip('-')
            time.sleep(1)

            Taxe_saisi_input = self.get_input_by_label("Total taxes saisi")
            Taxe_saisi_input.click()
            time.sleep(0.5)
            Taxe_saisi_input.clear()
            Taxe_saisi_input.send_keys(taxe_value)
            Taxe_saisi_input.send_keys(Keys.TAB)
            time.sleep(1)

            # Date facture fournisseur
            date_input = self.get_input_by_label("Date fact.fou")
            date_input.click()
            time.sleep(0.5)
            # check if popup appears after DFF input 
            try:
                popup = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".s_alertbox_content"))
                )   
                popup_text = popup.find_element(By.CSS_SELECTOR, ".s_alertbox_msg").text
                if "Maj N°Facture et date fournisseur" in popup_text :
                    self.logger.info("Popup de changement de dépôt détectée, clique sur 'OK'")
                    oui_btn = popup.find_element(By.XPATH, "//a[@aria-label='OK']")
                    oui_btn.click()
                    time.sleep(1)   
            except Exception:
                self.logger.info("Pas de popup de changement de dépôt après saisie du DFF")
        
            date_input.clear()
            date_input.send_keys(Date)
            date_input.send_keys(Keys.TAB)
            time.sleep(1)

            # No fact.fou
            factureFrs_input = self.get_input_by_label("No fact.fou")
            factureFrs_input.click()
            time.sleep(0.5)
            factureFrs_input.clear()
            factureFrs_input.send_keys(factureFournisseur)
            factureFrs_input.send_keys(Keys.TAB)
            time.sleep(1)

            # Reference interne
            referenceIntern_input = self.get_input_by_label("Référence interne")
            referenceIntern_input.click()
            time.sleep(0.5)
            referenceIntern_input.clear()
            referenceIntern_input.send_keys(factureFournisseur)
            referenceIntern_input.send_keys(Keys.TAB)
            time.sleep(1)

            self.logger.info(f"Informations saisies pour {codeFournisseur} ({nom})")
            return True

        except Exception as e:
            self.logger.error(f"Erreur saisie information: {e}")
            return False

    # ------------------------------------------------------------------
    # Enregistrement
    # ------------------------------------------------------------------

    def clique_enregistrer(self):
        driver = self.driver_manager.driver
        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_check")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()
            time.sleep(5)
            self.wait_for_spinner_to_disappear(driver, 900000000)

            self.logger.info("Enregistrement clique")
            try:
                msg = self.read_popup_message()
                self.logger.info(f"Message de confirmation: {msg}")
                if "ATTENTION : Montants".lower() in msg.lower():
                    self.logger.warning("Le message de confirmation indique un probleme de montants")
                    header = driver.find_element(By.CLASS_NAME, "s_alertbox_header")
                    close_button = header.find_element(By.CLASS_NAME, "s_modal_close")
                    close_button.click()
                    time.sleep(1)
                    return False

            except Exception as e:
                self.logger.warning(f"Impossible de fermer la popup de confirmation: {e}")
                
            self.logger.info(f"Enregistrement reussi")
            time.sleep(3)
            return True
        except Exception as e:
            self.logger.error(f"Erreur enregistrement: {e}")
            driver.save_screenshot("ScreenShot/error_enregistrement.png")
            return False

    # ------------------------------------------------------------------
    # Traitement d'un groupe (une facture fournisseur)
    # ------------------------------------------------------------------

    def traiter_fournisseur(self, url, codeFournisseur, factureFournisseur, DFF, Date,
                            list_codeReception: List[str], nom="", typeF="FAF"):
        """
        Traite un groupe : une facture fournisseur avec plusieurs codes reception.

        Args:
            list_codeReception: Liste de codes BR a selectionner
        """
        self.logger.info("="*80)
        self.logger.info(f"TRAITEMENT : {nom if nom else codeFournisseur}")
        self.logger.info(f"DFF: {DFF} | Date: {Date} | Receptions: {list_codeReception}")
        self.logger.info("="*80)

        resultat = {
            'codeFournisseur': codeFournisseur,
            'factureFournisseur': factureFournisseur,
            'DFF': DFF,
            'Date': Date,
            'codesReception': list_codeReception,
            'nom': nom,
            'statut': 'Echec',
            'facturation_effectue': False,
            'message': ''
        }

        try:
            if not self.saisi_information(
                typeF=typeF,
                codeFournisseur=codeFournisseur,
                factureFournisseur=factureFournisseur,
                DFF=DFF,
                Date=Date,
                list_codeReception=list_codeReception,
                nom=nom
            ):
                self.logger.warning("Erreur saisie, tentative d'actualisation...")

                if self.sage_connector.refresh_with_popup_handling():
                    if not self.saisi_information(
                        typeF="FAF",
                        codeFournisseur=codeFournisseur,
                        factureFournisseur=factureFournisseur,
                        DFF=DFF,
                        Date=Date,
                        list_codeReception=list_codeReception,
                        nom=nom
                    ):
                        resultat['message'] = 'Erreur saisie apres actualisation'
                        error_info = self.handle_error_with_screenshot(
                            error_message=resultat['message'],
                            context=f"Fournisseur {codeFournisseur} - Facture {factureFournisseur}"
                        )
                        resultat['error_info'] = error_info
                        return resultat
                else:
                    resultat['message'] = 'Actualisation echouee'
                    error_info = self.handle_error_with_screenshot(
                        error_message=resultat['message'],
                        context=f"Fournisseur {codeFournisseur} - Actualisation"
                    )
                    resultat['error_info'] = error_info
                    return resultat

            time.sleep(2)
            if not self.clique_enregistrer():
                resultat['message'] = 'Erreur enregistrement'
                error_info = self.handle_error_with_screenshot(
                    error_message=resultat['message'],
                    context=f"Fournisseur {codeFournisseur} - Enregistrement"
                )
                resultat['error_info'] = error_info
                return resultat

            self.close_module()

            resultat['statut'] = 'Succes'
            resultat['facturation_effectue'] = True
            resultat['message'] = 'Facturation effectuee avec succes'

        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f"Erreur traitement fournisseur: {e}")
            error_info = self.handle_error_with_screenshot(
                error_message=str(e),
                context=f"Fournisseur {codeFournisseur} - Exception"
            )
            resultat['error_info'] = error_info

        return resultat
