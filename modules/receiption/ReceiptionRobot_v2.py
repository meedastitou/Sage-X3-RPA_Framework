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
        self.url_receiption = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FPREPROD%2F%24sessions%3Ff%3DGESPTH2%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%2765059cf7-11e9-4b40-bac9-66ef183fb4e1~ep~%2764a56978-56ab-46f1-8d83-ed18f7fa6484~appConn~())"
        
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

            
            # 6. TRAITER CHAQUE FOURNISSEUR
            for code_frs, frs_data in structure.items():
                
                # 5. NAVIGUER VERS MODULE
                self.navigate_to_module(self.url_receiption)
                time.sleep(5)
                self.wait_for_spinner_to_disappear(self.driver_manager.driver, timeout=90000)

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
            self.add_result({
                'type': 'BILAN_FINAL',
                'statut': 'SUCCES' if self.fournisseurs_echec == 0 else 'PARTIEL',
                'fournisseurs_traites': self.fournisseurs_traites,
                'fournisseurs_echec': self.fournisseurs_echec,
                'total_articles': self.total_articles,
                'message': f'{self.fournisseurs_traites} fournisseur(s) traité(s), {self.total_articles} article(s)'
            })
            
            # # 8. SAUVEGARDER RAPPORT
            self.save_report()
            
            # # 9. ENVOYER RÉSULTATS WEB
            self.send_results_to_web(email_f)
            
            self.logger.info("="*80)
            self.logger.info("🎉 PROCESSUS TERMINÉ")
            self.logger.info(f"✅ {self.fournisseurs_traites} fournisseur(s) traité(s)")
            self.logger.info(f"❌ {self.fournisseurs_echec} fournisseur(s) en échec")
            self.logger.info(f"📦 {self.total_articles} article(s) traité(s)")
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
            'CodeFrs',
            'BLFrs',
            'DateBC',
            'N_BC',
            'CodeArticle',
            'Quantite',
            'N_B_transport',
            'Matricule',
            'Poids',
            'Marque',
            'observation'
        ]
        
        df = self.excel_handler.read_excel(excel_file, required_columns=colonnes_requises)
        
        self.logger.info(f"✅ {len(df)} ligne(s) lues")
        
        # Validation des colonnes importantes (observation est optionnelle)
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
        CodeFrs	    BLFrs	        DateBC	    N_BC	    CodeArticle	Quantite	N_B_transport	Matricule	Poids	Marque	observation
        T6664	    FN°0037/2025	23/05/2025	BC186553	A15007	    1	        FN°0037/2025	XX	        0,01	LEASING	Note 1
        T6664	    FN°0037/2025	23/05/2025	BC186553	A15884	    1	        FN°0037/2025	XX	        0,01	LEASING	Note 2
        T3581	    FN°0065/2025	01/11/2021	BC165170	A12585	    1	        FN°0065/2025	XX	        0,01	LEASING
        T5700	    FN°0037/2025	06/01/2026	BC191348	A14495	    1	        FN°0037/2025	XX	        0,01	ETUDE	Urgent
        T5700	    FN°0065/2025	06/01/2026	BC191349	A14495	    1	        FN°0065/2025	XX	        0,01	ETUDE 

        Structure:
        {
            'T6664': {
                'bl_frs': 'FN°0037/2025',
                'date_bc': '23/05/2025',
                'bons_commande': {
                    'BC186553': {
                        'articles': [
                            {
                                'code': 'A15007',
                                'quantite': '1',
                                'n_b_transport': 'FN°0037/2025',
                                'matricule': 'XX',
                                'poids': '0,01',
                                'marque': 'LEASING'
                            },
                            {
                                'code': 'A15884',
                                'quantite': '1',
                                'n_b_transport': 'FN°0037/2025',
                                'matricule': 'XX',
                                'poids': '0,01',
                                'marque': 'LEASING'
                            }
                        ]
                    }
                }
            },
            'T3581': {
                'bl_frs': 'FN°0065/2025',
                'date_bc': '01/11/2021',
                'bons_commande': {
                    'BC165170': {
                        'articles': [
                            {
                                'code': 'A12585',
                                'quantite': '1',
                                'n_b_transport': 'FN°0065/2025',
                                'matricule': 'XX',
                                'poids': '0,01',
                                'marque': 'LEASING',
                                'observation': ''
                            }
                        ]
                    }
                }
            },
            'T5700': {
                'bl_frs': 'FN°0037/2025',
                'date_bc': '06/01/2026',
                'bons_commande': {
                    'BC191348': {
                        'articles': [
                            {
                                'code': '',
                                ...
                            }
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
                'marque': str(row['Marque']) if not pd.isna(row['Marque']) else '',
                'observation': str(row['observation']) if not pd.isna(row['observation']) else ''
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
        """
        Traiter un fournisseur avec TOUS ses BCs dans UNE SEULE réception
        Permet de regrouper plusieurs bons de commande du même fournisseur
        """
        resultat = {
            'type': 'Fournisseur',
            'code_frs': code_frs,
            'statut': 'Echec',
            'bcs_traites': 0,
            'bcs_echec': 0,
            'total_articles': 0,
            'message': ''
        }

        driver = self.driver_manager.driver
        bons_commande = frs_data['bons_commande']

        try:
            # 1. CRÉER UNE SEULE RÉCEPTION pour ce fournisseur
            if not self._cree_reception():
                self.logger.warning(f"❌ Échec création réception pour fournisseur {code_frs}")
                error_info = self.handle_error_with_screenshot(f"Erreur création réception pour {code_frs}", "_cree_reception")
                resultat['message'] = 'Erreur création réception'
                resultat['error_info'] = error_info
                return resultat

            self.logger.info(f"✅ Réception créée pour fournisseur {code_frs}")

            # 2. REMPLIR LES CHAMPS HEADER (une seule fois)
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

            # BL Fournisseur
            bl_input = self.get_input_by_label("BL fournisseur")
            bl_input.click()
            time.sleep(0.5)
            bl_input.clear()
            bl_input.send_keys(frs_data['bl_frs'])
            bl_input.send_keys(Keys.TAB)
            time.sleep(0.5)

            self.logger.info("✅ Header rempli")

            # 3. SÉLECTIONNER LES ARTICLES DE TOUS LES BCs
            self.logger.info(f"🔍 Sélection des articles pour {len(bons_commande)} BC(s)...")

            articles_selectionnes = self._selectionner_articles_multi_bc(bons_commande)

            if articles_selectionnes == 0:
                self.logger.warning(f"❌ Aucun article sélectionné pour fournisseur {code_frs}")
                error_info = self.handle_error_with_screenshot(f"Aucun article sélectionné pour {code_frs}", "_selectionner_articles_multi_bc")
                resultat['message'] = 'Aucun article sélectionné'
                resultat['error_info'] = error_info
                return resultat

            self.logger.info(f"✅ {articles_selectionnes} article(s) sélectionné(s) au total")

            # 4. REMPLIR LES DONNÉES DE CHAQUE ARTICLE
            ligne_num = 1
            for n_bc, bc_data in bons_commande.items():
                self.logger.info(f"{'─'*60}")
                self.logger.info(f"📋 Traitement articles du BC: {n_bc}")

                for article in bc_data['articles']:
                    self.logger.info(f"   📦 Article: {article['code']}")

                    if self._remplir_article_dans_ligne(article, ligne_num):
                        resultat['total_articles'] += 1
                        self.total_articles += 1
                        self.logger.info(f"   ✅ Article {article['code']} OK")
                    else:
                        self.logger.warning(f"   ⚠️ Article {article['code']} échec")

                    ligne_num += 1
                    time.sleep(0.3)

                resultat['bcs_traites'] += 1

            # 5. ENREGISTRER LA RÉCEPTION (une seule fois pour tous les BCs)
            if self._enregistrer_reception():
                resultat['statut'] = 'Succes'
                resultat['message'] = f'{resultat["bcs_traites"]} BC(s), {resultat["total_articles"]} article(s) traité(s)'
                self.logger.info(f"✅ Réception enregistrée pour fournisseur {code_frs}")
            else:
                error_info = self.handle_error_with_screenshot(f"Erreur enregistrement réception pour {code_frs}", "_enregistrer_reception")
                resultat['message'] = 'Erreur enregistrement'
                resultat['error_info'] = error_info

            self.logger.info(f"✅ Fournisseur {code_frs}: {resultat['message']}")

        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f"❌ Erreur fournisseur {code_frs}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            # Fermer le module avec confirmation d'abandon
            self.close_module(confirm_abandon=True)
            time.sleep(2)

        return resultat
    
    def _cree_reception(self) -> bool:
        """Cliquer sur le bouton 'Créer Réception'"""
        driver = self.driver_manager.driver
        try:
            time.sleep(2)
            add_button = driver.find_element(By.CSS_SELECTOR, "a.s_page_action_add")

            if "s-disabled" in add_button.get_attribute("class"):
                # Bouton désactivé 
                self.logger.info("❌ Bouton Add désactivé, impossible de créer une nouvelle réception")
                return False
            else:
                # Bouton activé
                self.logger.info("✅ Nouvelle réception créée")
                add_button.click()
                time.sleep(2)
                return True
        except Exception as e:
            self.logger.error(f"❌ Erreur création réception: {e}")
            return False

        # try:
        #     creer_btn = WebDriverWait(driver, 10).until(
        #         EC.element_to_be_clickable((By.CLASS_NAME, "s_page_action_i.s_page_action_i_add"))
        #     )
        #     creer_btn.click()
        #     time.sleep(2)
        
        #     self.logger.info("✅ Nouvelle réception créée")
        #     return True
            
        # except Exception as e:
        #     self.logger.error(f"❌ Erreur création réception: {e}")
        #     return False

    def _selectionner_articles_multi_bc(self, bons_commande: Dict) -> int:
        """
        Sélectionner les articles de PLUSIEURS bons de commande dans le tableau 'Sélection commandes'

        Args:
            bons_commande: Dictionnaire {n_bc: {'articles': [...]}, ...}

        Returns:
            Nombre total d'articles sélectionnés
        """
        driver = self.driver_manager.driver
        total_articles_selectionnes = 0

        try:
            # 1. Cliquer sur "Sélection commandes" pour ouvrir la section
            try:
                commandes_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[@title='Sélection commandes']"))
                )
                commandes_btn.click()
                self.logger.info("✅ Section 'Sélection commandes' ouverte")
                time.sleep(1)
            except:
                self.logger.warning("⚠️ Bouton 'Sélection commandes' non trouvé, tableau déjà ouvert")

            # 2. Attendre le tableau
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-grid-table-body"))
            )
            time.sleep(1)

            # 3. Traiter chaque BC
            for n_bc, bc_data in bons_commande.items():
                self.logger.info(f"{'─'*60}")
                self.logger.info(f"🔍 Sélection articles pour BC: {n_bc}")

                articles = bc_data['articles']
                articles_trouves = self._selectionner_articles_pour_un_bc(n_bc, articles)

                total_articles_selectionnes += articles_trouves
                self.logger.info(f"✅ {articles_trouves}/{len(articles)} article(s) sélectionné(s) pour BC {n_bc}")

            # 4. Gérer la popup de confirmation "Voulez-vous remplacer..."
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

            return total_articles_selectionnes

        except Exception as e:
            self.logger.error(f"❌ Erreur sélection multi-BC: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return total_articles_selectionnes

    def _selectionner_articles_pour_un_bc(self, n_bc: str, articles: List[Dict]) -> int:
        """
        Sélectionner les articles d'UN seul BC dans le tableau (utilisé par _selectionner_articles_multi_bc)

        Args:
            n_bc: Numéro du bon de commande
            articles: Liste des articles à sélectionner

        Returns:
            Nombre d'articles sélectionnés
        """
        driver = self.driver_manager.driver
        articles_trouves = 0
        articles_attendus = {art['code'].strip(): False for art in articles}

        try:
            # Récupérer toutes les lignes
            rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")

            bc_trouve = False

            for idx, row in enumerate(rows):
                try:
                    # Vérifier si ligne visible
                    style = row.get_attribute('style') or ''
                    if 'display: none' in style or 'display:none' in style:
                        continue

                    # Récupérer le padding-left pour déterminer le niveau
                    td = row.find_element(By.CSS_SELECTOR, "td.s-tree-cell")
                    padding_left = td.get_attribute('style')

                    # Extraire la valeur de padding-left
                    if 'padding-left: 0px' in padding_left:
                        niveau = 0  # BC parent
                    elif 'padding-left: 22px' in padding_left:
                        niveau = 1  # Article enfant
                    else:
                        niveau = 2  # Autre

                    # Récupérer le texte de la ligne
                    desc_div = row.find_element(By.CSS_SELECTOR, ".s-tree-node-desc-value")
                    ligne_text = desc_div.text.strip()

                    # NIVEAU 0 = Ligne BC (parent)
                    if niveau == 0:
                        # Si on était dans notre BC et qu'on en trouve un autre, on arrête
                        if bc_trouve:
                            break

                        # Vérifier si c'est notre BC
                        if n_bc in ligne_text:
                            bc_trouve = True
                            self.logger.info(f"✅ BC trouvé: {ligne_text}")

                            # Vérifier si le BC a un bouton expand (plier/déplier)
                            try:
                                expand_btn = row.find_element(By.CSS_SELECTOR, "a.s-tree-node-picker")
                                btn_class = expand_btn.get_attribute('class')

                                # Si bouton "up" = BC plié, il faut le déplier
                                if 's-btn-dir_up' in btn_class:
                                    self.logger.info("📂 Dépliage du BC...")
                                    expand_btn.click()
                                    time.sleep(0.8)

                                    # Recharger les lignes après le dépliage
                                    rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
                            except:
                                pass

                    # NIVEAU 1 = Ligne Article (enfant)
                    elif niveau == 1 and bc_trouve:
                        # Chercher si cet article correspond à notre liste
                        for code_article in articles_attendus.keys():
                            if articles_attendus[code_article]:
                                continue  # Déjà trouvé

                            # Vérifier si la ligne commence par le code article
                            if ligne_text.startswith(code_article):
                                self.logger.info(f"   ✅ Article trouvé: {ligne_text}")

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
                                        driver.execute_script("arguments[0].click();", label)

                                    time.sleep(0.5)
                                    self.logger.info(f"   ☑️ Article {code_article} coché")

                                articles_trouves += 1
                                articles_attendus[code_article] = True
                                break

                except Exception as e:
                    self.logger.debug(f"⚠️ Erreur ligne {idx}: {e}")
                    continue

            if not bc_trouve:
                self.logger.warning(f"⚠️ BC {n_bc} non trouvé dans le tableau")

            # Afficher les articles manquants
            articles_manquants = [code for code, trouve in articles_attendus.items() if not trouve]
            if articles_manquants:
                self.logger.warning(f"⚠️ Articles non trouvés dans {n_bc}: {', '.join(articles_manquants)}")

            return articles_trouves

        except Exception as e:
            self.logger.error(f"❌ Erreur sélection articles BC {n_bc}: {e}")
            return articles_trouves

    def _ajouter_observation(self, article: Dict, row_number: int) -> bool:
        """
        Ajouter une observation à un article via la modale de texte

        Args:
            article: Dictionnaire contenant les données de l'article
            row_number: Numéro de la ligne dans le tableau

        Returns:
            True si l'observation a été ajoutée avec succès, False sinon
        """
        driver = self.driver_manager.driver

        try:
            # Vérifier si une observation existe
            observation = article.get('observation', '').strip()
            if not observation:
                self.logger.info("   ℹ️ Aucune observation à ajouter")
                return True

            # Trouver la ligne avec le numéro dans la première cellule
            row_with_number = driver.find_element(By.XPATH,
                f"//td[contains(@class, 's-record-row-index') and normalize-space(text())='{row_number}']/parent::tr"
            )

            # Dans cette ligne, trouver le premier <i> et cliquer dessus
            icon_i = row_with_number.find_element(By.XPATH, ".//i")
            icon_i.click()
            time.sleep(1)

            # Cliquer sur "Texte" dans le popup
            popup = driver.find_element(By.CLASS_NAME, "s_popup")
            texte_link = popup.find_element(By.XPATH, ".//a[text()='Texte']")
            texte_link.click()
            time.sleep(2)

            # Attendre la modale
            modal = driver.find_element(By.CLASS_NAME, "s_modal_dialog")
            if not modal.is_displayed():
                self.logger.warning("   ⚠️ Modale non visible")
                return False

            # Basculer vers l'iframe de la modale
            iframe = modal.find_element(By.TAG_NAME, "iframe")
            driver.switch_to.frame(iframe)

            # Écrire l'observation dans le body de l'iframe
            body = driver.find_element(By.TAG_NAME, "body")
            body.clear()
            body.send_keys(observation)

            # Revenir au contenu principal
            driver.switch_to.default_content()

            # Cliquer sur OK pour valider
            ok_button = driver.find_element(By.XPATH,
                "//div[@class='s_page_header_business_actions']//a[text()='OK']"
            )
            ok_button.click()
            time.sleep(0.5)

            self.logger.info(f"   ✅ Observation ajoutée: {observation}")
            return True

        except Exception as e:
            self.logger.error(f"   ❌ Erreur lors de l'ajout de l'observation: {e}")
            # Revenir au contenu principal en cas d'erreur
            try:
                driver.switch_to.default_content()
            except:
                pass
            return False

    def _remplir_article_dans_ligne(self, article: Dict, ligne_num: int) -> bool:
        """Remplir les données d'un article dans le tableau des lignes"""
        
        driver = self.driver_manager.driver

        self.logger.info(f"🖊️ Remplissage article {article} dans la ligne {ligne_num}")
        try:
            # Attendre le tableau
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-grid-table-body"))
            )

            table = driver.find_element(By.XPATH, 
                "//section[contains(@class, 's-h1')]//div[contains(text(), 'Lignes')]/ancestor::section//table[contains(@class, 's-grid-table-body')]"
            )
            # Trouver toutes les lignes
            rows = table.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
            self.logger.info(f"📊 {len(rows)} ligne(s) dans le tableau pour remplissage")
            
            # Chercher la ligne avec cet article
            target_row = None
            row_number = 1
            row_index = None
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
                    row_number = row_number+1
                except:
                    continue
            
            if not target_row:
                self.logger.warning(f"Article {article['code']} non trouvé dans tableau")
                return False
            self.logger.info(f"   📍 Ligne trouvée: {row_number}")

            # Ajouter l'observation si elle existe
            self._ajouter_observation(article, row_number)

            # Modifier les cellules
            cells = target_row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")
            
            # Quantité (adapter l'index selon ton tableau)
            if article['quantite'] and len(cells) > 5:
                self.logger.info("Remplissage quantité...")
                qte_cell = cells[5]
                # driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", qte_cell)
                qte_cell.click()
                time.sleep(0.3)
                qte_cell.clear()
                qte_cell.send_keys(article['quantite'])
                qte_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            # N° Bon de transport
            if article['n_b_transport'] and len(cells) > 9:
                transport_cell = cells[9]  
                transport_cell.click()
                time.sleep(0.3)
                transport_cell.clear()
                transport_cell.send_keys(article['n_b_transport'])
                transport_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            # Matricule
            if article['matricule'] and len(cells) > 10:
                matricule_cell = cells[10] 
                matricule_cell.click()
                time.sleep(0.3)
                matricule_cell.clear()
                matricule_cell.send_keys(article['matricule'])
                matricule_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            # Poids
            if article['poids'] and len(cells) > 11:
                poids_cell = cells[11] 
                poids_cell.click()
                time.sleep(0.3)
                poids_cell.clear()
                poids_cell.send_keys(article['poids'])
                poids_cell.send_keys(Keys.TAB)
                time.sleep(0.3)
            
            # Marque
            if article['marque'] and len(cells) > 12:
                marque_cell = cells[12] 
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
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_check")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()

            time.sleep(5)

            self.wait_for_spinner_to_disappear(driver, timeout=120000)
            
            # try:
            #     alert = driver.find_element(By.CSS_SELECTOR, ".s_alertbox_title")
            #     msg = alert.text
                
            #     if "Avertissement" in msg or "Erreur" in msg:
            #         self.logger.error(f"❌ {msg}")
            #         return False
            #     else:
            #         self.logger.info(f"✅ {msg}")
            #         return True
            # except:
            #     self.logger.info("✅ Enregistré")
            #     return True
            time.sleep(4)
            s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
            s_page_close.click()
            time.sleep(2)
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
            self.logger.info("✅ Popup 'Oui' cliquée")
            time.sleep(1)
        except:
            # Pas de popup
            pass