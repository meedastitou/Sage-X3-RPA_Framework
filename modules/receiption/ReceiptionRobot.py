# -*- coding: utf-8 -*-
"""
Module Receiption - Robot pour les réceptions d'achat Sage X3
Regroupe par Fournisseur → BC → Articles
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


class ReceiptionRobot(BaseRobot, WebResultMixin):
    """Robot pour la gestion automatique des réceptions d'achat avec regroupement"""
    
    def __init__(self, headless: bool = False):
        """Initialiser le robot réception"""
        BaseRobot.__init__(self, 'receiption')
        WebResultMixin.__init__(self)
        
        self.excel_handler = ExcelHandler()
        self.driver_manager.headless = headless
        
        # URL du module réceptions d'achat
        self.url_receiption = "http://192.168.1.252:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FPREPROD%2F%24sessions%3Ff%3DGESPTH2%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%2765059cf7-11e9-4b40-bac9-66ef183fb4e1~ep~%2764a56978-56ab-46f1-8d83-ed18f7fa6484~appConn~())"
        
        # Compteurs
        self.fournisseurs_traites = 0
        self.fournisseurs_echec = 0
        self.total_articles = 0
        
        self.logger.info(f"🤖 Robot Réception initialisé (REGROUPEMENT PAR FOURNISSEUR)")
    
    def execute(self, excel_file: str, url: str = None):
        """
        Exécuter le traitement des réceptions
        
        Args:
            excel_file: Chemin du fichier Excel
            url: URL du module (optionnel)
        """
        email_f=""
        try:
            # 1. LIRE ET VALIDER L'EXCEL
            df = self._lire_et_valider_excel(excel_file)
            email_f = df.iloc[0]['email_expediteur']
            
            # 2. REGROUPER PAR FOURNISSEUR → BC → ARTICLES
            structure = self._regrouper_donnees(df)
            
            # 3. AFFICHER RÉSUMÉ
            self._afficher_resume(structure)
            
            # 4. CONNEXION SAGE
            self.connect_sage()
            
            # 5. NAVIGUER VERS MODULE
            self.navigate_to_module(self.url_receiption)
            time.sleep(3)
            
            # 6. TRAITER CHAQUE FOURNISSEUR
            for code_frs, frs_data in structure.items():
                self.logger.info(f"{'='*80}")
                self.logger.info(f"🏢 FOURNISSEUR: {code_frs}")
                self.logger.info(f"{'='*80}")
                
                resultat_frs = self._traiter_fournisseur(code_frs, frs_data)
                self.add_result(resultat_frs)
                
                if resultat_frs['statut'] == 'Succes':
                    self.fournisseurs_traites += 1
                else:
                    self.fournisseurs_echec += 1
                    self.logger.warning(f"⚠️ Échec fournisseur {code_frs}, mais on continue...")
            
            # # 7. BILAN FINAL
            # self.add_result({
            #     'type': 'BILAN_FINAL',
            #     'statut': 'SUCCES' if self.fournisseurs_echec == 0 else 'PARTIEL',
            #     'fournisseurs_traites': self.fournisseurs_traites,
            #     'fournisseurs_echec': self.fournisseurs_echec,
            #     'total_articles': self.total_articles,
            #     'message': f'{self.fournisseurs_traites} fournisseur(s) traité(s), {self.total_articles} article(s)'
            # })
            
            # # 8. SAUVEGARDER RAPPORT
            # self.save_report()
            
            # # 9. ENVOYER RÉSULTATS WEB
            # self.send_results_to_web()
            
            # self.logger.info("\n" + "="*80)
            # self.logger.info("🎉 PROCESSUS TERMINÉ")
            # self.logger.info(f"✅ {self.fournisseurs_traites} fournisseur(s) traité(s)")
            # self.logger.info(f"❌ {self.fournisseurs_echec} fournisseur(s) en échec")
            # self.logger.info(f"📦 {self.total_articles} article(s) traité(s)")
            # self.logger.info("="*80)
            
        except Exception as e:
            self.logger.error(f"\n❌ ERREUR CRITIQUE: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            self.add_result({
                'type': 'ERREUR',
                'statut': 'ECHEC',
                'message': str(e)
            })
            
            self.save_report()
            self.send_results_to_web(email_f)
    
    def _lire_et_valider_excel(self, excel_file: str) -> pd.DataFrame:
        """Lire et valider le fichier Excel"""
        self.logger.info("="*80)
        self.logger.info("📖 LECTURE EXCEL")
        self.logger.info("="*80)
        
        colonnes_requises = [
            'CodeFrs',
            'BLFrs', 
            'DateBC',
            'N_BC',
            'CodeArticle',
            'Quantite',
            'N_B_transport',
            'Matricule',
            'Poids',
            'Marque'
        ]
        
        df = self.excel_handler.read_excel(excel_file, required_columns=colonnes_requises)
        
        self.logger.info(f"✅ {len(df)} ligne(s) lues")
        
        # Validation des colonnes importantes
        lignes_invalides = []
        for idx, row in df.iterrows():
            colonnes_vides = []
            for col in ['CodeFrs','BLFrs', 'DateBC', 'N_BC', 'CodeArticle', 'Quantite', 'Poids', 'Marque']:
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
        Regrouper par Fournisseur → BC → Articles
        
        Structure:
        {
            'T3775': {
                'bl_frs': '2025-23',
                'date_bc': '01/01/2026',
                'bons_commande': {
                    'BC167784': {
                        'articles': [
                            {
                                'code': 'A13254',
                                'quantite': '60',
                                'n_b_transport': '265225',
                                'matricule': '23-5656-a',
                                'poids': '52',
                                'marque': 'dds'
                            },
                            ...
                        ]
                    }
                }
            }
        }
        """
        self.logger.info("="*80)
        self.logger.info("🔄 REGROUPEMENT DES DONNÉES")
        self.logger.info("="*80)
        
        structure = {}
        
        for _, row in df.iterrows():
            code_frs = str(row['CodeFrs'])
            bl_frs = str(row['BLFrs'])
            date_bc = self._format_date(row['DateBC'])
            n_bc = str(row['N_BC'])
            
            # Initialiser fournisseur si nouveau
            if code_frs not in structure:
                structure[code_frs] = {
                    'bl_frs': bl_frs,
                    'date_bc': date_bc,
                    'bons_commande': {}
                }
            
            # Initialiser BC si nouveau
            if n_bc not in structure[code_frs]['bons_commande']:
                structure[code_frs]['bons_commande'][n_bc] = {
                    'articles': []
                }
            
            # Ajouter l'article
            article = {
                'code': str(row['CodeArticle']).strip(),
                'quantite': str(row['Quantite']),
                'n_b_transport': str(row['N_B_transport']) if not pd.isna(row['N_B_transport']) else '',
                'matricule': str(row['Matricule']) if not pd.isna(row['Matricule']) else '',
                'poids': str(row['Poids']) if not pd.isna(row['Poids']) else '',
                'marque': str(row['Marque']) if not pd.isna(row['Marque']) else ''
            }
            
            structure[code_frs]['bons_commande'][n_bc]['articles'].append(article)
        
        return structure
    
    def _format_date(self, date_value) -> str:
        """Formater la date au format JJ/MM/AAAA"""
        if isinstance(date_value, pd.Timestamp):
            return date_value.strftime('%d/%m/%Y')
        elif isinstance(date_value, datetime):
            return date_value.strftime('%d/%m/%Y')
        else:
            date_str = str(date_value)
            # Si format "01/01/2026"
            if '/' in date_str:
                return date_str
            # Si format "2026-01-01"
            if '-' in date_str and len(date_str) == 10:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    return date_obj.strftime('%d/%m/%Y')
                except:
                    pass
            return date_str
    
    def _afficher_resume(self, structure: Dict):
        """Afficher un résumé de la structure"""
        self.logger.info("="*80)
        self.logger.info("📊 RÉSUMÉ DU TRAITEMENT")
        self.logger.info("="*80)
        
        self.logger.info(f"🏢 {len(structure)} Fournisseur(s):")
        
        for code_frs, frs_data in structure.items():
            self.logger.info(f"   📦 Fournisseur: {code_frs}")
            self.logger.info(f"      BL: {frs_data['bl_frs']}")
            self.logger.info(f"      Date BC: {frs_data['date_bc']}")
            self.logger.info(f"      {len(frs_data['bons_commande'])} Bon(s) de Commande:")
            
            for n_bc, bc_data in frs_data['bons_commande'].items():
                nb_articles = len(bc_data['articles'])
                self.logger.info(f"         • {n_bc}: {nb_articles} article(s)")
                for art in bc_data['articles']:
                    self.logger.info(f"            - {art['code']}: Qté {art['quantite']}")
        
        self.logger.info("="*80)
    
    def _traiter_fournisseur(self, code_frs: str, frs_data: Dict) -> Dict[str, Any]:
        """Traiter un fournisseur (tous ses BCs)"""
        resultat = {
            'type': 'Fournisseur',
            'code_frs': code_frs,
            'statut': 'Echec',
            'bcs_traites': 0,
            'bcs_echec': 0,
            'message': ''
        }
        
        try:
            # Traiter chaque BC du fournisseur
            for n_bc, bc_data in frs_data['bons_commande'].items():
                self.logger.info(f"{'─'*80}")
                self.logger.info(f"📋 Bon de Commande: {n_bc}")
                self.logger.info(f"{'─'*80}")
                
                resultat_bc = self._traiter_bon_commande(
                    code_frs=code_frs,
                    n_bc=n_bc,
                    bl_frs=frs_data['bl_frs'],
                    date_bc=frs_data['date_bc'],
                    articles=bc_data['articles']
                )
                
                self.add_result(resultat_bc)
                
                if resultat_bc['statut'] == 'Succes':
                    resultat['bcs_traites'] += 1
                else:
                    resultat['bcs_echec'] += 1
            
            # Statut global fournisseur
            if resultat['bcs_echec'] == 0:
                resultat['statut'] = 'Succes'
                resultat['message'] = f'{resultat["bcs_traites"]} BC traité(s)'
            else:
                resultat['message'] = f'{resultat["bcs_traites"]} BC OK, {resultat["bcs_echec"]} BC échec'
            
            self.logger.info(f"✅ Fournisseur {code_frs}: {resultat['message']}")
            
        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f"❌ Erreur fournisseur {code_frs}: {e}")
        finally:
            self.logger.info(f"\n✅ Articles traités: {self.articles_traites}, Échecs: {self.articles_echec}")
            driver = self.driver_manager.driver

            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

            s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
            s_page_close.click()
            time.sleep(20)
        return resultat
    
    def _traiter_bon_commande(self, code_frs: str, n_bc: str, bl_frs: str, 
                              date_bc: str, articles: List[Dict]) -> Dict[str, Any]:
        """Traiter un bon de commande avec ses articles"""
        resultat = {
            'type': 'BonCommande',
            'n_bc': n_bc,
            'code_frs': code_frs,
            'statut': 'Echec',
            'articles_traites': 0,
            'message': ''
        }
        
        driver = self.driver_manager.driver
        
        try:
            # 0. CRÉER LA RÉCEPTION
            if self._cree_reception():
                self.logger.info(f"✅ Réception créée pour BC {n_bc}")
            else:
                resultat['message'] = 'Erreur création réception'
                return resultat
            

            # 1. REMPLIR LES CHAMPS HEADER
            self.logger.info("📝 Remplissage header...")
            # Fournisseur
            fournisseur = driver.find_element(By.ID, "3-75-input")  
            fournisseur.click()
            time.sleep(0.5)
            fournisseur.clear()
            fournisseur.send_keys(code_frs)
            fournisseur.send_keys(Keys.TAB)
            time.sleep(1)

            # driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            self._gere_popup_fournisseur()

            # Date BC
            date_input = driver.find_element(By.ID, "3-76-input")
            date_input.click()
            time.sleep(0.5)
            date_input.clear()
            date_input.send_keys(date_bc)
            date_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            
            # BL Fournisseur
            bl_input = driver.find_element(By.ID, "3-77-input")
            bl_input.click()
            time.sleep(0.5)
            bl_input.clear()
            bl_input.send_keys(bl_frs)
            bl_input.send_keys(Keys.TAB)
            time.sleep(0.5)
            
            self.logger.info("✅ Header rempli")
            
            # 2. SÉLECTIONNER LE BC
            self.logger.info(f"🔍 Sélection BC: {n_bc}")

            # if not self._selectionner_bc(n_bc):
            #     resultat['message'] = f'BC {n_bc} non trouvé'
            #     return resultat

            if not self._selectionner_articles_par_bc(n_bc, articles):
                resultat['message'] = f'Aucun article sélectionné pour BC {n_bc}'
                return resultat
            
            input("test")
            # 3. TRAITER CHAQUE ARTICLE
            for idx, article in enumerate(articles, 1):
                self.logger.info(f"   📦 Article {idx}/{len(articles)}: {article['code']}")
                
                if self._remplir_article_dans_ligne(article, idx):
                    resultat['articles_traites'] += 1
                    self.total_articles += 1
                    self.logger.info(f"   ✅ Article {article['code']} OK")
                else:
                    self.logger.warning(f"   ⚠️ Article {article['code']} échec")
                
                time.sleep(0.5)
            
            # 4. ENREGISTRER
            if self._enregistrer_reception():
                resultat['statut'] = 'Succes'
                resultat['message'] = f'{resultat["articles_traites"]}/{len(articles)} article(s) traité(s)'
                self.logger.info(f"✅ BC {n_bc} enregistré")
            else:
                resultat['message'] = 'Erreur enregistrement'
            
        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f"❌ Erreur BC {n_bc}: {e}")
        
        return resultat
    
    def _cree_reception(self) -> bool:
        """Cliquer sur le bouton 'Créer Réception'"""
        driver = self.driver_manager.driver
        
        try:
            creer_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "s_page_action_i.s_page_action_i_add"))
            )
            creer_btn.click()
            time.sleep(2)
        
            self.logger.info("✅ Nouvelle réception créée")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur création réception: {e}")
            return False

    def _selectionner_bc(self, n_bc: str) -> bool:
        """Sélectionner le BC dans la liste des réceptions"""
        driver = self.driver_manager.driver
        
        try:
            # Cliquer sur "Sélection réceptions" ou bouton similaire
            selection_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[@title='Sélection réceptions']"))
            )
            selection_btn.click()
            time.sleep(1)
            
            # Attendre le tableau
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "s-grid-table-body"))
            )
            
            # Chercher le BC
            rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
            
            for row in rows:
                try:
                    text = row.text
                    if n_bc in text:
                        checkbox = row.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                        checkbox_id = checkbox.get_attribute("id")
                        
                        if not checkbox.is_selected():
                            label = row.find_element(By.CSS_SELECTOR, f"label[for='{checkbox_id}']")
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label)
                            time.sleep(0.3)
                            label.click()
                            time.sleep(0.5)
                        
                        # Popup "Oui"
                        try:
                            oui_btn = driver.find_element(By.XPATH, "//a[@aria-label='Oui']")
                            oui_btn.click()
                            time.sleep(1)
                        except:
                            pass
                        
                        self.logger.info(f"✅ BC {n_bc} sélectionné")
                        return True
                except:
                    continue
            
            self.logger.error(f"❌ BC {n_bc} non trouvé")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Erreur sélection BC: {e}")
            return False

    def _selectionner_articles_par_bc(self, n_bc: str, articles: List[Dict]) -> bool:
        """
        Sélectionner les articles dans le tableau 'Sélection commandes'
        en s'assurant qu'ils appartiennent au bon BC
        
        Args:
            n_bc: Numéro du bon de commande (ex: 'BC167784')
            articles: Liste des articles à sélectionner [{'code': 'A13254', ...}, ...]
        
        Returns:
            True si au moins un article sélectionné, False sinon
        """
        driver = self.driver_manager.driver
        
        try:
            self.logger.info(f"🔍 Sélection articles pour BC: {n_bc}")
            
            # Attendre le tableau
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-grid-table-body"))
            )
            time.sleep(1)
            
            # Récupérer toutes les lignes
            rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
            
            # Structure hiérarchique : BC → Articles
            bc_trouve = False
            bc_ouvert = False
            articles_trouves = 0
            
            for row in rows:
                try:
                    # Vérifier si ligne visible
                    if row.get_attribute('style') and 'display: none' in row.get_attribute('style'):
                        continue
                    
                    # Récupérer le texte de la ligne
                    desc_div = row.find_element(By.CSS_SELECTOR, ".s-tree-node-desc-value")
                    ligne_text = desc_div.text.strip()
                    
                    # Détecter le niveau (BC parent ou Article enfant)
                    tree_node = row.find_element(By.CSS_SELECTOR, ".s-tree-node")
                    niveau = tree_node.get_attribute("aria-level")
                    
                    # NIVEAU 0 ou 1 = Ligne BC (parent)
                    if niveau in ['0', '1']:
                        # Vérifier si c'est notre BC
                        if n_bc in ligne_text:
                            bc_trouve = True
                            self.logger.info(f"✅ BC trouvé: {ligne_text}")
                            
                            # Vérifier si le BC est déplié (expanded)
                            try:
                                expand_btn = row.find_element(By.CSS_SELECTOR, ".s-tree-node-expand")
                                aria_expanded = expand_btn.get_attribute("aria-expanded")
                                
                                if aria_expanded == "false":
                                    # Déplier le BC pour voir les articles
                                    self.logger.info("📂 Dépliage du BC...")
                                    expand_btn.click()
                                    time.sleep(0.5)
                                
                                bc_ouvert = True
                            except:
                                # Pas de bouton expand = déjà déplié
                                bc_ouvert = True
                        else:
                            # C'est un autre BC, on arrête si on était dans le bon
                            if bc_trouve:
                                break
                    
                    # NIVEAU 2+ = Ligne Article (enfant)
                    elif int(niveau) >= 2:
                        # On traite seulement si on est dans le bon BC
                        if not bc_trouve or not bc_ouvert:
                            continue
                        
                        # Chercher si cet article correspond à notre liste
                        for article in articles:
                            code_article = article['code'].strip()
                            
                            # Vérifier si la ligne commence par le code article
                            if ligne_text.startswith(code_article):
                                self.logger.info(f"   ✅ Article trouvé: {ligne_text}")
                                
                                # Récupérer la checkbox
                                checkbox = row.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                                checkbox_id = checkbox.get_attribute("id")
                                
                                # Cocher si pas déjà coché
                                if not checkbox.is_selected():
                                    label = row.find_element(By.CSS_SELECTOR, f"label[for='{checkbox_id}']")
                                    
                                    # Scroll
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label)
                                    time.sleep(0.3)
                                    
                                    # Cliquer
                                    label.click()
                                    time.sleep(0.5)
                                    
                                    self.logger.info(f"   ☑️ Article {code_article} coché")
                                    articles_trouves += 1
                                else:
                                    self.logger.info(f"   ⚪ Article {code_article} déjà coché")
                                    articles_trouves += 1
                                
                                # Ne pas chercher les autres articles pour cette ligne
                                break
                
                except Exception as e:
                    continue
            
            if not bc_trouve:
                self.logger.error(f"❌ BC {n_bc} non trouvé dans le tableau")
                return False
            
            # Gérer la popup de confirmation
            time.sleep(1)
            try:
                oui_btn = driver.find_element(By.XPATH, "//a[@aria-label='Oui']")
                oui_btn.click()
                self.logger.info("✅ Popup 'Oui' cliquée")
                time.sleep(1)
            except:
                pass
            
            self.logger.info(f"✅ {articles_trouves}/{len(articles)} article(s) sélectionné(s) pour BC {n_bc}")
            
            return articles_trouves > 0
            
        except Exception as e:
            self.logger.error(f"❌ Erreur sélection articles: {e}")
            driver.save_screenshot("error_selection_articles.png")
            return False

    def _remplir_article_dans_ligne(self, article: Dict, ligne_num: int) -> bool:
        """Remplir les données d'un article dans le tableau des lignes"""
        driver = self.driver_manager.driver
        
        try:
            # Attendre le tableau
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-grid-table-body"))
            )
            
            # Trouver toutes les lignes
            rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
            
            # Chercher la ligne avec cet article
            target_row = None
            for row in rows:
                try:
                    cells = row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
                    for cell in cells:
                        cell_value = cell.get_attribute('value')
                        if cell_value and article['code'] in cell_value:
                            target_row = row
                            break
                    if target_row:
                        break
                except:
                    continue
            
            if not target_row:
                self.logger.warning(f"Article {article['code']} non trouvé dans tableau")
                return False
            
            # Modifier les cellules
            cells = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
            
            # Quantité (adapter l'index selon ton tableau)
            if article['quantite'] and len(cells) > 2:
                qte_cell = cells[2]  # À ADAPTER
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", qte_cell)
                qte_cell.click()
                time.sleep(0.3)
                qte_cell.clear()
                qte_cell.send_keys(article['quantite'])
                qte_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            # N° Bon de transport
            if article['n_b_transport'] and len(cells) > 3:
                transport_cell = cells[3]  # À ADAPTER
                transport_cell.click()
                time.sleep(0.3)
                transport_cell.clear()
                transport_cell.send_keys(article['n_b_transport'])
                transport_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            # Matricule
            if article['matricule'] and len(cells) > 4:
                matricule_cell = cells[4]  # À ADAPTER
                matricule_cell.click()
                time.sleep(0.3)
                matricule_cell.clear()
                matricule_cell.send_keys(article['matricule'])
                matricule_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            # Poids
            if article['poids'] and len(cells) > 5:
                poids_cell = cells[5]  # À ADAPTER
                poids_cell.click()
                time.sleep(0.3)
                poids_cell.clear()
                poids_cell.send_keys(article['poids'])
                poids_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            # Marque
            if article['marque'] and len(cells) > 6:
                marque_cell = cells[6]  # À ADAPTER
                marque_cell.click()
                time.sleep(0.3)
                marque_cell.clear()
                marque_cell.send_keys(article['marque'])
                marque_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur remplissage article: {e}")
            return False
    
    def _enregistrer_reception(self) -> bool:
        """Enregistrer la réception"""
        driver = self.driver_manager.driver
        
        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i_save")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            
            save_link = save_btn.find_element(By.XPATH, "./ancestor::a")
            save_link.click()
            self.logger.info("💾 Enregistrement...")
            time.sleep(2)
            
            try:
                alert = driver.find_element(By.CSS_SELECTOR, ".s_alertbox_title")
                msg = alert.text
                
                if "Avertissement" in msg or "Erreur" in msg:
                    self.logger.error(f"❌ {msg}")
                    return False
                else:
                    self.logger.info(f"✅ {msg}")
                    return True
            except:
                self.logger.info("✅ Enregistré")
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
            self.logger.info("✅ Popup 'Oui' cliquée")
            time.sleep(1)
        except:
            # Pas de popup
            pass