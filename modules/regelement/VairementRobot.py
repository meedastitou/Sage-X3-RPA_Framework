# =====================================================
#  Regelement via vairement Robot
#  Version 1 - 13/02/2026
#  Objectif : Automatiser les règlements de vairement  
#  
# =====================================================

from typing import Dict, Any, List
import pandas as pd
from core.sage_connector import SageConnector
from core.web_result_mixin import WebResultMixin
from modules.regelement.OrderVairementRobot import OrderVairementRobot
from utils.excel_handler import ExcelHandler
from core.logger import Logger
from core.base_robot import BaseRobot
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime
from selenium.webdriver.common.keys import Keys


class VairementRobot(BaseRobot, WebResultMixin):
    """Initialiser le robot règlement"""
    def __init__(self, headless: bool = False):  
        
        BaseRobot.__init__(self, 'vairement')
        WebResultMixin.__init__(self)
        
        self.excel_handler = ExcelHandler()
        self.driver_manager.headless = headless

        self.url_regelement = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESPAY%252F2%252F%252FM%252F%26representation%3DWOPYFEFFFRA.%2524fusion%26profile%3D~(loc~%27fr-FR~role~%278ecdb3d1-8ca7-40ca-af08-76cb58c70740~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"

        # Initialisé après connect_sage() pour partager le même driver
        self.order_virement_robot = None
    
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
            
            # email_f = df.iloc[0]['email_expediteur'] if 'email_expediteur' in df.columns else "astitoumd@gmail.com"

            self.logger.info(f"{'='*80}")
            # self.logger.info(f"📊 {len(df)} ligne(s) à traiter")
            self.logger.info(f"{'='*80}")
            
            # 2. CONNEXION SAGE
            self.connect_sage()

            # Créer le OrderVairementRobot APRÈS connexion pour partager le même sage_connector/driver
            self.order_virement_robot = OrderVairementRobot(self)

            # =================================================================
            # RECUPERER LE NUMERO D'ORDRE DE VIREMENT
            # =================================================================
            Numero_order_virement = self.order_virement_robot.get_numero_order_virement(df)
            self.logger.info(f"Numéro d'ordre de virement: {Numero_order_virement}")

            input("Appuyez sur Entrée pour continuer 1...")  # Pause pour vérification manuelle


            # Naviguer vers le module
            self.navigate_to_module(self.url_regelement)
            self.wait_for_spinner_to_disappear(self.driver_manager.driver, timeout=900000000)
            self.handle_popup("OK",  "GESPAY : Accès restreint par la licence")
            self.wait_for_spinner_to_disappear(self.driver_manager.driver, timeout=900000000)
            self._choisir_mode_regelement("Virement national")

            # # 3. TRAITER CHAQUE LIGNE
            for idx, row in df.iterrows():
               
                self.logger.info(f"🚀 Ligne {idx + 1} - FIN rencontrée, arrêt du traitement.")
                time.sleep(5)
                self.wait_for_spinner_to_disappear(self.driver_manager.driver, timeout=90000)
                self.wait_for_element_to_appear(self.driver_manager.driver, By.CSS_SELECTOR, "div.s-page-content-slot", timeout=60000)
                self.logger.info(f"{'='*80}")
                self.logger.info(f"📋 Ligne {idx + 1}/{len(df)}")
                self.logger.info(f"{'='*80}")

                resultat = self._traiter_ligne(row, Numero_order_virement)
                self.add_result(resultat)

                if resultat['statut'] == 'Succes':
                    self.fournisseurs_traites += 1
                else:
                    self.fournisseurs_echec += 1
                    self.logger.warning(f"⚠️ Échec ligne {idx + 1}, mais on continue...")
                
                time.sleep(1)
            
            # # 4. BILAN FINAL
            # self.add_result({
            #     'type': 'BILAN_FINAL',
            #     'statut': 'SUCCES' if self.fournisseurs_echec == 0 else 'PARTIEL',
            #     'lignes_traitees': self.fournisseurs_traites,
            #     'lignes_echec': self.fournisseurs_echec,
            #     'total_regelements': self.total_factures,
            #     'message': f'{self.fournisseurs_traites} ligne(s) traitée(s), {self.total_factures} règlement(s)'
            # })
            
            # # 5. SAUVEGARDER RAPPORT
            # self.save_report()
            
            # # 6. ENVOYER RÉSULTATS WEB
            # self.send_results_to_web(email_f)
            
            # self.logger.info("="*80)
            # self.logger.info("🎉 PROCESSUS TERMINÉ")
            # self.logger.info(f"✅ {self.fournisseurs_traites} ligne(s) traitée(s)")
            # self.logger.info(f"❌ {self.fournisseurs_echec} ligne(s) en échec")
            # self.logger.info(f"💳 {self.total_factures} règlement(s) créé(s)")
            # self.logger.info("="*80)
            
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
            pass
        finally:
            # self.logger.info("Deconnexion du robot...")
            # # self.navigate_to_module(self.url_home)
            # self.disconnect_sage() 
            pass

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
            'objet',
            'type_virement',
            'Montant',
            'N_Facture',
            'Refference',
            'TVA'
            # 'Date_Reel', # c'est date ajourd'hui
            # 'DateEcheance' # c'est date ajourd'hui
        ]
        
        df = self.excel_handler.read_excel(excel_file, required_columns=colonnes_requises)
        
        self.logger.info(f"✅ {len(df)} ligne(s) lues")
        
        # Validation des colonnes importantes
        lignes_invalides = []
        for idx, row in df.iterrows():
            colonnes_vides = []
            for col in ['Code_Frs', 'Montant', 'type_virement', 'objet']:
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
     
    def _traiter_ligne(self, row: pd.Series, numero_order_vairement: str) -> Dict[str, Any]:
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
            montant = str(row['Montant'])
            num_cheque = self._get_num_cheque_from_db()  # Récupérer le numéro de chèque depuis la base de données
            tva = str(row['TVA']) if not pd.isna(row['TVA']) else ""

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
            self.logger.info(f"📅 Date Réel: {date_reel} | Date Échéance: {date_echeance}")

            # =================================================================
            # verfier est-ce c'est un reglement de l'avancement sans facture ou pas
            # 
            # =================================================================
            avance = False if num_facture.startswith("FF") else True
            self.logger.info(f"🔍 Type de règlement: {'Avance sans facture' if avance else 'Règlement avec facture'}")
            input("Vérifier le type de règlement, puis appuyer sur Entrée pour continuer...")
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

            # =================================================================
            # =================================================================
            # 4. REMPLIR LA REFÉRENCE DE PIECE
            self.logger.info(f"🔍 REMPLIR la Refference de piece: {refference}")
            reference_input = self.get_input_by_label("Référence pièce")
            reference_input.click()
            time.sleep(0.5)
            reference_input.clear()
            reference_input.send_keys(refference)
            reference_input.send_keys(Keys.TAB)
            time.sleep(0.5)

            # =================================================================
            # =================================================================
            # 5. SAIISIR Libelle
            self.logger.info(f"🔍 REMPLIR le Libelle: {num_cheque}")
            libelle_input = self.get_input_by_label("Libellé")
            libelle_input.click()
            time.sleep(0.5)
            libelle_input.clear()
            libelle_input.send_keys(num_cheque + "/BMCE/BRIQUETERIE JBEL A")
            libelle_input.send_keys(Keys.TAB)
            time.sleep(0.5)

            banque_input = self.get_input_by_label("Banque", 95)
            banque_input.click()
            time.sleep(0.5)
            banque_input.send_keys("B01")
            banque_input.send_keys(Keys.TAB)
            time.sleep(0.5)

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

            if self._check_num_cheque_deja_utilise(num_cheque):
                self.logger.warning(f"⚠️ Numéro de chèque {num_cheque} déjà utilisé")
                error_info = self.handle_error_with_screenshot(
                    error_message=f'Numéro de chèque {num_cheque} déjà utilisé',
                    context=f"Chèque {num_cheque}"
                )
                resultat['error_info'] = error_info
                return resultat
           
            Etablisstpayeur_input = self.get_input_by_label("Etablisst payeur")
            Etablisstpayeur_input.click()
            time.sleep(0.5)
            Etablisstpayeur_input.clear()
            Etablisstpayeur_input.send_keys("BMCE")
            Etablisstpayeur_input.send_keys(Keys.TAB)
            time.sleep(0.5)

            # =================================================================
            # =================================================================
            # 8. REMPLIR TVA
            self.logger.info(f"🔍 REMPLIR la TVA: {tva}")
            tva_input = self.get_input_by_label("Montant TVA")
            tva_input.click()
            time.sleep(0.5)
            tva_input.clear()
            tva_input.send_keys(tva)
            tva_input.send_keys(Keys.TAB)
            time.sleep(0.5)

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
    
            # =================================================================
            # =================================================================
            # 10. REMPLIR Order Vairement
            self.logger.info(f"🔍 REMPLIR Order Vairement: {numero_order_vairement}")
            date_reel_input = self.get_input_by_label("Ordre Virement")
            date_reel_input.click()
            time.sleep(0.5)
            date_reel_input.clear()
            date_reel_input.send_keys(numero_order_vairement)
            date_reel_input.send_keys(Keys.TAB)
            time.sleep(0.5)

            # =================================================================
            # =================================================================
            # 11. REMPLIR LES DÉTAILS DE PAIEMENT    
            self.logger.info(f"🔍 {avance} , {num_facture} ")
            if not avance:
                # REMPLIR LES DÉTAILS DE PAIEMENT
                self.logger.info(f"🔍 REMPLIR les détails de paiement pour la facture ")       
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
                    return resultat
            else:
                # juste clique sur le champ montant banque 
                # pour re-formule la date d'échéance et la date réel dans le cas de règlement de l'avance sans facture
                Montant_banque_input = self.get_input_by_label("Tiers Endossé")
                Montant_banque_input.click()   


            input("Vérifier les champs, puis appuyer sur Entrée pour enregistrer...")
            # 12. ENREGISTRER
            if self._enregistrer_regelement():
                input_reg = self.get_input_by_label("No règlement", 65)
                reg_num = input_reg.get_attribute("value")
                resultat['statut'] = 'Succes'
                resultat['message'] = f'Règlement créé pour {num_facture}, N° Règlement: {reg_num}'
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
        self.logger.info("📊 RÉSUMÉ DU TRAITEMENT")
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

    def _enregistrer_regelement(self) -> bool:
        """Enregistrer le règlement"""
        driver = self.driver_manager.driver
        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_check")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()

            time.sleep(5)
            
            self.wait_for_spinner_to_disappear(driver, timeout=120000000)
            try:
                self.wait_for_element_to_appear(driver, By.CSS_SELECTOR, "a.s_page_close", timeout=1000000)
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
            wait = WebDriverWait(driver, 10)
            dialog = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "s_alertbox")))

            # Cliquer sur OK
            ok_button = dialog.find_element(By.LINK_TEXT, "OK")
            ok_button.click()
            self.logger.info("✅ Popup 'OK' cliquée")
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
            
            self.logger.info(f"📊 {len(cells_fixed)} cellules trouvées")
            time.sleep(5)
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
            
            time.sleep(5)
            rows_scrool = driver.find_elements(By.CSS_SELECTOR, ".s-page-content-slot .s-grid-slot-table-scroll .s-grid-table-body tr.s-grid-row")
            self.logger.info(f"📊 {len(rows_scrool)} ligne(s) trouvée(s) dans la partie scroll du tableau")
            if not rows_scrool:
                self.logger.warning("Aucune ligne trouvée dans le tableau")
                return False
            
            # Prendre la première ligne
            target_row = rows_scrool[0]
            cells_scrool = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
            
            self.logger.info(f"📊 {len(cells_scrool)} cellules trouvées")
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
                self.handle_popup("OK", "ATTENTION ECHEANCE MISE A JOUR")
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
    
    def _get_num_cheque_from_db(self) -> str:
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
            cursor.execute("select TOP 1 XNUM_0, L.NSER_0, XPAM_0 as ModReg from BASE1.XACRCAL L WHERE FLG_0<>2 AND XPAM_0=5 ORDER BY L.ROWID ASC")
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
   