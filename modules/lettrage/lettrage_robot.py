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
from utils.excel_handler import ExcelHandler


class LettrageRobot(BaseRobot):
    """Robot pour le lettrage automatique des fournisseurs"""
    
    def __init__(self, headless: bool = False):
        """
        Initialiser le robot lettrage
        
        Args:
            headless: Mode sans interface
        """
        super().__init__('lettrage')
        self.excel_handler = ExcelHandler()
        # self.driver_manager.headless = headless
        
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
            required_columns=['Compte', 'Code', 'Facture', 'N-Avis']
        )
        
        self.logger.info(f"📊 {len(df)} lignes à traiter")
        
        # Connexion Sage
        self.connect_sage()
        self.navigate_to_module(url)
        
        # Traiter chaque ligne
        for idx, row in df.iterrows():
            self.logger.info(f"\n{'='*80}")
            self.logger.info(f"📌 LIGNE {idx+1}/{len(df)}")
            self.logger.info(f"{'='*80}")
            
            result = self.traiter_fournisseur(
                compte=str(row['Compte']),
                code=str(row['Code']),
                facture=str(row['Facture']),
                n_avis=str(row['N-Avis']),
                nom=str(row.get('Nom', ''))
            )
            
            self.add_result(result)
            self.save_report(incremental=True)
            
            time.sleep(2)
    
    def traiter_fournisseur(self, compte: str, code: str, facture: str, 
                           n_avis: str, nom: str = "") -> Dict[str, Any]:
        """
        Traiter un fournisseur avec lettrage Facture <-> N-Avis
        
        Returns:
            Dictionnaire avec résultats
        """
        self.logger.info(f"🏢 Fournisseur: {nom or code}")
        self.logger.info(f"   Compte: {compte} | Code: {code}")
        self.logger.info(f"   Facture: {facture} | N-Avis: {n_avis}")
        
        resultat = {
            'compte': compte,
            'code': code,
            'nom': nom,
            'facture': facture,
            'n_avis': n_avis,
            'statut': 'Echec',
            'ecritures_trouvees': 0,
            'lettrage_effectue': False,
            'message': ''
        }
        
        try:
            # Rechercher le fournisseur
            if not self.rechercher_fournisseur(compte, code):
                # Réessayer avec actualisation
                if self.sage_connector.refresh_with_popup_handling():
                    if not self.rechercher_fournisseur(compte, code):
                        resultat['message'] = 'Erreur recherche après actualisation'
                        return resultat
                else:
                    resultat['message'] = 'Actualisation échouée'
                    return resultat
            
            # Extraire les écritures
            ecritures = self.extraire_ecritures()
            resultat['ecritures_trouvees'] = len(ecritures)
            
            if not ecritures:
                resultat['message'] = 'Aucune ecriture trouvee'
                return resultat
            
            # Afficher les écritures
            self.logger.info("\n📋 ECRITURES EXTRAITES:")
            for e in ecritures:
                lettre_info = f"[Lettre: {e['lettre']}]" if e['lettre'] else ""
                self.logger.info(f"L{e['index']:>2} | {e['date']} | Numero: {e['numero']:>15} | D:{e['debit_str']:>12} C:{e['credit_str']:>12} {lettre_info}")
            
            # Trouver les correspondances
            corresp = self.trouver_correspondances_par_numero(ecritures, facture, n_avis)
            
            if not corresp:
                resultat['message'] = 'Facture ou N-Avis non trouvé ou déjà lettré'
                resultat['statut'] = 'Non lettré'
                return resultat
            
            # Effectuer le lettrage
            c = corresp[0]
            self.logger.info(f"\n🔄 Lettrage: {c['description']}")
            nb = self.selectionner_ecritures(c['checkbox_ids'])
            
            if nb == len(c['checkbox_ids']):
                time.sleep(1)
                if self.cliquer_lettrage():
                    resultat['lettrage_effectue'] = True
                    resultat['statut'] = 'Succes'
                    resultat['message'] = f"Lettrage effectué: {c['description']}"
                    self.logger.info("✅ Lettrage réussi")
                else:
                    resultat['message'] = 'Erreur lors du clic sur Lettrage'
                time.sleep(2)
            else:
                resultat['message'] = 'Erreur lors de la sélection des écritures'
            
        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f"❌ Erreur traitement fournisseur: {e}")
        
        return resultat
    
    def rechercher_fournisseur(self, compte: str, code: str) -> bool:
        """Rechercher un fournisseur dans Sage"""
        try:
            driver = self.driver_manager.driver
            
            self.logger.info(f"🔍 Recherche: Compte={compte}, Code={code}")
            
            # Remplir compte
            compte_field = driver.find_element(By.ID, "2-60-input")
            compte_field.click()
            time.sleep(0.5)
            compte_field.clear()
            compte_field.send_keys(compte)
            compte_field.send_keys(Keys.TAB)
            time.sleep(1)
            
            # Remplir code
            code_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "2-62-input"))
            )
            code_field.click()
            time.sleep(0.5)
            code_field.clear()
            code_field.send_keys(code)
            code_field.send_keys(Keys.TAB)
            time.sleep(1)
            
            # Cliquer recherche
            search_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[@title='Recherche']"))
            )
            search_btn.click()
            time.sleep(3)
            
            # Vérifier résultats
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-grid-fixed-table-body"))
            )
            
            self.logger.info("✅ Résultats affichés")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur recherche: {e}")
            return False
    
    def extraire_ecritures(self):
        """Extrait TOUTES les écritures (lettrées ou non)"""
        ecritures = []
        driver = self.driver_manager.driver
        
        rows_fixed = driver.find_elements(By.CSS_SELECTOR, ".s-grid-fixed-table-body tr.s-grid-row")
        rows_scroll = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
        
        self.logger.info(f"📊 Lignes totales: {len(rows_fixed)}")
        
        for i in range(len(rows_fixed)):
            try:
                cb = rows_fixed[i].find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                if_inputs = rows_fixed[i].find_elements(By.CSS_SELECTOR, ".s-inplace-input")
                is_inputs = rows_scroll[i].find_elements(By.CSS_SELECTOR, ".s-inplace-input")
                
                lettre = if_inputs[3].get_attribute('value') if len(if_inputs) > 3 else ''
                
                def parse_montant(s):
                    if not s or not s.strip():
                        return 0.0
                    try:
                        return float(s.replace(' ', '').replace(',', '.'))
                    except:
                        return 0.0
                
                e = {
                    'index': i + 1,
                    'checkbox_id': cb.get_attribute('id'),
                    'date': if_inputs[0].get_attribute('value') if len(if_inputs) > 0 else '',
                    'type': if_inputs[1].get_attribute('value') if len(if_inputs) > 1 else '',
                    'numero': if_inputs[2].get_attribute('value') if len(if_inputs) > 2 else '',
                    'lettre': lettre,
                    'debit_str': is_inputs[0].get_attribute('value') if len(is_inputs) > 0 else '',
                    'credit_str': is_inputs[1].get_attribute('value') if len(is_inputs) > 1 else '',
                    'etat': is_inputs[2].get_attribute('value') if len(is_inputs) > 2 else '',
                    'libelle': is_inputs[3].get_attribute('value') if len(is_inputs) > 3 else '',
                }
                e['debit'] = parse_montant(e['debit_str'])
                e['credit'] = parse_montant(e['credit_str'])
                ecritures.append(e)
                
            except Exception as ex:
                self.logger.warning(f"⚠️ Erreur ligne {i+1}: {ex}")
        
        self.logger.info(f"✅ {len(ecritures)} écritures extraites")
        return ecritures
    
    def trouver_correspondances_par_numero(self, ecritures, facture, n_avis):
        """Trouve les écritures qui correspondent à la facture et au N-Avis"""
        correspondances = []
        
        self.logger.info(f"🔍 Recherche de Facture: '{facture}' et N-Avis: '{n_avis}'")
        
        # Chercher la facture
        ligne_facture = None
        for e in ecritures:
            if e['numero'].strip().upper() == str(facture).strip().upper():
                ligne_facture = e
                self.logger.info(f"✅ Facture trouvée: Ligne {e['index']} | Numero: {e['numero']} | D:{e['debit_str']} C:{e['credit_str']}")
                break
        
        # Chercher le N-Avis
        ligne_avis = None
        for e in ecritures:
            if e['numero'].strip().upper() == str(n_avis).strip().upper():
                ligne_avis = e
                self.logger.info(f"✅ N-Avis trouvé: Ligne {e['index']} | Numero: {e['numero']} | D:{e['debit_str']} C:{e['credit_str']}")
                break
        
        if ligne_facture and ligne_avis:
            # Vérifier qu'ils ne sont pas déjà lettrés
            if ligne_facture['lettre'] and ligne_facture['lettre'].strip():
                self.logger.warning(f"⚠️ Facture {facture} déjà lettrée (code: {ligne_facture['lettre']})")
                return []
            
            if ligne_avis['lettre'] and ligne_avis['lettre'].strip():
                self.logger.warning(f"⚠️ N-Avis {n_avis} déjà lettré (code: {ligne_avis['lettre']})")
                return []
            
            correspondances.append({
                'indices': [ligne_facture['index'], ligne_avis['index']],
                'checkbox_ids': [ligne_facture['checkbox_id'], ligne_avis['checkbox_id']],
                'facture': facture,
                'n_avis': n_avis,
                'description': f"Facture {facture} (L{ligne_facture['index']}) ↔ N-Avis {n_avis} (L{ligne_avis['index']})"
            })
            
            self.logger.info(f"✅ Correspondance créée: {correspondances[0]['description']}")
        else:
            if not ligne_facture:
                self.logger.warning(f"❌ Facture '{facture}' NON TROUVÉE")
            if not ligne_avis:
                self.logger.warning(f"❌ N-Avis '{n_avis}' NON TROUVÉ")
        
        return correspondances
    
    def selectionner_ecritures(self, checkbox_ids):
        """Sélectionner les écritures à lettrer"""
        driver = self.driver_manager.driver
        ok = 0
        
        for cb_id in checkbox_ids:
            try:
                cb = driver.find_element(By.ID, cb_id)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cb)
                time.sleep(0.5)
                
                if cb.is_selected():
                    self.logger.info(f"⏭️ Déjà sélectionné: {cb_id}")
                    ok += 1
                    continue
                
                try:
                    cb.click()
                    self.logger.info(f"✅ Coché (normal): {cb_id}")
                    ok += 1
                except:
                    driver.execute_script("arguments[0].click();", cb)
                    self.logger.info(f"✅ Coché (JS): {cb_id}")
                    ok += 1
                
                time.sleep(0.3)
            except Exception as e:
                self.logger.warning(f"⚠️ Impossible {cb_id}: {e}")
        
        self.logger.info(f"📊 TOTAL: {ok}/{len(checkbox_ids)} sélectionné(s)")
        return ok
    
    def cliquer_lettrage(self):
        """Cliquer sur le bouton Lettrage"""
        driver = self.driver_manager.driver
        
        try:
            selectors = [
                "//a[@title='Lettrage' and contains(@class, 's-mn-prefer-link')]",
                "//a[@title='Lettrage']",
                "//a[contains(text(), 'Lettrage')]"
            ]
            
            btn = None
            for sel in selectors:
                try:
                    btn = driver.find_element(By.XPATH, sel)
                    self.logger.info(f"✅ Bouton Lettrage trouvé avec: {sel}")
                    break
                except:
                    continue
            
            if btn:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.5)
                
                try:
                    btn.click()
                    self.logger.info("✅ Clic sur Lettrage (normal)")
                except:
                    driver.execute_script("arguments[0].click();", btn)
                    self.logger.info("✅ Clic sur Lettrage (JavaScript)")
                
                time.sleep(2)
                
                # Gérer popup de confirmation
                try:
                    confirm_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'OK')] | //button[contains(text(), 'Confirmer')] | //button[contains(text(), 'Valider')]"))
                    )
                    confirm_btn.click()
                    self.logger.info("✅ Confirmation cliquée")
                except:
                    self.logger.info("ℹ️ Pas de popup de confirmation")
                
                time.sleep(1)
                self.logger.info("✅ Lettrage validé")
                return True
            else:
                self.logger.error("❌ Bouton Lettrage non trouvé")
                self.driver_manager.take_screenshot("error_bouton_lettrage.png")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lettrage: {e}")
            self.driver_manager.take_screenshot("error_lettrage_exception.png")
            return False
