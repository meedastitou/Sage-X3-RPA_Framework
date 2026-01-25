# -*- coding: utf-8 -*-
"""
Module Règlement - Robot pour les règlements de factures Sage X3
Regroupe par Fournisseur → Factures → Articles
"""
from typing import Dict, Any, List
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from collections import defaultdict
import time

from core.base_robot import BaseRobot
from core.web_result_mixin import WebResultMixin
from utils.excel_handler import ExcelHandler


class RegelementRobot(BaseRobot, WebResultMixin):
    """Robot pour la gestion automatique des règlements de factures avec regroupement"""
    
    def __init__(self, headless: bool = False):
        """Initialiser le robot règlement"""
        BaseRobot.__init__(self, 'regelement')
        WebResultMixin.__init__(self)
        
        self.excel_handler = ExcelHandler()
        self.driver_manager.headless = headless
        
        # URL du module règlements
        self.url_regelement = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FPREPROD%2F%24sessions%3Ff%3DGESRGL%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%2765059cf7-11e9-4b40-bac9-66ef183fb4e1~ep~%2764a56978-56ab-46f1-8d83-ed18f7fa6484~appConn~())"
        
        # Compteurs
        self.fournisseurs_traites = 0
        self.fournisseurs_echec = 0
        self.total_factures = 0
        
        self.logger.info(f"🤖 Robot Règlement initialisé (REGROUPEMENT PAR FOURNISSEUR)")
    
    def execute(self, excel_file: str, url: str = None):
        """
        Exécuter le traitement des règlements
        Créer un règlement par ligne Excel
        
        Args:
            excel_file: Chemin du fichier Excel
            url: URL du module (optionnel)
        """
        email_f = ""
        try:
            # 1. LIRE ET VALIDER L'EXCEL
            df = self._lire_et_valider_excel(excel_file)
            email_f = df.iloc[0]['email_expediteur'] if 'email_expediteur' in df.columns else ""

            self.logger.info(f"{'='*80}")
            self.logger.info(f"📊 {len(df)} ligne(s) à traiter")
            self.logger.info(f"{'='*80}")
            
            # 2. CONNEXION SAGE
            self.connect_sage()
            
            # 3. TRAITER CHAQUE LIGNE
            for idx, row in df.iterrows():
                # Naviguer vers le module
                self.navigate_to_module(self.url_regelement)
                time.sleep(5)
                self.wait_for_spinner_to_disappear(self.driver_manager.driver, timeout=90000)

                self.logger.info(f"{'='*80}")
                self.logger.info(f"📋 Ligne {idx + 1}/{len(df)}")
                self.logger.info(f"{'='*80}")
                
                resultat = self._traiter_ligne(row)
                self.add_result(resultat)

                if resultat['statut'] == 'Succes':
                    self.fournisseurs_traites += 1
                else:
                    self.fournisseurs_echec += 1
                    self.logger.warning(f"⚠️ Échec ligne {idx + 1}, mais on continue...")
                
                time.sleep(1)
            
            # 4. BILAN FINAL
            self.add_result({
                'type': 'BILAN_FINAL',
                'statut': 'SUCCES' if self.fournisseurs_echec == 0 else 'PARTIEL',
                'lignes_traitees': self.fournisseurs_traites,
                'lignes_echec': self.fournisseurs_echec,
                'total_regelements': self.total_factures,
                'message': f'{self.fournisseurs_traites} ligne(s) traitée(s), {self.total_factures} règlement(s)'
            })
            
            # 5. SAUVEGARDER RAPPORT
            self.save_report()
            
            # 6. ENVOYER RÉSULTATS WEB
            self.send_results_to_web(email_f)
            
            self.logger.info("="*80)
            self.logger.info("🎉 PROCESSUS TERMINÉ")
            self.logger.info(f"✅ {self.fournisseurs_traites} ligne(s) traitée(s)")
            self.logger.info(f"❌ {self.fournisseurs_echec} ligne(s) en échec")
            self.logger.info(f"💳 {self.total_factures} règlement(s) créé(s)")
            self.logger.info("="*80)
            
        except Exception as e:
            self.logger.error(f"❌ ERREUR CRITIQUE: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            self.add_result({
                'type': 'ERREUR',
                'statut': 'ECHEC',
                'message': str(e)
            })
            
            self.save_report()
            self.send_results_to_web(email_f)

        finally:
            self.logger.info("Deconnexion du robot...")
            self.disconnect_sage() 
    
    def _lire_et_valider_excel(self, excel_file: str) -> pd.DataFrame:
        """Lire et valider le fichier Excel"""
        self.logger.info("="*80)
        self.logger.info("📖 LECTURE EXCEL")
        self.logger.info("="*80)
        
        colonnes_requises = [
            'Code_Frs',
            'N_Facture',
            'Refference',
            'Libelle',
            'Montant',
            'Numero_Cheque',
            'TVA',
            'Date_Reel',
            'DateEcheance'
        ]
        
        df = self.excel_handler.read_excel(excel_file, required_columns=colonnes_requises)
        
        self.logger.info(f"✅ {len(df)} ligne(s) lues")
        
        # Validation des colonnes importantes
        lignes_invalides = []
        for idx, row in df.iterrows():
            colonnes_vides = []
            for col in ['Code_Frs', 'N_Facture', 'Montant', 'Numero_Cheque']:
                if pd.isna(row[col]) or str(row[col]).strip() == '':
                    colonnes_vides.append(col)

            if colonnes_vides:
                lignes_invalides.append(idx)
                self.logger.warning(f"⚠️ Ligne {idx+1} ignorée - Colonnes vides: {', '.join(colonnes_vides)}")
        
        if lignes_invalides:
            df = df.drop(df.index[lignes_invalides])
            self.logger.warning(f"⚠️ {len(lignes_invalides)} ligne(s) invalide(s) ignorée(s)")
        
        self.logger.info(f"✅ {len(df)} ligne(s) valides à traiter")
        return df
    
    def _regrouper_donnees(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        DÉPRÉCIÉ: Cette méthode n'est plus utilisée.
        On traite directement chaque ligne du DataFrame.
        """
        pass
    
    def _traiter_ligne(self, row: pd.Series) -> Dict[str, Any]:
        """Traiter une ligne Excel (créer 1 règlement par ligne)"""
        resultat = {
            'type': 'Ligne',
            'statut': 'Echec',
            'code_frs': str(row['Code_Frs']),
            'num_facture': str(row['N_Facture']),
            'message': '',
            'error_info': None
        }
        
        driver = self.driver_manager.driver
        
        try:
            # Extraire les données de la ligne
            code_frs = str(row['Code_Frs'])
            num_facture = str(row['N_Facture'])
            refference = str(row['Refference']) if not pd.isna(row['Refference']) else ""
            libelle = str(row['Libelle']) if not pd.isna(row['Libelle']) else ""
            montant = str(row['Montant'])
            num_cheque = str(row['Numero_Cheque']) if not pd.isna(row['Numero_Cheque']) else ""
            tva = str(row['TVA']) if not pd.isna(row['TVA']) else ""
            date_reel = self._format_date(row['Date_Reel']) if not pd.isna(row['Date_Reel']) else ""
            date_echeance = self._format_date(row['DateEcheance']) if not pd.isna(row['DateEcheance']) else ""
            
            self.logger.info(f"🏢 Fournisseur: {code_frs}")
            self.logger.info(f"📋 Facture: {num_facture} - {libelle}")
            self.logger.info(f"💰 Montant: {montant} | Chèque: {num_cheque}")
            
            # 1. CRÉER LE RÈGLEMENT
            if not self._cree_regelement():
                self.logger.warning(f"❌ Échec création règlement pour {num_facture}")
                error_info = self.handle_error_with_screenshot(
                    error_message='Erreur création règlement',
                    context=f"Facture {num_facture} - Création"
                )
                resultat['error_info'] = error_info
                resultat['message'] = 'Erreur création règlement'
                return resultat
            
            self.logger.info(f"✅ Règlement créé")
            
            # 2. REMPLIR LES CHAMPS HEADER
            self.logger.info("📝 Remplissage header...")

            # Fournisseur
            fournisseur_input = self.get_input_by_label("Fournisseur")
            fournisseur_input.click()
            time.sleep(0.5)
            fournisseur_input.clear()
            fournisseur_input.send_keys(code_frs)
            fournisseur_input.send_keys(Keys.TAB)
            time.sleep(1)

            self._gere_popup_fournisseur()

            # 3. REMPLIR LA FACTURE DANS LE CHAMPS DE COMMANTAIRE
            self.logger.info(f"🔍 REMPLIR la Commantaire: {num_facture}")

            # =================================================================
            # =================================================================

            # 4. REMPLIR LA REFÉRENCE DE PIECE
            self.logger.info(f"🔍 REMPLIR la Refference de piece: {refference}")

            # =================================================================
            # =================================================================

            # 5. SAIISIR Libelle
            self.logger.info(f"🔍 REMPLIR le Libelle: {libelle}")

            # =================================================================
            # =================================================================

            # 6. REMPLIR MONTANT
            self.logger.info(f"🔍 REMPLIR le Montant: {montant}")

            # =================================================================
            # =================================================================
            # 7. SÉLECTIONNER Numero cheque
            self.logger.info(f"🔍 REMPLIR le Numero cheque: {num_cheque}")

            # =================================================================
            # =================================================================
            # 8. REMPLIR TVA
            self.logger.info(f"🔍 REMPLIR la TVA: {tva}")

            # =================================================================
            # =================================================================
            # 9. REMPLIR DATE REEL
            self.logger.info(f"🔍 REMPLIR la Date reel: {date_reel}")

            # =================================================================
            # =================================================================
            # 10. REMPLIR DATE ECHEANCE
            self.logger.info(f"🔍 REMPLIR la Date echeance: {date_echeance}")

            # =================================================================
            # =================================================================
            
            # 11. REMPLIR LES DÉTAILS DE PAIEMENT - REMPLIR LA FACTURE


            # if not self._selectionner_facture_simple(num_facture):
            #     self.logger.warning(f"❌ Facture {num_facture} non trouvée")
            #     error_info = self.handle_error_with_screenshot(
            #         error_message=f'Facture {num_facture} non trouvée',
            #         context=f"Facture {num_facture} - Sélection"
            #     )
            #     resultat['error_info'] = error_info
            #     resultat['message'] = f'Facture {num_facture} non trouvée'
            #     return resultat
            
            # 4. REMPLIR LES DÉTAILS DE PAIEMENT
            self.logger.info(f"💳 Détail paiement: Chèque {num_cheque}")
            
            if self._remplir_detail_simple(num_facture):
                self.total_factures += 1
                self.logger.info(f"✅ Détail OK")
            else:
                self.logger.warning(f"⚠️ Détail échec")
                error_info = self.handle_error_with_screenshot(
                    error_message=f'Échec remplissage détail paiement',
                    context=f"Chèque {num_cheque} - Détail paiement"
                )
                resultat['error_info'] = error_info

            # 5. ENREGISTRER
            if self._enregistrer_regelement():
                resultat['statut'] = 'Succes'
                resultat['message'] = f'Règlement créé pour {num_facture}'
                self.logger.info(f"✅ Règlement enregistré")
            else:
                error_info = self.handle_error_with_screenshot(
                    error_message='Erreur enregistrement règlement',
                    context=f"Facture {num_facture} - Enregistrement"
                )
                resultat['error_info'] = error_info
                resultat['message'] = 'Erreur enregistrement'
            
        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f"❌ Erreur traitement ligne: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            error_info = self.handle_error_with_screenshot(
                error_message=str(e),
                context=f"Facture {resultat['num_facture']} - Exception"
            )
            resultat['error_info'] = error_info
        
        return resultat
    
    def _format_date(self, date_value) -> str:
        """Formater la date au format JJ/MM/AAAA"""
        try:
            # Si c'est un nombre Excel, le convertir
            if isinstance(date_value, (int, float)):
                date_obj = pd.Timestamp('1899-12-30') + pd.Timedelta(days=float(date_value))
                return date_obj.strftime('%d/%m/%Y')
            else:
                date_obj = pd.to_datetime(date_value)
                return date_obj.strftime('%d/%m/%Y')
        except Exception as e:
            self.logger.error(f"Erreur conversion date: {e}")
            return ""  # Valeur par défaut en cas d'erreur
    
    def _afficher_resume(self, structure: Dict):
        """Afficher un résumé de la structure"""
        self.logger.info("="*80)
        self.logger.info("📊 RÉSUMÉ DU TRAITEMENT")
        self.logger.info("="*80)
        
        self.logger.info(f"🏢 {len(structure)} Fournisseur(s):")
        
        for code_frs, frs_data in structure.items():
            self.logger.info(f"   📦 Fournisseur: {code_frs}")
            self.logger.info(f"      {len(frs_data['factures'])} Facture(s):")
            
            for num_facture, facture_data in frs_data['factures'].items():
                nb_details = len(facture_data['details'])
                self.logger.info(f"         • {num_facture}: {facture_data['libelle']} - {facture_data['montant_facture']} ({nb_details} détail(s))")
        
        self.logger.info("="*80)
    
    def _traiter_fournisseur(self, code_frs: str, frs_data: Dict) -> Dict[str, Any]:
        """Traiter un fournisseur (toutes ses factures)"""
        resultat = {
            'type': 'Fournisseur',
            'code_frs': code_frs,
            'statut': 'Echec',
            'factures_traitees': 0,
            'factures_echec': 0,
            'message': ''
        }
        
        try:
            # Traiter chaque facture du fournisseur
            for num_facture, facture_data in frs_data['factures'].items():
                self.logger.info(f"{'─'*80}")
                self.logger.info(f"📋 Facture: {num_facture}")
                self.logger.info(f"{'─'*80}")
                
                resultat_facture = self._traiter_facture(
                    code_frs=code_frs,
                    num_facture=num_facture,
                    montant_facture=facture_data['montant_facture'],
                    date_reel=facture_data['date_reel'],
                    date_echeance=facture_data['date_echeance'],
                    details=facture_data['details']
                )
                
                self.add_result(resultat_facture)
                
                if resultat_facture['statut'] == 'Succes':
                    resultat['factures_traitees'] += 1
                else:
                    resultat['factures_echec'] += 1
            
            # Statut global fournisseur
            if resultat['factures_echec'] == 0:
                resultat['statut'] = 'Succes'
                resultat['message'] = f'{resultat["factures_traitees"]} facture(s) traitée(s)'
            else:
                resultat['message'] = f'{resultat["factures_traitees"]} factures OK, {resultat["factures_echec"]} factures échec'
            
            self.logger.info(f"✅ Fournisseur {code_frs}: {resultat['message']}")
            
        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f"❌ Erreur fournisseur {code_frs}: {e}")
        finally:
            # Fermer le module avec confirmation d'abandon
            self.close_module(confirm_abandon=True)
            time.sleep(2)

        return resultat
    
    def _traiter_facture(self, code_frs: str, num_facture: str, montant_facture: str,
                         date_reel: str, date_echeance: str, details: List[Dict]) -> Dict[str, Any]:
        """Traiter une facture avec ses paiements"""
        resultat = {
            'type': 'Facture',
            'num_facture': num_facture,
            'code_frs': code_frs,
            'statut': 'Echec',
            'details_traites': 0,
            'message': ''
        }
        
        driver = self.driver_manager.driver
        
        try:
            # 1. CRÉER LE RÈGLEMENT
            if self._cree_regelement():
                self.logger.info(f"✅ Règlement créé pour facture {num_facture}")
            else:
                self.logger.warning(f"❌ Échec création règlement pour facture {num_facture}")
                resultat['message'] = 'Erreur création règlement'
                return resultat
            
            # 2. REMPLIR LES CHAMPS HEADER
            self.logger.info("📝 Remplissage header...")

            # Fournisseur
            fournisseur_input = self.get_input_by_label("Fournisseur")
            fournisseur_input.click()
            time.sleep(0.5)
            fournisseur_input.clear()
            fournisseur_input.send_keys(code_frs)
            fournisseur_input.send_keys(Keys.TAB)
            time.sleep(1)

            self._gere_popup_fournisseur()

            # 3. SÉLECTIONNER LA FACTURE
            self.logger.info(f"🔍 Sélection facture: {num_facture}")

            if not self._selectionner_facture(num_facture, details):
                self.logger.warning(f"❌ Facture {num_facture} non trouvée")
                resultat['message'] = f'Facture {num_facture} non trouvée'
                return resultat
            
            # 4. REMPLIR LES DÉTAILS DE PAIEMENT
            for idx, detail in enumerate(details, 1):
                self.logger.info(f"   💳 Détail {idx}/{len(details)}: Chèque {detail['num_cheque']}")
                
                if self._remplir_detail_paiement(detail, idx):
                    resultat['details_traites'] += 1
                    self.total_factures += 1
                    self.logger.info(f"   ✅ Détail {detail['num_cheque']} OK")
                else:
                    self.logger.warning(f"   ⚠️ Détail {detail['num_cheque']} échec")

                time.sleep(0.5)

            # 5. ENREGISTRER
            if self._enregistrer_regelement():
                resultat['statut'] = 'Succes'
                resultat['message'] = f'{resultat["details_traites"]}/{len(details)} détail(s) traité(s)'
                self.logger.info(f"✅ Facture {num_facture} enregistrée")
            else:
                resultat['message'] = 'Erreur enregistrement'
            
        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f"❌ Erreur facture {num_facture}: {e}")
        
        return resultat
    
    def _cree_regelement(self) -> bool:
        """Cliquer sur le bouton 'Créer Règlement'"""
        driver = self.driver_manager.driver
        try:
            time.sleep(2)
            add_button = driver.find_element(By.CSS_SELECTOR, "a.s_page_action_add")

            if "s-disabled" in add_button.get_attribute("class"):
                # Bouton désactivé 
                self.logger.info("❌ Bouton Add désactivé, impossible de créer un nouveau règlement")
                return False
            else:
                # Bouton activé
                self.logger.info("✅ Nouveau règlement créé")
                add_button.click()
                time.sleep(2)
                return True
        except Exception as e:
            self.logger.error(f"❌ Erreur création règlement: {e}")
            return False

    def _selectionner_facture(self, num_facture: str, details: List[Dict]) -> bool:
        """
        Sélectionner la facture dans le tableau 'Sélection factures'
        
        Args:
            num_facture: Numéro de la facture
            details: Liste des détails de paiement
        
        Returns:
            True si facture sélectionnée, False sinon
        """
        driver = self.driver_manager.driver
        
        try:
            self.logger.info(f"🔍 Sélection facture: {num_facture}")
            
            # 1. Cliquer sur "Sélection factures" pour ouvrir la section
            try:
                factures_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[@title='Sélection factures']"))
                )
                factures_btn.click()
                self.logger.info("✅ Section 'Sélection factures' ouverte")
                time.sleep(1)
            except:
                self.logger.warning("⚠️ Bouton 'Sélection factures' non trouvé, tableau déjà ouvert")
            
            # 2. Attendre le tableau
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-grid-table-body"))
            )
            time.sleep(1)
            
            # 3. Récupérer toutes les lignes
            rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
            self.logger.info(f"📊 {len(rows)} ligne(s) trouvée(s) dans le tableau")
            
            # 4. Parcourir les lignes pour trouver la facture
            for idx, row in enumerate(rows):
                try:
                    # Vérifier si ligne visible
                    style = row.get_attribute('style') or ''
                    if 'display: none' in style or 'display:none' in style:
                        continue
                    
                    # Récupérer le texte de la ligne
                    ligne_text = row.text.strip()
                    
                    # Vérifier si c'est notre facture
                    if num_facture in ligne_text:
                        self.logger.info(f"✅ Facture trouvée: {ligne_text}")
                        
                        # Récupérer la checkbox
                        checkbox = row.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                        checkbox_id = checkbox.get_attribute("id")
                        
                        # Cocher si pas déjà coché
                        if not checkbox.is_selected():
                            label = row.find_element(By.CSS_SELECTOR, f"label[for='{checkbox_id}']")
                            
                            # Scroll vers l'élément
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label)
                            time.sleep(0.3)
                            
                            # Cliquer sur le label
                            try:
                                label.click()
                            except:
                                # Si le clic normal échoue, utiliser JavaScript
                                driver.execute_script("arguments[0].click();", label)
                            
                            time.sleep(0.5)
                            
                            self.logger.info(f"   ☑️ Facture {num_facture} cochée")
                        else:
                            self.logger.info(f"   ⚪ Facture {num_facture} déjà cochée")
                        
                        # Gérer la popup de confirmation
                        time.sleep(1)
                        try:
                            oui_btn = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, "//a[@aria-label='Oui']"))
                            )
                            oui_btn.click()
                            self.logger.info("✅ Popup 'Oui' cliquée")
                            time.sleep(1)
                        except:
                            self.logger.debug("ℹ️ Pas de popup de confirmation")
                        
                        return True
                
                except Exception as e:
                    self.logger.debug(f"⚠️ Erreur ligne {idx}: {e}")
                    continue
            
            self.logger.error(f"❌ Facture {num_facture} non trouvée dans le tableau")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Erreur sélection facture: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _remplir_detail_paiement(self, detail: Dict, ligne_num: int) -> bool:
        """Remplir les données d'un détail de paiement"""
        
        driver = self.driver_manager.driver

        self.logger.info(f"🖊️ Remplissage détail paiement dans la ligne {ligne_num}")
        try:
            # Attendre le tableau
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-grid-table-body"))
            )

            table = driver.find_element(By.XPATH, 
                "//section[contains(@class, 's-h1')]//div[contains(text(), 'Paiements')]/ancestor::section//table[contains(@class, 's-grid-table-body')]"
            )
            # Trouver toutes les lignes
            rows = table.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
            self.logger.info(f"📊 {len(rows)} ligne(s) dans le tableau pour remplissage")
            
            # Chercher la bonne ligne (par numéro de ligne)
            target_row = None
            row_count = 0
            for idx, row in enumerate(rows):
                try:
                    # Chercher la cellule avec le numéro de ligne
                    row_number_cell = row.find_element(By.CSS_SELECTOR, ".s-record-row-index")
                    if row_number_cell and row_number_cell.text.strip() == str(ligne_num):
                        target_row = row
                        row_count = ligne_num
                        break
                except:
                    continue
            
            if not target_row:
                # Si pas trouvé par numéro, prendre simplement la énième ligne
                if ligne_num <= len(rows):
                    target_row = rows[ligne_num - 1]
                    row_count = ligne_num
                else:
                    self.logger.warning(f"Ligne {ligne_num} non trouvée dans le tableau")
                    return False
            
            self.logger.info(f"   📍 Ligne trouvée: {row_count}")

            # Modifier les cellules
            cells = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
            
            # Numéro de Chèque (adapter l'index selon la structure du tableau)
            if detail['num_cheque'] and len(cells) > 0:
                self.logger.info("Remplissage numéro chèque...")
                cheque_cell = cells[0]
                cheque_cell.click()
                time.sleep(0.3)
                cheque_cell.clear()
                cheque_cell.send_keys(detail['num_cheque'])
                cheque_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            # Montant (adapter l'index selon la structure du tableau)
            if detail['montant'] and len(cells) > 1:
                self.logger.info("Remplissage montant...")
                montant_cell = cells[1]  
                montant_cell.click()
                time.sleep(0.3)
                montant_cell.clear()
                montant_cell.send_keys(detail['montant'])
                montant_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            # Observation si elle existe
            if detail['observation'] and len(cells) > 2:
                self.logger.info("Remplissage observation...")
                obs_cell = cells[2]
                obs_cell.click()
                time.sleep(0.3)
                obs_cell.clear()
                obs_cell.send_keys(detail['observation'])
                obs_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur remplissage détail: {e}")
            return False
    
    def _enregistrer_regelement(self) -> bool:
        """Enregistrer le règlement"""
        driver = self.driver_manager.driver
        
        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_check")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()

            time.sleep(5)

            self.wait_for_spinner_to_disappear(driver, timeout=120000)
            
            time.sleep(4)
            try:
                s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
                s_page_close.click()
                time.sleep(2)
            except:
                pass
            
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur enregistrement: {e}")
            return False
        
    def _gere_popup_fournisseur(self):
        """Gérer la popup après saisie du fournisseur"""
        driver = self.driver_manager.driver
        
        try:
            time.sleep(1)
            # Attendre que la boîte de dialogue soit visible
            wait = WebDriverWait(driver, 2)
            dialog = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "s_alertbox")))

            # Cliquer sur OK
            ok_button = dialog.find_element(By.LINK_TEXT, "OK")
            ok_button.click()
            self.logger.info("✅ Popup 'OK' cliquée")
            time.sleep(1)
        except:
            # Pas de popup
            pass

    def _selectionner_facture_simple(self, num_facture: str) -> bool:
        """
        Sélectionner la facture simplement (une seule ligne par traitement)
        """
        driver = self.driver_manager.driver
        
        try:
            self.logger.info(f"🔍 Sélection facture: {num_facture}")
            
            # 1. Cliquer sur "Sélection factures" pour ouvrir la section
            try:
                factures_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[@title='Sélection factures']"))
                )
                factures_btn.click()
                self.logger.info("✅ Section 'Sélection factures' ouverte")
                time.sleep(1)
            except:
                self.logger.warning("⚠️ Bouton 'Sélection factures' non trouvé, tableau déjà ouvert")
            
            # 2. Attendre le tableau
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-grid-table-body"))
            )
            time.sleep(1)
            
            # 3. Récupérer toutes les lignes
            rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
            self.logger.info(f"📊 {len(rows)} ligne(s) trouvée(s)")
            
            # 4. Chercher la facture
            for row in rows:
                try:
                    style = row.get_attribute('style') or ''
                    if 'display: none' in style:
                        continue
                    
                    ligne_text = row.text.strip()
                    
                    if num_facture in ligne_text:
                        self.logger.info(f"✅ Facture trouvée: {ligne_text}")
                        
                        # Cocher la facture
                        checkbox = row.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                        if not checkbox.is_selected():
                            label = row.find_element(By.CSS_SELECTOR, f"label[for='{checkbox.get_attribute('id')}']")
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label)
                            time.sleep(0.3)
                            label.click()
                            time.sleep(0.5)
                        
                        # Gérer popup confirmation
                        time.sleep(1)
                        try:
                            oui_btn = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, "//a[@aria-label='Oui']"))
                            )
                            oui_btn.click()
                            time.sleep(1)
                        except:
                            pass
                        
                        return True
                except:
                    continue
            
            self.logger.error(f"❌ Facture {num_facture} non trouvée")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Erreur sélection facture: {e}")
            self.handle_error_with_screenshot(
                error_message=str(e),
                context="Sélection facture - Exception"
            )
            return False
    
    def _remplir_detail_simple(self, num_facture: str) -> bool:
        """
        Remplir un détail de paiement simplement (une seule ligne)
        """
        driver = self.driver_manager.driver
        
        try:
            # Attendre le tableau
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-grid-table-body"))
            )

            # Récupérer la première ligne du tableau des paiements
            rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
            
            if not rows:
                self.logger.warning("Aucune ligne trouvée dans le tableau")
                return False
            
            # Prendre la première ligne
            target_row = rows[0]
            cells = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
            
            self.logger.info(f"📊 {len(cells)} cellules trouvées")
            
            # Numéro de Facture
            self.logger.info("Remplissage facture...")
            facture_cell = cells[0]
            facture_cell.click()
            time.sleep(0.3)
            facture_cell.clear()
            facture_cell.send_keys(num_facture)
            facture_cell.send_keys(Keys.TAB)
            time.sleep(0.3)
            
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur remplissage détail: {e}")
            self.handle_error_with_screenshot(
                error_message=str(e),
                context="Remplissage détail - Exception"
            )
            return False
