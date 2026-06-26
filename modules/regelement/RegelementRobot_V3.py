# -*- coding: utf-8 -*-
"""
Module Règlement - Robot pour les règlements de factures Sage X3
Regroupe par Fournisseur → Factures → Articles

Version 3:
    - pour regelemt de l'avancement sans facture 
    - date réel et date d'échéance c'est la date d'aujourd'hui 
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

import pyautogui

TYPE_REGELEMENT = {
    1: "Effet à payer",
    2: "Chèques émis",
}

class RegelementRobot(BaseRobot, WebResultMixin):
    """Robot pour la gestion automatique des règlements de factures avec regroupement"""
    
    def __init__(self, headless: bool = False):
        """Initialiser le robot règlement"""
        BaseRobot.__init__(self, 'regelement')
        WebResultMixin.__init__(self)
        
        self.excel_handler = ExcelHandler()
        self.driver_manager.headless = headless
        
        # URL du module règlements
        self.url_regelement = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESPAY%252F2%252F%252FM%252F%26representation%3DWOPYFEFFFRA.%2524fusion%26profile%3D~(loc~%27fr-FR~role~%278ecdb3d1-8ca7-40ca-af08-76cb58c70740~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"
        self.url_home = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%3Frepresentation%3Dhome.%2524landing%26profile%3D~(loc~%27fr-FR~role~%278ecdb3d1-8ca7-40ca-af08-76cb58c70740~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"
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
            
            email_f = df.iloc[0]['email_expediteur'] if 'email_expediteur' in df.columns else "astitoumd@gmail.com"

            self.logger.info(f"{'='*80}")
            self.logger.info(f" {len(df)} ligne(s) à traiter")
            self.logger.info(f"{'='*80}")
            
            # 2. CONNEXION SAGE
            self.connect_sage()
            
            # Naviguer vers le module
            self.navigate_to_module(self.url_regelement)
            self.wait_for_spinner_to_disappear(self.driver_manager.driver, timeout=900000000)
            self.handle_popup("OK",  "GESPAY : Accès restreint par la licence")
            self.wait_for_spinner_to_disappear(self.driver_manager.driver, timeout=900000000)
            
            type_reg = int(df.iloc[0]['type_regelement'])
            self._choisir_mode_regelement(TYPE_REGELEMENT[type_reg])

            # 3. TRAITER CHAQUE LIGNE
            for idx, row in df.iterrows():
                if(row['Code_Frs'] == 'T2948' or row['Code_Frs'] == 'T4407'):
                    self.logger.info(f"🚀 Ligne {idx + 1} - FIN rencontrée, arrêt du traitement.")
                    resultat = {
                        'type': 'Ligne',
                        'statut': 'Echec',
                        'code_frs': str(row['Code_Frs']),
                        # return N_facture si non vide sinon return empty string
                        'num_facture': str(row['N_Facture']) if 'N_Facture' in row and not pd.isna(row['N_Facture']) else "",
                        'message': 'AKEG et AMS (T2948 et T4407) sont interdits pour le règlement, arrêt du traitement.',
                        'error_info': None
                    }
                    self.add_result(resultat)
                    continue
                
                if not self._verifie_sold_fournisseur(row) : 
                    self.logger.info("le solde fournisseur ne permet pas de saise ce regelement, s'il vous plait contacter M. PDG")
                    resultat = {
                        'type': 'Ligne',
                        'statut': 'Echec',
                        'code_frs': str(row['Code_Frs']),
                        # return N_facture si non vide sinon return empty string
                        'num_facture': str(row['N_Facture']) if 'N_Facture' in row and not pd.isna(row['N_Facture']) else "",
                        'message': 'Le solde fournisseur est insuffisant pour créer ce règlement.',
                        'error_info': None
                    }
                    self.add_result(resultat)
                    continue
                time.sleep(5)
                self.wait_for_spinner_to_disappear(self.driver_manager.driver, timeout=90000)
                self.wait_for_element_to_appear(self.driver_manager.driver, By.CSS_SELECTOR, "div.s-page-content-slot", timeout=60000)
                self.logger.info(f"{'='*80}")
                self.logger.info(f"📋 Ligne {idx + 1}/{len(df)}")
                self.logger.info(f"{'='*80}")

                resultat = self._traiter_ligne(row)
                self.add_result(resultat)

                if resultat['statut'] == 'Succes':
                    self.fournisseurs_traites += 1
                else:
                    self.fournisseurs_echec += 1
                    self.logger.warning(f" Échec ligne {idx + 1}, mais on continue...")
                
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
            self.logger.info(f" {self.fournisseurs_traites} ligne(s) traitée(s)")
            self.logger.info(f" {self.fournisseurs_echec} ligne(s) en échec")
            self.logger.info(f"💳 {self.total_factures} règlement(s) créé(s)")
            self.logger.info("="*80)
            
        except Exception as e:
            self.logger.error(f" ERREUR CRITIQUE: {e}")
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
            # self.navigate_to_module(self.url_home)
            self.disconnect_sage() 

    def _lire_et_valider_excel(self, excel_file: str) -> pd.DataFrame:
        """
        Lire et valider le fichier Excel
        v2:
            - Numero cheque est recupter automatique depuis sql
        """
        self.logger.info("="*80)
        self.logger.info("📖 LECTURE EXCEL")
        self.logger.info("="*80)
        
        colonnes_requises = [
            'Code_Frs',
            'N_Facture',
            'Refference',
            'Montant',
            'TVA',
            'type_regelement'
            # 'Date_Reel', # c'est date ajourd'hui
            # 'DateEcheance' # c'est date ajourd'hui
        ]
        
        df = self.excel_handler.read_excel(excel_file, required_columns=colonnes_requises)
        
        self.logger.info(f" {len(df)} ligne(s) lues")
        
        # Validation des colonnes importantes
        lignes_invalides = []
        for idx, row in df.iterrows():
            
            # SI type_regelement EST VIDE SAISI 1
            if pd.isna(row.get('type_regelement')) or str(row.get('type_regelement', '')).strip() == '':
                df.at[idx, 'type_regelement'] = 1

            colonnes_vides = []
            for col in ['Code_Frs', 'N_Facture', 'Montant']:
                if pd.isna(row[col]) or str(row[col]).strip() == '':
                    colonnes_vides.append(col)

            if colonnes_vides:
                lignes_invalides.append(idx)
                self.logger.warning(f" Ligne {idx+1} ignorée - Colonnes vides: {', '.join(colonnes_vides)}")
        
        if lignes_invalides:
            df = df.drop(df.index[lignes_invalides])
            self.logger.warning(f" {len(lignes_invalides)} ligne(s) invalide(s) ignorée(s)")
        
        self.logger.info(f" {len(df)} ligne(s) valides à traiter")
        return df
    
    def _traiter_ligne(self, row: pd.Series) -> Dict[str, Any]:
        """Traiter une ligne Excel (créer 1 règlement par ligne)"""
        resultat = {
            'type': 'Ligne',
            'statut': 'Echec',
            'code_frs': str(row['Code_Frs']),
            'num_facture': str(row['N_Facture'] if 'N_Facture' in row and not pd.isna(row['N_Facture']) else ""),
            'message': '',
            'error_info': None
        }
        
        driver = self.driver_manager.driver
        
        try:
            # Extraire les données de la ligne
            code_frs = str(row['Code_Frs'])
            num_facture = str(row['N_Facture']) if 'N_Facture' in row and not pd.isna(row['N_Facture']) else ""
            refference = str(row['Refference']) if not pd.isna(row['Refference']) else ""
            # libelle = str(row['Libelle']) if not pd.isna(row['Libelle']) else ""
            montant = str(row['Montant'])
            num_cheque = self._get_num_cheque_from_db(row['type_regelement'])  # Récupérer le numéro de chèque depuis la base de données
            tva = str(row['TVA']) if not pd.isna(row['TVA']) else ""
            if float(tva) == 0.0:
                tva = "0.1"  # pour éviter les problèmes de champ obligatoire dans le cas ou tva = 0    
            tier_endo = str(row['tier_endo']).strip() if 'tier_endo' in row and not pd.isna(row.get('tier_endo', None)) and str(row['tier_endo']).strip() != '' else None
            # date reel c'est date d'aujourd'hui
            date_reel = datetime.now().strftime('%d/%m/%Y')
            # date_reel = self._format_date(row['Date_Reel']) if not pd.isna(row['Date_Reel']) else ""
            date_echeance = datetime.now().strftime('%d/%m/%Y')  # Par défaut, on met la date d'aujourd'hui pour éviter les problèmes de formatage
            # date_echeance = self._format_date(row['DateEcheance']) if not pd.isna(row['DateEcheance']) else ""

            self.logger.info(f"{'-'*80}")
            self.logger.info(f"date_echeance: {date_echeance} - date_reel: {date_reel}")

            self.logger.info(f"🏢 Fournisseur: {code_frs}")
            self.logger.info(f"📋 Facture: {num_facture} - ")
            self.logger.info(f"💰 Montant: {montant} | Chèque: {num_cheque}")
            self.logger.info(f" Date Réel: {date_reel} | Date Échéance: {date_echeance}")

            # =================================================================
            # verfier est-ce c'est un reglement de l'avancement sans facture ou pas
            # 
            # =================================================================
            avance = False if num_facture.startswith("FF") else True
            self.logger.info(f"🔍 Type de règlement: {'Avance sans facture' if avance else 'Règlement avec facture'}")

            # =====================================================================================
            # Comparer le montant de la facture FF avec le montant de la facture fournisseur DFF
            # si y une ecart de montant entre la facture FF et la facture fournisseur DFF entre 5dh ou -5dh alors robot va prendre le montant de la facture fournisseur DFF 
            # si l'ecart de montant entre la facture FF et la facture fournisseur DFF superieur a 5dh ou inferieur a -5dh alors robot va eviter de faire le reglement.
            # =====================================================================================
            if not avance:
                montant_facture_frs = self._get_montant_facture_frs(num_facture)
                if montant_facture_frs is not None:
                    ecart = float(montant) - montant_facture_frs
                    self.logger.info(f" Montant facture fournisseur (DFF): {montant_facture_frs} | Écart: {ecart}")
                    if abs(ecart) > 5:
                        self.logger.warning(f" Écart de montant supérieur à 5 DH pour {num_facture}, évitement du règlement.")
                        resultat['message'] = f'Écart de montant de {ecart} DH entre la facture FF et la facture fournisseur DFF, évitement du règlement.'
                        return resultat
                    else:
                        self.logger.info(f" Écart de montant de {ecart} DH pour {num_facture}, ajustement du montant au montant de la facture fournisseur DFF.")
                        montant = str(montant_facture_frs)

            
            # 1. CRÉER LE RÈGLEMENT
            if not self._cree_regelement():
                self.logger.warning(f" Échec création règlement pour {num_facture}")
                error_info = self.handle_error_with_screenshot(
                    error_message='Erreur création règlement',
                    context=f"Facture {num_facture} - Création"
                )
                resultat['error_info'] = error_info
                resultat['message'] = 'Erreur création règlement'
                return resultat
            
            self.logger.info(f" Règlement créé")

            # =================================================================
            # =================================================================
            # 2. REMPLIR LES CHAMPS HEADER
            self.logger.info("📝 Remplissage header...")

            # Fournisseur
            fournisseur_input = self.get_input_by_label("Tiers")
            fournisseur_input.click()
            time.sleep(0.5)
            fournisseur_input.clear()
            fournisseur_input.send_keys(code_frs)
            fournisseur_input.send_keys(Keys.TAB)
            time.sleep(1)

            self._gere_popup_fournisseur()
            self.wait_stabilite()
            # =================================================================
            # =================================================================
            # 3. REMPLIR LA FACTURE DANS LE CHAMPS DE COMMANTAIRE
            self.logger.info(f"🔍 REMPLIR la Commantaire: {num_facture}")
            commentaire_input = self.get_input_by_label("Commentaire")
            commentaire_input.click()
            time.sleep(0.5)
            commentaire_input.clear()
            commentaire_input.send_keys(num_facture)
            commentaire_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            self.wait_stabilite()
            # =================================================================
            # =================================================================
            # 4. REMPLIR LA REFÉRENCE DE PIECE
            self.logger.info(f"🔍 REMPLIR la Refference de piece: {refference}")
            reference_input = self.get_input_by_label("Référence pièce")
            reference_input.click()
            time.sleep(0.5)
            reference_input.clear()
            reference_input.send_keys(refference.replace(" ", ""))
            reference_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            self.wait_stabilite()
            if self.read_popup_message() is not None:
                self.logger.warning(f" Popup détecté après saisie de la référence de pièce pour {refference}")
                error_info = self.handle_error_with_screenshot(
                    error_message='Popup détecté après saisie de la référence de pièce',
                    context=f"Facture {num_facture} - Référence pièce {refference}"
                )
                resultat['error_info'] = error_info
                try:
                    self.handle_popup("OK", "Référence erronée") 
                    close_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_close")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", close_btn)
                    time.sleep(0.5)
                    close_btn.click()
                except Exception as e:
                    self.logger.error(f" Erreur lors de la fermeture de la popup: {e}")
                return resultat
            # =================================================================
            # =================================================================
            # 5. SAIISIR Libelle
            self.wait_stabilite()
            self.logger.info(f"🔍 REMPLIR le Libelle: {num_cheque}")
            libelle_input = self.get_input_by_label("Libellé")
            libelle_input.click()
            time.sleep(0.5)
            libelle_input.clear()
            libelle_input.send_keys(num_cheque + "/BMCE/BRIQUETERIE JBEL A")
            libelle_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            self.wait_stabilite()
            banque_input = self.get_input_by_label("Banque", 96) # id de champ banque est change de 95 a 96 dans le cas de reglement de l'avance sans facture
            banque_input.click()
            time.sleep(0.5)
            banque_input.send_keys("B01")
            banque_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            self.wait_stabilite()
            # =================================================================
            # =================================================================
            # 6. REMPLIR MONTANT
            self.logger.info(f"🔍 REMPLIR le Montant: {montant}")
            montant_input = self.get_input_by_label("Montant Tiers")
            montant_input.click()
            time.sleep(0.5)
            montant_input.clear()   
            montant_input.send_keys(montant)
            montant_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            self.wait_stabilite()
            # =================================================================
            # =================================================================
            # 7. SÉLECTIONNER Numero cheque
            self.logger.info(f"🔍 REMPLIR le Numero cheque: {num_cheque}")
            num_cheque_input = self.get_input_by_label("Numéro chèque")
            num_cheque_input.click()
            time.sleep(0.5)
            num_cheque_input.clear()
            num_cheque_input.send_keys(num_cheque)
            num_cheque_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            self.wait_stabilite()
            if self._check_num_cheque_deja_utilise(num_cheque):
                self.logger.warning(f" Numéro de chèque {num_cheque} déjà utilisé")
                error_info = self.handle_error_with_screenshot(
                    error_message=f'Numéro de chèque {num_cheque} déjà utilisé',
                    context=f"Chèque {num_cheque}"
                )
                resultat['error_info'] = error_info
                return resultat
            self.wait_stabilite()
            Etablisstpayeur_input = self.get_input_by_label("Etablisst payeur")
            Etablisstpayeur_input.click()
            time.sleep(0.5)
            Etablisstpayeur_input.clear()
            Etablisstpayeur_input.send_keys("BMCE")
            Etablisstpayeur_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            self.wait_stabilite()
            # =================================================================
            # =================================================================
            # 8. REMPLIR TVA
            self.logger.info(f"🔍 REMPLIR la TVA: {tva}")
            tva_input = self.get_input_by_label("Montant TVA")
            tva_input.click()
            time.sleep(0.5)
            tva_input.clear()
            tva_input.send_keys(str(round(float(tva), 2)))
            tva_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            self.wait_stabilite()
            # =================================================================
            # =================================================================
            # 9. REMPLIR DATE REEL
            self.logger.info(f"🔍 REMPLIR la Date reel: {date_reel}")
            date_reel_input = self.get_input_by_label("Date réelle")
            date_reel_input.click()
            time.sleep(0.5)
            date_reel_input.clear()
            date_reel_input.send_keys(date_reel)
            date_reel_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            self.wait_stabilite()
            # =================================================================
            # verifier c'est une popup apparait
            if self.read_popup_message() is not None:
                self.logger.warning(f" Popup détecté après saisie de la date reel pour {num_facture}")
                error_info = self.handle_error_with_screenshot(
                    error_message='Popup détecté après saisie de la date reel',
                    context=f"Facture {num_facture} - Date réelle"
                )
                resultat['error_info'] = error_info
                return resultat

            # self.wait_for_spinner_to_disappear(driver=driver)
            self.wait_stabilite()
            # =================================================================
            # =================================================================
            # 10. REMPLIR DATE ECHEANCE
            if not avance:
                # Facture FF : date de départ = date facture SQL, montant = montant de la ligne
                if not self._saisir_date_echeance_v2(date_echeance, num_facture, resultat, float(montant)):
                    return resultat
                # if not self._saisir_date_echeance(date_echeance):
                #     return resultat
                # self.wait_for_spinner_to_disappear(driver=driver)    
                self.wait_stabilite()            
            else:
                # Avance sans facture : date de départ = aujourd'hui, montant = montant de la ligne
                if not self._saisir_date_echeance_avance(resultat, float(montant)):
                    return resultat


            # =================================================================
            # =================================================================
            # 11. REMPLIR LES DÉTAILS DE PAIEMENT    
            self.logger.info(f"🔍 {avance} , {num_facture} ")
            if not avance:
                # REMPLIR LES DÉTAILS DE PAIEMENT
                self.logger.info(f"🔍 REMPLIR les détails de paiement pour la facture ")       
                if self._remplir_detail_simple(num_facture):
                    self.total_factures += 1
                    self.logger.info(f" Détail OK")
                    if not self._saisir_date_echeance_v2(date_echeance, num_facture, resultat, float(montant)):
                        return resultat

                else:
                    self.logger.warning(f" Détail échec")
                    error_info = self.handle_error_with_screenshot(
                        error_message=f'Échec remplissage détail paiement',
                        context=f"Chèque {num_cheque} - Détail paiement"
                    )
                    resultat['error_info'] = error_info
                    self.logger.warning(f" Erreur lors du remplissage du détail de paiement pour {num_facture}")
                    return resultat
            else:
                # juste clique sur le champ montant banque 
                # pour re-formule la date d'échéance et la date réel dans le cas de règlement de l'avance sans facture
                self.logger.info(f"🔍 Cliquer sur le champ Montant banque pour reformuler la date d'échéance et la date réel dans le cas de règlement de l'avance sans facture")
                #pyautogui.press('esc') 

            # 12. TIERS ENDOSSATAIRE (optionnel)
            if tier_endo:
                self.logger.info(f"🔍 REMPLIR Tiers Endo.: {tier_endo}")
                endo_input = self.get_input_by_label("Endossable")
                time.sleep(0.5)
                label_endo = driver.find_element(By.CSS_SELECTOR, f"label[for='{endo_input.get_attribute('id')}']")
                label_endo.click()
                time.sleep(0.5)
                self.wait_stabilite()
                tier_endo_input = self.get_input_by_label("Tiers Endo.")
                tier_endo_input.click()
                time.sleep(0.5)
                tier_endo_input.clear()
                tier_endo_input.send_keys(tier_endo)
                tier_endo_input.send_keys(Keys.TAB)
                time.sleep(0.5)
                self.wait_stabilite()

            # =================================================================
            # 10. AJUSTER DATE ECHEANCE + ENREGISTRER (apres detail paiement)
            # =================================================================
            # self._ajuster_date_et_enregistrer(num_facture, resultat)
            if self._enregistrer_regelement():
                WebDriverWait(driver, 15).until(
                        EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.s_overlay"))
                    )
                input_reg = self.get_input_by_label("No règlement", 65)
                reg_num = input_reg.get_attribute("value")
                self.logger.info(f"Reg {reg_num}")
                resultat['statut'] = 'Succes'
                resultat['message'] = f'Règlement créé pour {num_facture}, N° Règlement: {reg_num}'
                
            
            
        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f" Erreur traitement ligne: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            error_info = self.handle_error_with_screenshot(
                error_message=str(e),
                context=f"Facture {resultat['num_facture']} - Exception"
            )
            resultat['error_info'] = error_info
        
        return resultat
    
    def _saisir_date_echeance_v2(self, date_echeance: str, num_facture: str, resultat: dict, montant_facture: float = 0.0) -> bool:
        """
        Calcule la date d'échéance optimale :
        1. Récupère la date de la facture depuis SQL
        2. Cherche le 1er mois (M+0 à M+5) où solde - montant > 0 ET date >= aujourd'hui
        3. Si la date calculée est < aujourd'hui, continue à chercher le mois suivant (avec vérif solde)
        4. Si aucun mois valide trouvé, fallback M+6 automatique
        """
        import calendar

        driver = self.driver_manager.driver
        today = datetime.now().date()

        # 1. Date de la facture depuis SQL
        date_facture = self._get_date_echeance_(num_facture)
        if date_facture is None:
            self.logger.warning(f"Date facture introuvable pour {num_facture}, fallback aujourd'hui")
            date_facture = today
        self.logger.info(f" Date facture SQL: {date_facture}, montant: {montant_facture}")

        # Si la date de facture est dans le passé, partir de aujourd'hui pour le calcul des mois
        if date_facture < today:
            self.logger.info(f" Date facture ({date_facture}) < aujourd'hui ({today}), base de calcul: aujourd'hui")
            date_facture = today

        # 2. Soldes mensuels depuis SQL
        soldes_par_mois = self._get_sold_par_mois(date_facture)
        self.logger.info(f" Soldes mensuels: {soldes_par_mois}")

        def dernier_jour_mois(annee, mois):
            return calendar.monthrange(annee, mois)[1]

        def mois_plus(base_date, delta):
            m = base_date.month + delta
            y = base_date.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1
            j = dernier_jour_mois(y, m)
            return base_date.replace(year=y, month=m, day=j)

        # 3. Chercher M+0 à M+5 : solde > montant ET date >= aujourd'hui
        date_echeance_calculee = None
        for delta in range(6):
            candidate = mois_plus(date_facture, delta)
            cle = (candidate.year, candidate.month)
            solde = soldes_par_mois.get(cle, 0.0)
            self.logger.info(f"  → M+{delta} {candidate.year}/{candidate.month:02d}: solde={solde}, montant={montant_facture}, reste={solde - montant_facture}, date={candidate}")

            if solde - montant_facture > 0 and candidate >= today:
                date_echeance_calculee = candidate
                self.logger.info(f" Mois retenu: M+{delta} → {date_echeance_calculee}")
                break

        # 4. Fallback M+6
        if date_echeance_calculee is None:
            date_echeance_calculee = mois_plus(date_facture, 6)
            self.logger.info(f" Aucun mois valide (M+0→M+5), fallback M+6: {date_echeance_calculee}")

        # 5. Si fallback aussi < aujourd'hui, prendre le mois courant ou suivant avec solde suffisant
        if date_echeance_calculee < today:
            self.logger.info(f"Date M+6 ({date_echeance_calculee}) encore < aujourd'hui, recherche mois futur avec solde...")
            date_echeance_calculee = None
            for delta in range(7, 13):
                candidate = mois_plus(date_facture, delta)
                cle = (candidate.year, candidate.month)
                solde = soldes_par_mois.get(cle, 0.0)
                self.logger.info(f"  → M+{delta} {candidate.year}/{candidate.month:02d}: solde={solde}, date={candidate}")
                if candidate >= today and solde - montant_facture > 0:
                    date_echeance_calculee = candidate
                    self.logger.info(f" Mois futur retenu: M+{delta} → {date_echeance_calculee}")
                    break
            if date_echeance_calculee is None:
                # Dernier recours : fin du mois prochain
                date_echeance_calculee = mois_plus(today, 1)
                self.logger.warning(f"Aucun mois futur avec solde, dernier recours: {date_echeance_calculee}")

        # 6. Saisir dans Sage avec gestion popup Décaissements-30
        date_echeance_input = self.get_input_by_label("Date échéance")
        date_str = date_echeance_calculee.strftime("%d/%m/%Y")
        date_echeance_input.click()
        # time.sleep(0.5)
        self.wait_stabilite()
        date_echeance_input.clear()
        self.wait_stabilite()
        date_echeance_input.send_keys(date_str)
        date_echeance_input.send_keys(Keys.TAB)
        time.sleep(0.5)
        self.wait_stabilite()
        if self.read_popup_message():
            self.handle_popup("OK", "+120")

            WebDriverWait(driver=self.driver_manager.driver, timeout=60).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_close"))
            )
            close_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_close")
            time.sleep(1)
            close_btn.click()
            return False

        self.wait_for_spinner_to_disappear(driver=driver)
        return True
        # for attempt in range(10):
        #     self.logger.info(f"[Tentative {attempt+1}] Saisie date échéance: {date_str}")

        #     popup_msg = self.read_popup_message()
        #     if popup_msg and "Décaissements-30" in popup_msg:
        #         self.logger.warning(f"Popup 'Décaissements-30%' détectée, +1 mois")
        #         self.handle_popup("OK", popup_msg)
        #         next_candidate = mois_plus(date_echeance_calculee, 1)
        #         cle = (next_candidate.year, next_candidate.month)
        #         solde = soldes_par_mois.get(cle, 0.0)
        #         self.logger.info(f"  → Popup fallback {next_candidate.year}/{next_candidate.month:02d}: solde={solde}")
        #         date_echeance_calculee = next_candidate
        #         time.sleep(0.5)
        #         continue
        #     elif popup_msg is not None:
        #         self.logger.warning(f" Popup inattendue: {popup_msg}")
        #         error_info = self.handle_error_with_screenshot(
        #             error_message="Popup inattendue après saisie de la date d'échéance",
        #             context=f"Facture {num_facture} - Date échéance v2"
        #         )
        #         resultat['error_info'] = error_info
        #         try:
        #             self.handle_popup("OK", popup_msg)
        #             close_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_close")
        #             driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", close_btn)
        #             time.sleep(0.5)
        #             close_btn.click()
        #         except Exception as e:
        #             self.logger.error(f"Erreur fermeture popup: {e}")
        #         return False
        #     else:
        #         return True

        # self.logger.warning(f" Impossible de saisir la date échéance après 10 tentatives pour {num_facture}")
        # return False

        return True

    def _saisir_date_echeance_avance(self, resultat: dict, montant_facture: float = 0.0) -> bool:
        """
        Pour avance sans facture : date de départ = aujourd'hui.
        Cherche M+0 à M+5 (depuis aujourd'hui) où solde - montant > 0.
        Fallback M+6 si aucun mois trouvé.
        """
        import calendar

        driver = self.driver_manager.driver
        today = datetime.now().date()

        self.logger.info(f" Avance sans facture - date départ: {today}, montant: {montant_facture}")

        soldes_par_mois = self._get_sold_par_mois(today)
        self.logger.info(f" Soldes mensuels: {soldes_par_mois}")

        def dernier_jour_mois(annee, mois):
            return calendar.monthrange(annee, mois)[1]

        def mois_plus(base_date, delta):
            m = base_date.month + delta
            y = base_date.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1
            j = dernier_jour_mois(y, m)
            return base_date.replace(year=y, month=m, day=j)

        # Chercher M+0 à M+5 depuis aujourd'hui
        date_echeance_calculee = None
        for delta in range(6):
            candidate = mois_plus(today, delta)
            cle = (candidate.year, candidate.month)
            solde = soldes_par_mois.get(cle, 0.0)
            self.logger.info(f"  → M+{delta} {candidate.year}/{candidate.month:02d}: solde={solde}, montant={montant_facture}, reste={solde - montant_facture}")

            if solde - montant_facture > 0:
                date_echeance_calculee = candidate
                self.logger.info(f" Mois retenu: M+{delta} → {date_echeance_calculee}")
                break

        # Fallback M+6
        if date_echeance_calculee is None:
            date_echeance_calculee = mois_plus(today, 6)
            self.logger.info(f" Aucun mois valide (M+0→M+5), fallback M+6: {date_echeance_calculee}")

        # Saisir dans Sage avec gestion popup Décaissements-30
        date_echeance_input = self.get_input_by_label("Date échéance")
        date_str = date_echeance_calculee.strftime("%d/%m/%Y")
        date_echeance_input.click()
        time.sleep(0.5)
        date_echeance_input.clear()
        date_echeance_input.send_keys(date_str)
        # date_echeance_input.send_keys(Keys.TAB)
        time.sleep(0.5)
        # for attempt in range(10):

        #     popup_msg = self.read_popup_message()
        #     if popup_msg and "Décaissements-30" in popup_msg:
        #         self.logger.warning(f"Popup 'Décaissements-30%' détectée, +1 mois")
        #         self.handle_popup("OK", popup_msg)
        #         next_candidate = mois_plus(date_echeance_calculee, 1)
        #         cle = (next_candidate.year, next_candidate.month)
        #         solde = soldes_par_mois.get(cle, 0.0)
        #         self.logger.info(f"  → Popup fallback {next_candidate.year}/{next_candidate.month:02d}: solde={solde}")
        #         date_echeance_calculee = next_candidate
        #         time.sleep(0.5)
        #         continue
        #     elif popup_msg is not None:
        #         self.logger.warning(f" Popup inattendue: {popup_msg}")
        #         error_info = self.handle_error_with_screenshot(
        #             error_message="Popup inattendue après saisie de la date d'échéance (avance)",
        #             context="Avance sans facture - Date échéance"
        #         )
        #         resultat['error_info'] = error_info
        #         try:
        #             self.handle_popup("OK", popup_msg)
        #             close_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_close")
        #             driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", close_btn)
        #             time.sleep(0.5)
        #             close_btn.click()
        #         except Exception as e:
        #             self.logger.error(f"Erreur fermeture popup: {e}")
        #         return False
        #     else:
        #         return True

        # self.logger.warning(f" Impossible de saisir la date échéance avance après 10 tentatives")
        return True

    def _saisir_date_echeance(self, date_echeance: str) -> bool:
        
        driver = self.driver_manager.driver
        self.wait_for_spinner_to_disappear(driver=driver)

        date_echeance_input = self.get_input_by_label("Date échéance")
        date_echeance_input.click()
        time.sleep(1)
        date_echeance_input.clear()
        time.sleep(1)
        date_echeance_input.send_keys(date_echeance)
        date_echeance_input.send_keys(Keys.TAB)
        time.sleep(3)

        if self.read_popup_message():
            self.handle_popup("OK", "+120")

            WebDriverWait(driver=self.driver_manager.driver, timeout=60).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_close"))
            )
            close_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_close")
            time.sleep(1)
            close_btn.click()
            return False

        self.wait_for_spinner_to_disappear(driver=driver)
        return True
        
    def _ajuster_date_et_enregistrer(self, num_facture: str, resultat: dict) -> bool:
        from datetime import timedelta
        driver = self.driver_manager.driver
        today = datetime.now().date()
        max_attempts = 10

        date_ech_input = self.get_input_by_label("Date échéance")
        raw_date = date_ech_input.get_attribute("value").strip()
        self.logger.info(f"Date echeance apres detail paiement: {raw_date}")

        date_ech = None
        for fmt in ("%d/%m/%Y", "%d/%m/%y"):
            try:
                date_ech = datetime.strptime(raw_date, fmt).date()
                break
            except ValueError:
                continue
        if date_ech is None:
            date_ech = today
            self.logger.warning(f"Date echeance illisible ({raw_date}), utilisation de aujourd'hui: {today}")

        if date_ech < today:
            date_ech = today + timedelta(days=1)
            self.logger.info(f"Date echeance < aujourd'hui, corrigee a: {date_ech.strftime('%d/%m/%Y')}")

        enregistrement_ok = False
        for attempt in range(max_attempts):
            date_str = date_ech.strftime("%d/%m/%Y")
            self.logger.info(f"[Tentative {attempt+1}] Saisie date echeance: {date_str}")

            date_ech_input.click()
            time.sleep(0.3)
            date_ech_input.clear()
            date_ech_input.send_keys(date_str)
            date_ech_input.send_keys(Keys.TAB)
            time.sleep(5)

            popup_msg = self.read_popup_message()
            self.logger.info(f"Popup message apres saisie date echeance: {popup_msg}")
            if popup_msg and "Décaissements-30" in popup_msg:
                self.logger.warning(f"Popup 'Decaissements-30%' apres saisie date, +1 mois")
                self.handle_popup("OK", popup_msg)
                new_month = date_ech.month % 12 + 1
                new_year = date_ech.year + (1 if date_ech.month == 12 else 0)
                date_ech = date_ech.replace(month=new_month, year=new_year)
                time.sleep(0.5)
                continue

            if self._enregistrer_regelement():
                input_reg = self.get_input_by_label("No règlement", 65)
                reg_num = input_reg.get_attribute("value")
                self.logger.info(f"Reg {reg_num}")
                resultat['statut'] = 'Succes'
                resultat['message'] = f'Règlement créé pour {num_facture}, N° Règlement: {reg_num}'
                self.logger.info(f" Règlement enregistré")
                enregistrement_ok = True
                break
            else:
                popup_msg_save = self.read_popup_message()
                self.logger.info(f"Popup message apres enregistrement: {popup_msg_save}")
                if popup_msg_save and "Décaissements-30" in popup_msg_save:
                    self.logger.warning(f"Popup 'Decaissements-30%' apres enregistrement, +1 mois")
                    self.handle_popup("OK", popup_msg_save)
                    new_month = date_ech.month % 12 + 1
                    new_year = date_ech.year + (1 if date_ech.month == 12 else 0)
                    date_ech = date_ech.replace(month=new_month, year=new_year)
                    time.sleep(0.5)
                    continue
                else:
                    self.logger.warning(f" Échec enregistrement règlement pour {num_facture}")
                    error_info = self.handle_error_with_screenshot(
                        error_message='Erreur enregistrement règlement',
                        context=f"Facture {num_facture} - Enregistrement"
                    )
                    resultat['error_info'] = error_info
                    resultat['message'] = 'Erreur enregistrement'
                    self.handle_popup("OK", "Date réelle supérieur à la date facture fournisseur+120")
                    try:
                        close_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_close")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", close_btn)
                        time.sleep(0.5)
                        close_btn.click()
                    except Exception:
                        pass
                    break

        if not enregistrement_ok:
            self.logger.error(f"Règlement non enregistré après {max_attempts} tentatives pour {num_facture}")
        return enregistrement_ok

    def _check_num_cheque_deja_utilise(self, num_cheque: str) -> bool:
        """Vérifier si le numéro de chèque est déjà utilisé"""
        driver = self.driver_manager.driver
        try:
            #check if popup appears
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, f"//pre[@class='s_alertbox_msg' and contains(text(), 'Le Numéro de série que vous avez entré est déjà utilsé!')]"))
            )
            self.logger.warning(f"Popup détecté pour le numéro de chèque: {num_cheque}")
            return True
        except Exception as e:
            return False
        return False
    
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
        self.logger.info(" RÉSUMÉ DU TRAITEMENT")
        self.logger.info("="*80)
        
        self.logger.info(f"🏢 {len(structure)} Fournisseur(s):")
        
        for code_frs, frs_data in structure.items():
            self.logger.info(f"   📦 Fournisseur: {code_frs}")
            self.logger.info(f"      {len(frs_data['factures'])} Facture(s):")
            
            for num_facture, facture_data in frs_data['factures'].items():
                nb_details = len(facture_data['details'])
                self.logger.info(f"         • {num_facture}: {facture_data['Numero_Cheque']} - {facture_data['montant_facture']} ({nb_details} détail(s))")
        
        self.logger.info("="*80)
    
    def _cree_regelement(self) -> bool:
        """Cliquer sur le bouton 'Créer Règlement'"""
        driver = self.driver_manager.driver
        try:
            time.sleep(5)
            
            add_button = driver.find_element(By.CSS_SELECTOR, "a.s_page_action_add")

            if "s-disabled" in add_button.get_attribute("class"):
                # Bouton désactivé 
                self.logger.info(" Bouton Add désactivé, impossible de créer un nouveau règlement")
                return False
            else:
                # Bouton activé
                self.logger.info(" Nouveau règlement créé")
                add_button.click()
                time.sleep(2)
                return True
        except Exception as e:
            self.logger.error(f" Erreur création règlement: {e}")
            return False

    def _enregistrer_regelement(self) -> bool:
        """Enregistrer le règlement"""
        driver = self.driver_manager.driver
        try:
            time.sleep(2)
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_check")
            # driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_check")))

            save_btn.click()

            time.sleep(5)
            
            self.wait_for_spinner_to_disappear(driver, timeout=120000000)
            try:
                self.logger.info("⏳ Attente de la popup de confirmation...")
                self.wait_for_element_to_appear(driver, By.CSS_SELECTOR, "a.s_modal_close", timeout=1000000)
                self.logger.info(" Popup de confirmation détectée, fermeture...")
                s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_modal_close")
                s_page_close.click()
                time.sleep(2)
                
                # verifier si le bouton close est désactivé ou pas
                a_close_btn = driver.find_element(By.XPATH, "//div[contains(@class, 's_page_crud_action_wrapper')]//a[contains(@class, 's_page_action_close')]")
                close_disabled = a_close_btn.get_attribute("disabled") is not None
                close_class_disabled = "s-disabled" in a_close_btn.get_attribute("class")
                if not close_disabled and not close_class_disabled:
                    try:
                        
                        close_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_close")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", close_btn)
                        time.sleep(0.5)
                        close_btn.click()

                        WebDriverWait(driver, 2).until(
                            EC.visibility_of_element_located((By.XPATH, "//pre[@class='s_alertbox_msg' and contains(text(), 'Continuer et abandonner votre création ?')]"))
                        )
                        # Cliquer sur "Oui"
                        oui_button = driver.find_element(By.XPATH, "//a[@aria-label='Oui']")
                        oui_button.click()
                        self.logger.info(" Confirmation abandon cliquée")
                        time.sleep(1)
                        return False
                    except:
                        # Pas de popup ou autre type de popup
                        return False
                    return False
            except:
                pass
            
            return True
        except Exception as e:
            self.logger.error(f" Erreur enregistrement: {e}")
            return False
        
    def _gere_popup_fournisseur(self):
        """Gérer la popup après saisie du fournisseur"""
        driver = self.driver_manager.driver
        
        try:
            time.sleep(1)
            # Attendre que la boîte de dialogue soit visible
            wait = WebDriverWait(driver, 10)
            dialog = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "s_alertbox")))

            # Cliquer sur OK
            ok_button = dialog.find_element(By.LINK_TEXT, "OK")
            ok_button.click()
            self.logger.info(" Popup 'OK' cliquée")
            time.sleep(1)
        except:
            # Pas de popup
            pass

    def _remplir_detail_simple(self, num_facture: str) -> bool:
        """
        Remplir un détail de paiement simplement (une seule ligne)
        Format: DEC [TAB] FAFOU [TAB] reference [TAB] [TAB]
        """
        driver = self.driver_manager.driver
        
        try:
            self.wait_for_spinner_to_disappear(driver=driver)

            WebDriverWait(driver, 15).until(
                        EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.s_overlay"))
                    )
            # Attendre le tableau
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-grid-slot-table-fixed"))
            )

            # Récupérer la première ligne du tableau des paiements
            rows_fixed = driver.find_elements(By.CSS_SELECTOR, ".s-page-content-slot .s-grid-slot-table-fixed .s-grid-fixed-table-body tr.s-grid-row")
            
            if not rows_fixed:
                self.logger.warning("Aucune ligne trouvée dans le tableau")
                return False
            
            # Prendre la première ligne
            target_row = rows_fixed[0]
            cells_fixed = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
            
            self.logger.info(f" {len(cells_fixed)} cellules trouvées")
            time.sleep(5)
            WebDriverWait(driver, 15).until(
                        EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.s_overlay"))
                    )
            # Cellule 1: DEC
            self.logger.info("Remplissage DEC...")
            if len(cells_fixed) > 0:
                cell_dec = cells_fixed[0]
                cell_dec.click()
                time.sleep(0.3)
                cell_dec.clear()
                cell_dec.send_keys("DEC")
                cell_dec.send_keys(Keys.TAB)
                time.sleep(0.3)
            WebDriverWait(driver, 15).until(
                        EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.s_overlay"))
                    )
            time.sleep(5)
            rows_scrool = driver.find_elements(By.CSS_SELECTOR, ".s-page-content-slot .s-grid-slot-table-scroll .s-grid-table-body tr.s-grid-row")
            self.logger.info(f" {len(rows_scrool)} ligne(s) trouvée(s) dans la partie scroll du tableau")
            if not rows_scrool:
                self.logger.warning("Aucune ligne trouvée dans le tableau")
                return False
            
            # Prendre la première ligne
            target_row = rows_scrool[0]
            cells_scrool = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
            
            self.logger.info(f" {len(cells_scrool)} cellules trouvées")
            # Cellule 2: FAFOU
            self.logger.info("Remplissage FAFOU...")
            if len(cells_scrool) > 0:
                cell_fafou = cells_scrool[0]
                cell_fafou.click()
                time.sleep(0.3)
                cell_fafou.clear()
                cell_fafou.send_keys("FAFOU")
                cell_fafou.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            # Cellule 3: Numéro Facture
            self.logger.info(f"Remplissage facture: {num_facture}...")
            if len(cells_scrool) > 1:
                cell_facture = cells_scrool[1]
                cell_facture.click()
                time.sleep(0.3)
                cell_facture.clear()
                cell_facture.send_keys(num_facture)
                cell_facture.send_keys(Keys.TAB)
                time.sleep(1)
                try:
                    if not self.handle_popup("OK", "ATTENTION ECHEANCE MISE A JOUR"):
                        self.logger.warning(f" Popup de mise à jour d'échéance détectée pour la facture {num_facture}, mais le bouton OK n'a pas été trouvé ou cliqué")   

                        if self.handle_popup("OK", "Aucune échéance"):
                            close_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_close")
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", close_btn)
                            time.sleep(0.5)
                            close_btn.click()
                            return False
                except Exception as e:
                    self.logger.error(f"Erreur lors de la gestion de la popup: {e}")
                    if self.handle_popup("OK", "Référence erronée"):
                        close_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_close")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", close_btn)
                        time.sleep(0.5)
                        close_btn.click()
                    return False
                
                time.sleep(1)

            self.logger.info(f"Remplissage auto montant:...")
            if len(cells_scrool) > 5:
                cell_facture = cells_scrool[5]
                cell_facture.click()
                time.sleep(0.3)
                # cell_facture.send_keys(Keys.TAB)
                time.sleep(1)

                self.handle_popup("OK", "ATTENTION ECHEANCE MISE A JOUR")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur remplissage détail: {e}")
            self.handle_error_with_screenshot(
                error_message=str(e),
                context="Remplissage détail - Exception"
            )
            return False
    
    def _choisir_mode_regelement(self, mode: str) -> bool:
        """Choisir le mode de règlement"""
        driver = self.driver_manager.driver
        
        try:
            modal = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, 
                    "//span[@title='Choix transaction' and @class='s_modal_page_title']"))
            )

            # Attendre l'élément spécifique "FEFF FRA F - Effet à payer" et cliquer
            element = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, 
                    f"//div[contains(@class, 's-inplace-value-read') and contains(text(), '{mode}')]"))
            )
            element.click()
            return True
        except Exception as e:
            self.logger.error(f"Erreur choix mode règlement: {e}")
            return False
        
    def _get_num_cheque_from_db(self, mode: int) -> str:
        """Récupérer le numéro de chèque depuis la base de données"""
        # cree la connexion à la base de données ( SQLSERVER ) et récupérer le numéro de chèque
        import pyodbc

        try:
            conn = pyodbc.connect(
                "DRIVER={ODBC Driver 17 for SQL Server};"
                "SERVER=192.168.1.241\\ERPX3;"  # Notez le double backslash
                "DATABASE=x3;"
                "UID=X3U;"
                "PWD=SQL@2019;"
            )
            cursor = conn.cursor()
            print("Connected to SQL Server successfully!")
            cursor.execute(f"select TOP 1 XNUM_0, L.NSER_0, XPAM_0 as ModReg from BASE1.XACRCAL L WHERE FLG_0<>2 AND XPAM_0={mode} ORDER BY L.ROWID ASC")
            row = cursor.fetchone()
            if row:
                num_cheque = row[1]
                # return L.NSER_0 as NumCheque
                return num_cheque
            else:
                raise Exception("Aucun numéro de chèque disponible dans la base de données")
        except Exception as e:
            raise Exception(f"Erreur connexion SQL ou récupération numéro de chèque: {e}")
        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass

    def _get_date_echeance_(self, Facture: str):
        """Retourne la date de la facture depuis SQL (objet date Python) ou None"""
        import pyodbc
        from datetime import date as date_type

        try:
            conn = pyodbc.connect(
                "DRIVER={ODBC Driver 17 for SQL Server};"
                "SERVER=192.168.1.241\\ERPX3;"
                "DATABASE=x3;"
                "UID=X3U;"
                "PWD=SQL@2019;"
            )
            cursor = conn.cursor()
            cursor.execute(f"SELECT DUDDAT_0 FROM BASE1.GACCDUDATE WHERE NUM_0='{Facture}'")
            row = cursor.fetchone()
            if row and row[0] is not None:
                val = row[0]
                if hasattr(val, 'date'):
                    return val.date()
                if isinstance(val, date_type):
                    return val
                return pd.to_datetime(str(val)).date()
            else:
                self.logger.warning(f"Aucune date trouvée pour la facture {Facture}")
                return None
        except Exception as e:
            self.logger.error(f"Erreur récupération date facture {Facture}: {e}")
            return None
        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass

    def _get_sold_par_mois(self, date_facture) -> dict:
        """
        Retourne un dict {(annee, mois): total_mnt} pour tous les mois
        à partir du mois de la facture jusqu'à M+6.
        """
        import pyodbc

        annee_facture = date_facture.year if hasattr(date_facture, 'year') else int(str(date_facture)[:4])
        mois_facture = date_facture.month if hasattr(date_facture, 'month') else int(str(date_facture)[5:7])

        requete = f"""
            WITH CombinedData AS (
                SELECT
                    XMNT_0 * 0.7 AS MNT,
                    DUDDAT_0 AS DAT
                FROM BASE1.XENDECS

                UNION ALL

                SELECT
                    E.XMNT_0 AS MNT,
                    D.DAT_0 AS DAT
                FROM BASE1.XDATE D
                LEFT JOIN BASE1.XDECECS E ON E.DUDDAT_0 = D.DAT_0
            )
            SELECT
                YEAR(DAT) AS Annee,
                MONTH(DAT) AS Mois,
                SUM(ISNULL(MNT, 0)) AS Total_MNT
            FROM CombinedData
            WHERE DAT IS NOT NULL
              AND (YEAR(DAT) > {annee_facture} OR (YEAR(DAT) = {annee_facture} AND MONTH(DAT) >= {mois_facture}))
            GROUP BY YEAR(DAT), MONTH(DAT)
            ORDER BY Annee ASC, Mois ASC;
        """

        try:
            conn = pyodbc.connect(
                "DRIVER={ODBC Driver 17 for SQL Server};"
                "SERVER=192.168.1.241\\ERPX3;"
                "DATABASE=x3;"
                "UID=X3U;"
                "PWD=SQL@2019;"
            )
            cursor = conn.cursor()
            cursor.execute(requete)
            rows = cursor.fetchall()
            result = {}
            for row in rows:
                annee, mois, total = int(row[0]), int(row[1]), float(row[2]) if row[2] is not None else 0.0
                result[(annee, mois)] = total
            return result
        except Exception as e:
            self.logger.error(f"Erreur récupération soldes par mois: {e}")
            return {}
        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass
    
    def _verifie_sold_fournisseur(self, row : pd.DataFrame):
        """"verifier le montant de reglement avec sold de fournisseur"""
        try:
            code_fournisseur = row['Code_Frs']
            montant_reg = row['Montant']
            sold_fournisseur = self._get_sold_fournisseur(code_fournisseur=code_fournisseur) or 0.0


            if montant_reg > sold_fournisseur :
                # recuperer l id de la demande
                demande_id = row['demande_id']
                self.logger.info(f"id de la demande {demande_id} ")
                
                if self._get_status_demande(int(demande_id)) == 'valide_pdg':
                    self.logger.info(f"la damsnde {demande_id} est valide par pdg")
                    return True
                
                self.logger.info(f"la demand non trouve {demande_id}")
                return False
        except Exception as e : 
            self.logger.error(e)
            return False
    
    def _get_status_demande(self, demande_id: int):
        """ Recuperer status d'un demande avance """
        import mysql.connector
        query_demand_id = f"""SELECT * FROM avances_demandes where id = {demande_id}"""
        # Establish connection
        conn = mysql.connector.connect(
            host="192.168.1.211",
            user="root",
            password="root123",
            database="facturation"
        )

        # Create cursor
        cursor = conn.cursor(dictionary=True)

        # Execute query
        cursor.execute(query_demand_id)
        row = cursor.fetchone()
        print(row)
        if row and row is not None:
            print(row['statut'])
            self.logger.info(row['statut'])
            return row['statut']
        else:
            self.logger.warning(f"id de la demande non trouve {demande_id}")
            return None

    def _get_sold_fournisseur(self, code_fournisseur: str):
        """ recuperer sold fournisseur"""
        import pyodbc
        # Requete pour recuperer le solde fournisseur
        QUERY_SOLDE_FOURNISSEUR = f"""
        SELECT
            (
            F.Soldedépart +
            F.enReception +
            F.enFacturation +
            F.facture +
            F.retourNF +
            F.Réglement +
            F.ECART_AUT
            ) AS Solde
        FROM BASE1.SITUATION_FOU F
        WHERE F.BPRNUM_0 = '{code_fournisseur}'
        """

        try:
            conn = pyodbc.connect(
                "DRIVER={ODBC Driver 17 for SQL Server};"
                "SERVER=192.168.1.241\\ERPX3;"
                "DATABASE=x3;"
                "UID=X3U;"
                "PWD=SQL@2019;"
            )
            cursor = conn.cursor()
            cursor.execute(QUERY_SOLDE_FOURNISSEUR)
            row = cursor.fetchone()
            if row and row[0] is not None:
                return float(row[0])
            else:
                self.logger.warning(f"Aucun Resultat trouve de ce fournisseur {code_fournisseur}")
                return None
        except Exception as e:
            self.logger.error(f"Erreur récupération sold fournisseur {code_fournisseur}: {e}")
            return None
        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass

    def _get_montant_facture_frs(self, num_facture: str) -> float:
        """Récupérer le montant de la facture depuis SQL"""
        import pyodbc
        query_montant_dff = f"""SELECT XMNT_0 AS MONTANT_DFF FROM BASE1.PINVOICE PIN
                                LEFT JOIN BASE1.XDEPFACT DPF ON DPF.XNUM_0 = PIN.XDFF_0
                                WHERE NUM_0 = ' {num_facture}'"""
        try:
            conn = pyodbc.connect(
                "DRIVER={ODBC Driver 17 for SQL Server};"
                "SERVER=192.168.1.241\\ERPX3;"
                "DATABASE=x3;"
                "UID=X3U;"
                "PWD=SQL@2019;"
            )
            cursor = conn.cursor()
            cursor.execute(query_montant_dff)
            row = cursor.fetchone()
            if row and row[0] is not None:
                return float(row[0])
            else:
                self.logger.warning(f"Aucun montant trouvé pour la facture {num_facture}")
                return None
        except Exception as e:
            self.logger.error(f"Erreur récupération montant facture {num_facture}: {e}")
            return None
        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass