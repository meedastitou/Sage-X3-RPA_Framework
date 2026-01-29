# -*- coding: utf-8 -*-
"""
Module Lettrage - Robot principal
Intégration complète du code de lettrage dans le framework
"""
from typing import Dict, Any
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

from core.base_robot import BaseRobot
from core.web_result_mixin import WebResultMixin
from utils.excel_handler import ExcelHandler
from datetime import datetime

class FacturationRobot(BaseRobot, WebResultMixin):
    """Robot pour le facturation automatique des fournisseurs"""
    
    def __init__(self, headless: bool = False):
        """
        Initialiser le robot facturation
        
        Args:
            headless: Mode sans interface
        """
        BaseRobot.__init__(self, 'facturation')
        WebResultMixin.__init__(self)

        self.excel_handler = ExcelHandler()

        self.url_facturation = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESPIH%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%278ecdb3d1-8ca7-40ca-af08-76cb58c70740~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"
        # Compteurs pour les statistiques
        self.factures_traitees = 0
        self.factures_echec = 0

        self.logger.info(f"🤖 Robot Facturation initialisé")
    
    def execute(self, excel_file: str, url: str = None):
        """
        Exécuter la facturation

        Args:
            excel_file: Chemin du fichier Excel
            url: URL du module Sage X3
        """
        driver = self.driver_manager.driver
        email_f = ""

        try:
            # Lire Excel
            df = self.excel_handler.read_excel(
                excel_file,
                required_columns=['Code', 'DFF', 'FactureFrs', 'Date', 'BR']
            )

            # Récupérer l'email si disponible
            if 'email_expediteur' in df.columns:
                email_f = df.iloc[0]['email_expediteur']

            self.logger.info(f"📊 {len(df)} lignes à traiter")

            # Connexion Sage
            self.connect_sage()

            # Traiter chaque ligne
            for idx, row in df.iterrows():
                self.navigate_to_module(self.url_facturation)
                time.sleep(1)
                self.wait_for_spinner_to_disappear(driver, 600000)
                
                self.logger.info(f"\n{'='*80}")
                self.logger.info(f"📌 LIGNE {idx+1}/{len(df)}")
                self.logger.info(f"{'='*80}")

                code = str(row['Code'])
                dff = str(row['DFF'])
                # factureFrs = 'FN°' + str(row['FactureFrs'])
                factureFrs = str(row['FactureFrs'])

                try:
                    # Si c'est un nombre Excel, le convertir
                    if isinstance(row['Date'], (int, float)):
                        date_obj = pd.Timestamp('1899-12-30') + pd.Timedelta(days=float(row['Date']))
                    else:
                        date_obj = pd.to_datetime(row['Date'])
                    
                    date = date_obj.strftime('%d/%m/%Y')
                except Exception as e:
                    self.logger.error(f"Erreur conversion date: {e}")
                    date = ""  # Valeur par défaut en cas d'erreur

                # date = str(row['Date'].strftime('%d/%m/%Y'))
                br = str(row['BR'])
                nom = str(row.get('Nom', ''))
                resultat = self.traiter_fournisseur(url, code, factureFrs, dff, date, br, nom)

                # Récupérer le numéro de pièce (numero_FF)
                try:
                    numero_FF_input = self.get_input_by_label("Numéro pièce")
                    numero_FF = numero_FF_input.get_attribute("value") if numero_FF_input else ""
                    resultat['numero_FF'] = numero_FF
                    self.logger.info(f"📋 Numéro FF: {numero_FF}")
                except Exception as e:
                    resultat['numero_FF'] = ""
                    self.logger.warning(f"⚠️ Impossible de récupérer le numéro FF: {e}")

                # Mettre à jour les compteurs
                if resultat.get('statut') == 'Succes':
                    self.factures_traitees += 1
                else:
                    self.factures_echec += 1

                self.add_result(resultat)
                self.save_report(incremental=True)

                time.sleep(2)

            # Bilan final
            self.add_result({
                'type': 'BILAN_FINAL',
                'statut': 'SUCCES' if self.factures_echec == 0 else 'PARTIEL',
                'factures_traitees': self.factures_traitees,
                'factures_echec': self.factures_echec,
                'message': f'{self.factures_traitees} facture(s) traité(s), {self.factures_echec} échec(s)'
            })

            # Sauvegarder le rapport final
            self.save_report()

            # Envoyer les résultats vers n8n
            self.send_results_to_web(email_f)

            self.logger.info("="*80)
            self.logger.info("🎉 PROCESSUS TERMINÉ")
            self.logger.info(f"✅ {self.factures_traitees} facture(s) traité(s)")
            self.logger.info(f"❌ {self.factures_echec} facture(s) en échec")
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
            try:
                s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
                s_page_close.click()
                time.sleep(2)
            except:
                pass
            finally:
                self.wait_for_spinner_to_disappear(driver, 600000)
                self.disconnect_sage()
    
    def selection_recieption(self, codeReception):
        """
        Sélectionne une réception dans la liste (coche la checkbox)
        et gère la popup de confirmation
        
        Args:
            codeReception: Code BR (ex: "BR189847")
        
        Returns:
            True si succès, False sinon
        """
        driver = self.driver_manager.driver

        try:
            self.logger.info(f"🔍 Recherche de la réception: {codeReception}")
            
            # 1. Cliquer sur "Sélection réceptions" pour ouvrir la section
            reception_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[@title='Sélection réceptions']"))
            )
            reception_btn.click()
            self.logger.info("✅ Section 'Sélection réceptions' ouverte")
            time.sleep(1)
            
            # 2. Attendre que le tableau soit chargé
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "s-grid-table-body"))
            )
            
            # 3. Trouver TOUTES les lignes du tableau (visibles et cachées)
            all_rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row.s-grid-navig-row")
            self.logger.info(f"📊 {len(all_rows)} lignes trouvées dans le tableau")
            
            # 4. Chercher la ligne contenant le code de réception
            target_row = None
            for row in all_rows:
                try:
                    # Chercher le texte dans la ligne
                    desc_div = row.find_element(By.CSS_SELECTOR, ".s-tree-node-desc-value")
                    text = desc_div.text.strip()
                    
                    # Vérifier si c'est la bonne réception (commence par le code BR)
                    if text.startswith(codeReception):
                        target_row = row
                        self.logger.info(f"✅ Réception trouvée: {text}")
                        break
                except:
                    continue
            
            if not target_row:
                self.logger.error(f"❌ Réception {codeReception} non trouvée dans la liste")
                return False
            
            # 5. Vérifier si la ligne est visible (pas display: none)
            style = target_row.get_attribute("style") or ""
            is_hidden = "display: none" in style or "display:none" in style
            
            if is_hidden:
                self.logger.warning(f"⚠️ La réception {codeReception} est cachée, tentative d'expansion...")
                # Trouver le bouton d'expansion (parent picker)
                try:
                    # Chercher la ligne parent (celle qui contient le picker)
                    parent_rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row.s-grid-navig-row")
                    for i, pr in enumerate(parent_rows):
                        # Si la ligne suivante est notre target, ce parent contient le picker
                        if i + 1 < len(parent_rows) and parent_rows[i + 1] == target_row:
                            picker = pr.find_element(By.CSS_SELECTOR, ".s-tree-node-picker")
                            if picker.is_displayed():
                                picker.click()
                                self.logger.info("✅ Ligne expandée")
                                time.sleep(0.5)
                                break
                except Exception as e:
                    self.logger.warning(f"⚠️ Impossible d'expander: {e}")
            
            # 6. Trouver la checkbox dans cette ligne
            try:
                checkbox = target_row.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                checkbox_id = checkbox.get_attribute("id")
                
                # 7. Vérifier si déjà cochée
                if checkbox.is_selected():
                    self.logger.info(f"ℹ️ Réception {codeReception} déjà sélectionnée")
                else:
                    # 8. Cocher la checkbox
                    # Méthode 1: Cliquer sur le label
                    try:
                        label = target_row.find_element(By.CSS_SELECTOR, f"label[for='{checkbox_id}']")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label)
                        time.sleep(0.3)
                        label.click()
                        self.logger.info(f"✅ Checkbox cochée via label pour {codeReception}")
                    except:
                        # Méthode 2: Cliquer directement sur la checkbox
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                        time.sleep(0.3)
                        driver.execute_script("arguments[0].click();", checkbox)
                        self.logger.info(f"✅ Checkbox cochée via JavaScript pour {codeReception}")
                    
                    # # 9. Vérifier que c'est bien coché
                    # time.sleep(0.5)
                    # if not checkbox.is_selected():
                    #     self.logger.warning(f"⚠️ La checkbox n'est pas cochée après le clic")
                    #     return False
                
                # 10. Gérer la popup "Voulez-vous remplacer les données..."
                time.sleep(1)
                try:
                    # Chercher la popup
                    popup = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".s_alertbox_content"))
                    )
                    
                    # Vérifier que c'est bien la bonne popup
                    popup_text = popup.find_element(By.CSS_SELECTOR, ".s_alertbox_msg").text
                    
                    if "remplacer les données" in popup_text or "document d'origine" in popup_text:
                        self.logger.info("📋 Popup de confirmation détectée")
                        
                        # Cliquer sur "Oui"
                        oui_btn = popup.find_element(By.XPATH, "//a[@aria-label='Oui']")
                        oui_btn.click()
                        self.logger.info("✅ Cliqué sur 'Oui' dans la popup")
                        time.sleep(1)
                    else:
                        self.logger.warning(f"⚠️ Popup inattendue: {popup_text}")
                        
                except Exception as e:
                    # Pas de popup ou déjà fermée
                    self.logger.info("ℹ️ Pas de popup de confirmation (ou déjà gérée)")
                
                self.logger.info(f"✅ Réception {codeReception} sélectionnée avec succès")
                return True
                    
            except Exception as e:
                self.logger.error(f"❌ Erreur lors du cochage de la checkbox: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la sélection de la réception {codeReception}: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def saisi_information(self, typeF, codeFournisseur, factureFournisseur, DFF, Date, codeReception, nom=""):
        self.logger.info(f"🔍 Saisir: Tier={codeFournisseur}, Reception={codeReception}, Facture={factureFournisseur}, Date = {Date}")
        driver = self.driver_manager.driver

        try:
            wait = WebDriverWait(driver, 2000000)
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a.s_page_action_add")))
            cree = driver.find_element(By.CSS_SELECTOR, "a.s_page_action_add")
            
            cree.click()
            time.sleep(2)
            self.wait_for_spinner_to_disappear(driver, 90000)

            # cf = driver.find_element(By.ID, "2-73-input")
            cf = self.get_input_by_label("Type facture")
            cf.click()
            time.sleep(0.5)
            cf.clear()
            cf.send_keys(typeF)
            cf.send_keys(Keys.TAB)
            time.sleep(1)

            # cf2 = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "2-81-input")))
            cf2 = self.get_input_by_label("Fournisseur")
            cf2.click()
            time.sleep(0.5)
            cf2.clear()
            cf2.send_keys(codeFournisseur)
            cf2.send_keys(Keys.TAB)
            time.sleep(2)


            # AncienCode_input = driver.find_element(By.ID, "2-85-input")
            AncienCode_input = self.get_input_by_label("Ancien Code")
            AncienCode_input.click()
            time.sleep(0.5)
            AncienCode_input.clear()
            AncienCode_input.send_keys(factureFournisseur)
            AncienCode_input.send_keys(Keys.TAB)
            time.sleep(1)


            # DFF_input = driver.find_element(By.ID, "2-87-input")
            DFF_input = self.get_input_by_label("N°Dépôt")
            DFF_input.click()
            time.sleep(0.5)
            DFF_input.clear()
            DFF_input.send_keys(DFF)
            DFF_input.send_keys(Keys.TAB)
            time.sleep(1)
            
            # self.gere_popup_info()

            # Selection la Reception
            if not self.selection_recieption(codeReception):
                return False
            # Sleep pour laisser le temps de la sélection
            time.sleep(2)


            # Saisir le Montant HT
            # HT_input = driver.find_element(By.ID, "2-183-input")
            HT_input = self.get_input_by_label("HT calculé")
            ht_value= HT_input.get_attribute('value')  # Juste pour s'assurer que l'élément est chargé
            time.sleep(1)

            # HT_saisi_input = driver.find_element(By.ID, "2-182-input")
            HT_saisi_input = self.get_input_by_label("HT saisi")
            HT_saisi_input.click()
            time.sleep(0.5)
            HT_saisi_input.clear()
            HT_saisi_input.send_keys(ht_value)
            HT_saisi_input.send_keys(Keys.TAB)
            time.sleep(1)


            # Saisir la Taxe
            # Taxe = driver.find_element(By.ID, "2-190-input")
            Taxe = self.get_input_by_label("Ecart taxes")
            taxe_value= Taxe.get_attribute('value')  # Juste pour s'assurer que l'élément est chargé
            # Supprimer uniquement le '-' au début si présent
            if taxe_value and taxe_value.startswith('-'):
                taxe_value = taxe_value.lstrip('-')

            time.sleep(1)

            # Taxe_saisi_input = driver.find_element(By.ID, "2-189-input")
            Taxe_saisi_input = self.get_input_by_label("Total taxes saisi")
            Taxe_saisi_input.click()
            time.sleep(0.5)
            Taxe_saisi_input.clear()
            Taxe_saisi_input.send_keys(taxe_value)
            Taxe_saisi_input.send_keys(Keys.TAB)
            time.sleep(1)

            # Saisir la Date
            # date_input = driver.find_element(By.ID, "2-98-input")
            date_input = self.get_input_by_label("Date fact.fou")
            date_input.click()
            time.sleep(0.5)
            date_input.clear()
            date_input.send_keys(Date)
            date_input.send_keys(Keys.TAB)
            time.sleep(1)

            # factureFrs_input = driver.find_element(By.ID, "2-99-input")
            factureFrs_input = self.get_input_by_label("No fact.fou")
            factureFrs_input.click()
            time.sleep(0.5)
            factureFrs_input.clear()
            factureFrs_input.send_keys(factureFournisseur)
            factureFrs_input.send_keys(Keys.TAB)
            time.sleep(1)

            # referenceIntern_input = driver.find_element(By.ID, "2-111-input")
            referenceIntern_input = self.get_input_by_label("Référence interne")
            referenceIntern_input.click()
            time.sleep(0.5)
            referenceIntern_input.clear()
            referenceIntern_input.send_keys(factureFournisseur)
            referenceIntern_input.send_keys(Keys.TAB)
            time.sleep(1)

            self.logger.info(f"✅ Informations saisies pour le fournisseur {codeFournisseur} ({nom})")
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur recherche fournisseur: {e}")
            return False

    def clique_enregistrer(self):
        driver = self.driver_manager.driver

        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_check")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()
            time.sleep(5)
            self.wait_for_spinner_to_disappear(driver, 900000000)

            self.logger.info("✅ Enregistrement clique")
            confirmation_msg = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "s_alertbox_title"))
            )
            # confirmation_msg_text = confirmation_msg.text
            
            # if "Avertissement" in confirmation_msg_text :
            #     try:
            #         # Cliquer sur "Oui"
            #         oui_button = driver.find_element(By.XPATH, "//a[@aria-label='OK']")
            #         oui_button.click()
            #         self.logger.info("✅ Avertissement Confirmation abandon cliquée")
            #         time.sleep(1)
            #     except:
            #         # Pas de popup ou autre type de popup
            #         pass
            
            # if "Mibilisation" in confirmation_msg_text:
            #     try:
            #         header = driver.find_element(By.CLASS_NAME, "s_alertbox_header")
            #         close_button = header.find_element(By.CLASS_NAME, "s_modal_close")
            #         close_button.click()

            #         self.logger.error(f"Mobilisation : {confirmation_msg_text}")
            #     except: 
            #         pass
            
            try:
                # Fermer la popup de confirmation
                header = driver.find_element(By.CLASS_NAME, "s_alertbox_header")
                close_button = header.find_element(By.CLASS_NAME, "s_modal_close")
                close_button.click()

                self.logger.info(f"✅ Popup de confirmation fermée {confirmation_msg.text}")
                time.sleep(1)
            except:
                pass
            self.logger.info(f"✅ Enregistrement reussi: {confirmation_msg.text}")
            time.sleep(3)
        except Exception as e:
            self.logger.error(f"❌ Erreur enregistrement: {e}")
            driver.save_screenshot("ScreenShot/error_enregistrement.png")

    def traiter_fournisseur(self, url, codeFournisseur, factureFournisseur, DFF, Date, codeReception, nom=""):
        """Traite un fournisseur avec lettrage Facture <-> N-Avis"""
        self.logger.info("="*80)
        self.logger.info(f"🏢 TRAITEMENT FOURNISSEUR : {nom if nom else codeFournisseur}")
        self.logger.info(f" DFF: {DFF} | Date: {Date} | Reception: {codeReception}")
        self.logger.info("="*80)
        
        resultat = {
            'codeFournisseur': codeFournisseur,
            'factureFournisseur': factureFournisseur,
            'DFF': DFF,
            'Date': Date,
            'codeReception': codeReception,
            'nom': nom,
            'statut': 'Echec',
            'ecritures_trouvees': 0,
            'facturation_effectue': False,
            'message': ''
        }
        
        try:
            if not self.saisi_information(typeF="FAF", codeFournisseur=codeFournisseur, factureFournisseur=factureFournisseur, DFF=DFF, Date=Date, codeReception=codeReception, nom=nom):
                self.logger.warning("⚠️ Erreur recherche, tentative d'actualisation...")
                
                if self.sage_connector.refresh_with_popup_handling():
                    if not self.saisi_information(typeF="FAF", codeFournisseur=codeFournisseur, factureFournisseur=factureFournisseur, DFF=DFF, Date=Date, codeReception=codeReception, nom=nom):
                        resultat['message'] = 'Erreur recherche après actualisation'
                        return resultat
                else:
                    resultat['message'] = 'Erreur recherche, actualisation échouée'
                    return resultat
            
            time.sleep(2)
            self.clique_enregistrer()
            
            self.close_module()

            # Marquer comme succès
            resultat['statut'] = 'Succes'
            resultat['facturation_effectue'] = True
            resultat['message'] = 'Facturation effectuée avec succès'

        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f"❌ Erreur traitement fournisseur: {e}")

        return resultat
    