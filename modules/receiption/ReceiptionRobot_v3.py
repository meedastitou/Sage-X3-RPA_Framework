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
import itertools
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
        self.url_receiption = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESPTH2%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%279844eacb-4f96-4301-8b0c-dbe4f4d48e4d~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"
        
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

            
            # 6. TRAITER CHAQUE FOURNISSEUR ET CHAQUE RÉCEPTION (par BLFrs)
            for code_frs, frs_data in structure.items():
                self.logger.info(f"{'='*80}")
                self.logger.info(f"🏢 FOURNISSEUR: {code_frs}")
                self.logger.info(f"{'='*80}")

                # Parcourir chaque réception (groupée par BLFrs)
                for bl_frs, reception_data in frs_data['receptions'].items():
                    # NAVIGUER VERS MODULE pour chaque réception
                    self.navigate_to_module(self.url_receiption)
                    time.sleep(5)
                    self.wait_for_spinner_to_disappear(self.driver_manager.driver, timeout=90000)

                    self.logger.info(f"{'─'*60}")
                    self.logger.info(f"📄 RÉCEPTION pour BL Fournisseur: {bl_frs}")
                    self.logger.info(f"   📦 {len(reception_data['bons_commande'])} BC(s) à regrouper")
                    self.logger.info(f"{'─'*60}")

                    resultat_reception = self._traiter_reception(code_frs, reception_data)
                    self.add_result(resultat_reception)

                    if resultat_reception['statut'] == 'Succes':
                        self.fournisseurs_traites += 1
                    else:
                        self.fournisseurs_echec += 1
                        self.logger.warning(f" Échec réception {bl_frs} pour {code_frs}, mais on continue...")
            
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
            self.logger.info(f"{self.fournisseurs_traites} fournisseur(s) traité(s)")
            self.logger.info(f" {self.fournisseurs_echec} fournisseur(s) en échec")
            self.logger.info(f"📦 {self.total_articles} article(s) traité(s)")
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
        
        self.logger.info(f"{len(df)} ligne(s) lues")
        
        # Validation des colonnes importantes (observation est optionnelle)
        lignes_invalides = []
        for idx, row in df.iterrows():
            colonnes_vides = []
            for col in ['CodeFrs','BLFrs', 'DateBC', 'N_BC', 'CodeArticle', 'Quantite', 'Poids', 'Marque']:
                if pd.isna(row[col]) or str(row[col]).strip() == '':
                    colonnes_vides.append(col)

            if colonnes_vides:
                lignes_invalides.append(idx)
                self.logger.warning(f" Ligne {idx+1} ignorée - Colonnes vides: {', '.join(colonnes_vides)}")
        
        if lignes_invalides:
            df = df.drop(df.index[lignes_invalides])
            self.logger.warning(f" {len(lignes_invalides)} ligne(s) invalide(s) ignorée(s)")
        
        self.logger.info(f"{len(df)} ligne(s) valides à traiter")
        return df
    
    def _regrouper_donnees(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Regrouper par Fournisseur → BLFrs → BC → Articles

        IMPORTANT: On crée UNE SEULE réception pour plusieurs BC uniquement s'ils ont le MÊME BLFrs

        Exemple de données:
        CodeFrs     BLFrs           DateBC      N_BC        CodeArticle
        T6664       FN°0037/2025    23/05/2025  BC186553    A15007
        T6664       FN°0037/2025    23/05/2025  BC186554    A15884    <- même BLFrs = même réception
        T6664       FN°0065/2025    23/05/2025  BC186555    A15999    <- BLFrs différent = réception séparée
        T5700       FN°0037/2025    06/01/2026  BC191348    A14495
        T5700       FN°0065/2025    06/01/2026  BC191349    A14495    <- BLFrs différent = réception séparée

        Structure:
        {
            'T6664': {
                'receptions': {
                    'FN°0037/2025': {  # Une réception par BLFrs
                        'bl_frs': 'FN°0037/2025',
                        'date_bc': '23/05/2025',
                        'bons_commande': {
                            'BC186553': {'articles': [...]},
                            'BC186554': {'articles': [...]}  # Même réception car même BLFrs
                        }
                    },
                    'FN°0065/2025': {  # Réception séparée
                        'bl_frs': 'FN°0065/2025',
                        'date_bc': '23/05/2025',
                        'bons_commande': {
                            'BC186555': {'articles': [...]}
                        }
                    }
                }
            },
            'T5700': {
                'receptions': {
                    'FN°0037/2025': {...},
                    'FN°0065/2025': {...}
                }
            }
        }
        """
        self.logger.info("="*80)
        self.logger.info("🔄 REGROUPEMENT DES DONNÉES (par Fournisseur → BLFrs → BC)")
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
                    'receptions': {}
                }

            # Initialiser réception (par BLFrs) si nouvelle
            if bl_frs not in structure[code_frs]['receptions']:
                structure[code_frs]['receptions'][bl_frs] = {
                    'bl_frs': bl_frs,
                    'date_bc': date_bc,
                    'bons_commande': {}
                }

            # Initialiser BC si nouveau
            if n_bc not in structure[code_frs]['receptions'][bl_frs]['bons_commande']:
                structure[code_frs]['receptions'][bl_frs]['bons_commande'][n_bc] = {
                    'articles': []
                }

            # Ajouter l'article
            article = {
                'code': str(row['CodeArticle']).strip(),
                'quantite': str(row['Quantite']),
                'n_bc': n_bc,  # Numéro BC pour identifier la bonne ligne si même article dans plusieurs BC
                'n_b_transport': str(row['N_B_transport']) if not pd.isna(row['N_B_transport']) else '',
                'matricule': str(row['Matricule']) if not pd.isna(row['Matricule']) else '',
                'poids': str(row['Poids']) if not pd.isna(row['Poids']) else '',
                'marque': str(row['Marque']) if not pd.isna(row['Marque']) else '',
                'observation': str(row['observation']) if not pd.isna(row['observation']) else ''
            }

            structure[code_frs]['receptions'][bl_frs]['bons_commande'][n_bc]['articles'].append(article)

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
        """Afficher un résumé de la structure (Fournisseur → BLFrs → BCs)"""
        self.logger.info("="*80)
        self.logger.info(" RÉSUMÉ DU TRAITEMENT")
        self.logger.info("="*80)

        # Compter le nombre total de réceptions
        total_receptions = sum(len(frs_data['receptions']) for frs_data in structure.values())

        self.logger.info(f"🏢 {len(structure)} Fournisseur(s), {total_receptions} Réception(s) à créer:")

        for code_frs, frs_data in structure.items():
            self.logger.info(f"   📦 Fournisseur: {code_frs}")
            self.logger.info(f"      {len(frs_data['receptions'])} Réception(s):")

            for bl_frs, reception_data in frs_data['receptions'].items():
                nb_bcs = len(reception_data['bons_commande'])
                self.logger.info(f"      ─────────────────────────────────")
                self.logger.info(f"      📄 BL Fournisseur: {bl_frs}")
                self.logger.info(f"         Date BC: {reception_data['date_bc']}")
                self.logger.info(f"         {nb_bcs} BC(s) regroupés dans cette réception:")

                for n_bc, bc_data in reception_data['bons_commande'].items():
                    nb_articles = len(bc_data['articles'])
                    self.logger.info(f"            • {n_bc}: {nb_articles} article(s)")
                    for art in bc_data['articles']:
                        self.logger.info(f"               - {art['code']}: Qté {art['quantite']}")

        self.logger.info("="*80)
    
    def _traiter_reception(self, code_frs: str, reception_data: Dict) -> Dict[str, Any]:
        """
        Traiter une réception qui regroupe plusieurs BCs ayant le MÊME BLFrs

        Args:
            code_frs: Code du fournisseur
            reception_data: Données de la réception contenant:
                - bl_frs: Numéro BL fournisseur
                - date_bc: Date du BC
                - bons_commande: Dict des BCs à inclure dans cette réception
        """
        bl_frs = reception_data['bl_frs']
        bons_commande = reception_data['bons_commande']

        resultat = {
            'type': 'Reception',
            'code_frs': code_frs,
            'bl_frs': bl_frs,
            'statut': 'Echec',
            'bcs_traites': 0,
            'bcs_echec': 0,
            'total_articles': 0,
            'message': ''
        }

        try:
            # 1. CRÉER UNE SEULE RÉCEPTION pour ce groupe de BCs (même BLFrs)
            if not self._cree_reception():
                self.logger.warning(f" Échec création réception pour {code_frs} / BL {bl_frs}")
                resultat['message'] = 'Erreur création réception'
                return resultat

            self.logger.info(f"Réception créée pour {code_frs} / BL {bl_frs}")

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
            bl_input.send_keys(bl_frs)
            bl_input.send_keys(Keys.TAB)
            time.sleep(0.5)

            self.logger.info(f"Header rempli (Fournisseur: {code_frs}, BL: {bl_frs})")

            # 3. SÉLECTIONNER LES ARTICLES DE TOUS LES BCs (qui ont le même BLFrs)
            self.logger.info(f"🔍 Sélection des articles pour {len(bons_commande)} BC(s) avec BL {bl_frs}...")

            articles_selectionnes = self._selectionner_articles_multi_bc(bons_commande)

            if articles_selectionnes == 0:
                self.logger.warning(f" Aucun article sélectionné pour {code_frs} / BL {bl_frs}")
                resultat['message'] = 'Aucun article sélectionné'
                return resultat

            self.logger.info(f"{articles_selectionnes} article(s) sélectionné(s) au total")

            # 4. REMPLIR LES DONNÉES DE CHAQUE ARTICLE
            ligne_num = 1
            for n_bc, bc_data in bons_commande.items():
                self.logger.info(f"{'─'*40}")
                self.logger.info(f"📋 Traitement articles du BC: {n_bc}")

                for article in bc_data['articles']:
                    self.logger.info(f"   📦 Article: {article['code']}")

                    if self._remplir_article_dans_ligne(article, ligne_num):
                        resultat['total_articles'] += 1
                        self.total_articles += 1
                        self.logger.info(f"   Article {article['code']} OK")
                    else:
                        self.logger.warning(f"    Article {article['code']} échec")

                    ligne_num += 1
                    time.sleep(0.3)

                resultat['bcs_traites'] += 1
 
            # 5. ENREGISTRER LA RÉCEPTION (une seule fois pour tous les BCs du même BLFrs)
            if self._enregistrer_reception():
                resultat['statut'] = 'Succes'
                resultat['message'] = f'BL {bl_frs}: {resultat["bcs_traites"]} BC(s), {resultat["total_articles"]} article(s)'
                self.logger.info(f"Réception enregistrée pour {code_frs} / BL {bl_frs}")
            else:
                resultat['message'] = 'Erreur enregistrement'

            self.logger.info(f"Réception {code_frs} / BL {bl_frs}: {resultat['message']}")

        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f" Erreur réception {code_frs} / BL {bl_frs}: {e}")
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
                self.logger.info(" Bouton Add désactivé, impossible de créer une nouvelle réception")
                return False
            else:
                # Bouton activé
                self.logger.info("Nouvelle réception créée")
                add_button.click()
                time.sleep(2)
                return True
        except Exception as e:
            self.logger.error(f" Erreur création réception: {e}")
            return False

        # try:
        #     creer_btn = WebDriverWait(driver, 10).until(
        #         EC.element_to_be_clickable((By.CLASS_NAME, "s_page_action_i.s_page_action_i_add"))
        #     )
        #     creer_btn.click()
        #     time.sleep(2)
        
        #     self.logger.info("Nouvelle réception créée")
        #     return True
            
        # except Exception as e:
        #     self.logger.error(f" Erreur création réception: {e}")
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
                self.logger.info("Section 'Sélection commandes' ouverte")
                time.sleep(1)
            except:
                self.logger.warning(" Bouton 'Sélection commandes' non trouvé, tableau déjà ouvert")

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
                self.logger.info(f"{articles_trouves}/{len(articles)} article(s) sélectionné(s) pour BC {n_bc}")

            # 4. Gérer la popup de confirmation "Voulez-vous remplacer..."
            time.sleep(1)
            try:
                oui_btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[@aria-label='Oui']"))
                )
                oui_btn.click()
                self.logger.info("Popup 'Oui' cliquée")
                time.sleep(1)
            except:
                self.logger.debug("ℹ️ Pas de popup de confirmation")

            return total_articles_selectionnes

        except Exception as e:
            self.logger.error(f" Erreur sélection multi-BC: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return total_articles_selectionnes

    def _trouver_combinaison_lignes(self, lines: list, qty_voulue: float) -> list:
        """
        Retourne le sous-ensemble de lines dont la somme des quantités == qty_voulue.
        lines: List[(row_element, qty_ligne, ligne_text)]
        Priorité: 1) ligne unique exacte → 2) subset-sum exact → 3) greedy décroissant
        """
        if len(lines) == 1:
            return lines

        # 1. Match exact sur une seule ligne
        for entry in lines:
            if entry[1] is not None and abs(entry[1] - qty_voulue) < 1e-9:
                return [entry]

        # 2. Subset-sum exact
        for r in range(2, len(lines) + 1):
            for combo in itertools.combinations(lines, r):
                total = sum(q for (_, q, _) in combo if q is not None)
                if abs(total - qty_voulue) < 1e-9:
                    return list(combo)

        # 3. Greedy fallback: tri décroissant, accumulation jusqu'à qty_voulue
        sorted_lines = sorted(lines, key=lambda e: e[1] if e[1] is not None else 0, reverse=True)
        selected, running = [], 0.0
        for entry in sorted_lines:
            selected.append(entry)
            running += entry[1] if entry[1] is not None else 0
            if running >= qty_voulue:
                break
        return selected

    def _selectionner_articles_pour_un_bc(self, n_bc: str, articles: List[Dict]) -> int:
        """
        Sélectionner les articles d'UN seul BC dans le tableau (utilisé par _selectionner_articles_multi_bc)

        Args:
            n_bc: Numéro du bon de commande
            articles: Liste des articles à sélectionner

        Returns:
            Nombre d'articles sélectionnés (lignes cochées)
        """
        import re
        driver = self.driver_manager.driver
        articles_trouves = 0

        # dict code → quantité voulue (depuis Excel)
        articles_map = {}
        for art in articles:
            code = art['code'].strip()
            try:
                articles_map[code] = float(str(art['quantite']).replace(',', '.'))
            except (ValueError, TypeError):
                articles_map[code] = None

        def _scanner_rows(rows_list):
            """Scan les rows et retourne bc_rows + bc_trouve."""
            found = False
            collected = defaultdict(list)

            for idx, row in enumerate(rows_list):
                try:
                    style = row.get_attribute('style') or ''
                    if 'display: none' in style or 'display:none' in style:
                        continue

                    td = row.find_element(By.CSS_SELECTOR, "td.s-tree-cell")
                    padding_left = td.get_attribute('style') or ''

                    if 'padding-left: 0px' in padding_left:
                        niveau = 0
                    elif 'padding-left: 22px' in padding_left:
                        niveau = 1
                    else:
                        niveau = 2

                    desc_div = row.find_element(By.CSS_SELECTOR, ".s-tree-node-desc-value")
                    ligne_text = desc_div.text.strip()

                    if niveau == 0:
                        if found:
                            break
                        if n_bc in ligne_text:
                            found = True
                            self.logger.info(f"BC trouvé: {ligne_text}")
                            # Expand si replié
                            try:
                                expand_btn = row.find_element(By.CSS_SELECTOR, "a.s-tree-node-picker")
                                if 's-btn-dir_up' in (expand_btn.get_attribute('class') or ''):
                                    self.logger.info("📂 Dépliage du BC...")
                                    expand_btn.click()
                                    time.sleep(0.8)
                                    # DOM changé → signaler qu'il faut recommencer
                                    return None, True  # (pas de résultat, needs_rescan=True)
                            except Exception:
                                pass

                    elif niveau == 1 and found:
                        m = re.search(r'Attendue\s+([\d,\.]+)', ligne_text)
                        qty_ligne = None
                        if m:
                            try:
                                qty_ligne = float(m.group(1).replace(',', '.'))
                            except ValueError:
                                pass

                        for code in articles_map:
                            if ligne_text.startswith(code):
                                rest = ligne_text[len(code):]
                                if rest and rest[0] not in (' ', '_', '\t'):
                                    continue  # faux-positif (ex: A046 vs A04686)
                                collected[code].append((row, qty_ligne, ligne_text))
                                break

                except Exception as e:
                    self.logger.debug(f" Erreur scan ligne {idx}: {e}")
                    continue

            return collected, found

        try:
            # ── PHASE 1: EXTRACT ─────────────────────────────────────────────
            rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
            bc_rows, bc_trouve = _scanner_rows(rows)

            if bc_rows is None:
                # BC était replié, DOM rechargé → nouveau scan
                rows = driver.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
                bc_rows, bc_trouve = _scanner_rows(rows)

            if not bc_trouve:
                self.logger.warning(f" BC {n_bc} non trouvé dans le tableau")
                return 0

            total_lignes = sum(len(v) for v in bc_rows.values())
            self.logger.info(f" Phase 1 terminée: {total_lignes} ligne(s) collectée(s) pour {len(bc_rows)} code(s)")

            # ── PHASE 2: MATCH + SELECT ───────────────────────────────────────
            for code_article, qty_voulue in articles_map.items():
                lines_for_code = bc_rows.get(code_article, [])

                if not lines_for_code:
                    self.logger.warning(f" Article {code_article} non trouvé dans {n_bc}")
                    continue

                if qty_voulue is None or len(lines_for_code) == 1:
                    lignes_a_cocher = lines_for_code
                else:
                    lignes_a_cocher = self._trouver_combinaison_lignes(lines_for_code, qty_voulue)
                    total_sel = sum(q for (_, q, _) in lignes_a_cocher if q is not None)
                    self.logger.info(
                        f"   → {code_article}: {len(lignes_a_cocher)} ligne(s) sélectionnée(s), "
                        f"sum={total_sel} (voulue={qty_voulue})"
                    )
                    if total_sel < qty_voulue:
                        self.logger.warning(
                            f" {code_article}: sélection partielle {total_sel}/{qty_voulue} dans {n_bc}"
                        )

                for (row_elem, qty_ligne, ligne_text) in lignes_a_cocher:
                    try:
                        checkbox = row_elem.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                        if not checkbox.is_selected():
                            checkbox_id = checkbox.get_attribute("id")
                            label = row_elem.find_element(By.CSS_SELECTOR, f"label[for='{checkbox_id}']")
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label)
                            time.sleep(0.3)
                            try:
                                label.click()
                            except Exception:
                                driver.execute_script("arguments[0].click();", label)
                            time.sleep(0.5)
                            self.logger.info(f"   ☑️ {code_article} coché ({ligne_text})")
                        else:
                            self.logger.debug(f"   ℹ️ {code_article} déjà coché ({ligne_text})")
                        articles_trouves += 1
                    except Exception as e:
                        self.logger.warning(f"    Impossible de cocher {code_article}: {e}")

                self.logger.info(f"   {articles_trouves}/{len(articles)} article(s) sélectionné(s) pour {n_bc}")
            return articles_trouves

        except Exception as e:
            self.logger.error(f" Erreur sélection articles BC {n_bc}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
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
                self.logger.warning("    Modale non visible")
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

            self.logger.info(f"   Observation ajoutée: {observation}")
            return True

        except Exception as e:
            self.logger.error(f"    Erreur lors de l'ajout de l'observation: {e}")
            # Revenir au contenu principal en cas d'erreur
            try:
                driver.switch_to.default_content()
            except:
                pass
            return False

    def _remplir_article_dans_ligne(self, article: Dict, ligne_num: int) -> bool:
        """Remplir les données d'un article dans le tableau des lignes.
        Si plusieurs lignes existent pour le même article (multi-BC), distribue
        la quantité voulue en remplissant chaque ligne jusqu'à son max.
        Filtre par numéro de BC si disponible dans l'article.
        """
        driver = self.driver_manager.driver
        n_bc = article.get('n_bc', '')  # Numéro BC pour filtrer
        self.logger.info(f"🖊️ Remplissage article {article['code']} (BC={n_bc}, qty={article['quantite']}) ligne {ligne_num}")

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-grid-table-body"))
            )

            table = driver.find_element(By.XPATH,
                "//section[contains(@class, 's-h1')]//div[contains(text(), 'Lignes')]/ancestor::section//table[contains(@class, 's-grid-table-body')]"
            )
            rows = table.find_elements(By.CSS_SELECTOR, ".s-grid-table-body tr.s-grid-row")
            self.logger.info(f"📋 {len(rows)} ligne(s) dans le tableau pour remplissage")

            # Trouver TOUTES les lignes contenant ce code article ET correspondant au BC
            article_rows = []  # list of (row_element, row_number, cells)
            rn = 1
            for row in rows:
                try:
                    cells = row.find_elements(By.CSS_SELECTOR, ".s-inplace-input")

                    # Vérifier si cette ligne contient le code article
                    article_found = False
                    for cell in cells:
                        cell_value = cell.get_attribute('value')
                        if cell_value and article['code'] in cell_value:
                            article_found = True
                            break

                    if article_found:
                        # Si n_bc est spécifié, vérifier qu'il correspond
                        if n_bc:
                            bc_match = False
                            # Chercher le BC dans les premières colonnes (généralement cells[0] ou cells[1])
                            for idx in range(min(3, len(cells))):
                                cell_val = cells[idx].get_attribute('value') or ''
                                if n_bc in cell_val:
                                    bc_match = True
                                    break

                            if bc_match:
                                article_rows.append((row, rn, cells))
                                self.logger.debug(f"   Ligne {rn}: article {article['code']} + BC {n_bc} ✓")
                            else:
                                self.logger.debug(f"   Ligne {rn}: article {article['code']} trouvé mais BC différent, ignoré")
                        else:
                            # Pas de filtre BC, ajouter la ligne
                            article_rows.append((row, rn, cells))
                except Exception:
                    pass
                rn += 1

            if not article_rows:
                self.logger.warning(f"Article {article['code']} (BC={n_bc}) non trouvé dans tableau")
                return False

            self.logger.info(f"   📍 {len(article_rows)} ligne(s) trouvée(s) pour {article['code']} (BC={n_bc})")

            # Parser la quantité voulue
            try:
                qty_voulue = float(str(article['quantite']).replace(',', '.'))
            except (ValueError, TypeError):
                qty_voulue = None

            qty_restante = qty_voulue

            for i, (_, row_number, cells) in enumerate(article_rows):
                # Observation uniquement sur la première ligne
                if i == 0:
                    self._ajouter_observation(article, row_number)

                # Calculer la quantité à mettre sur cette ligne
                if qty_voulue is not None and len(article_rows) > 1:
                    # Lire la qty max de cette ligne (pré-remplie par Sage depuis le BC)
                    try:
                        pre_qty_str = cells[5].get_attribute('value') or '0'
                        pre_qty = float(pre_qty_str.replace(',', '.').replace(' ', ''))
                    except (ValueError, IndexError):
                        pre_qty = qty_restante
                    qty_ligne = min(pre_qty, qty_restante)
                    qty_restante -= qty_ligne
                    qty_str = str(int(qty_ligne) if qty_ligne == int(qty_ligne) else qty_ligne)
                    self.logger.info(f"   → Ligne {row_number}: qty={qty_str} (max={pre_qty}, restante={qty_restante})")
                else:
                    qty_str = str(article['quantite'])

                # Remplir la quantité
                if article['quantite'] and len(cells) > 5:
                    qte_cell = cells[5]
                    qte_cell.click()
                    time.sleep(0.3)
                    qte_cell.clear()
                    qte_cell.send_keys(qty_str)
                    qte_cell.send_keys(Keys.TAB)
                    time.sleep(0.3)

                # Remplir les autres champs sur chaque ligne
                if article['n_b_transport'] and len(cells) > 9:
                    transport_cell = cells[9]
                    transport_cell.click()
                    time.sleep(0.3)
                    transport_cell.clear()
                    transport_cell.send_keys(article['n_b_transport'])
                    transport_cell.send_keys(Keys.TAB)
                    time.sleep(0.3)

                if article['matricule'] and len(cells) > 10:
                    matricule_cell = cells[10]
                    matricule_cell.click()
                    time.sleep(0.3)
                    matricule_cell.clear()
                    matricule_cell.send_keys(article['matricule'])
                    matricule_cell.send_keys(Keys.TAB)
                    time.sleep(0.3)

                if article['poids'] and len(cells) > 11:
                    poids_cell = cells[11]
                    poids_cell.click()
                    time.sleep(0.3)
                    poids_cell.clear()
                    poids_cell.send_keys(article['poids'])
                    poids_cell.send_keys(Keys.TAB)
                    time.sleep(0.3)

                if article['marque'] and len(cells) > 12:
                    marque_cell = cells[12]
                    marque_cell.click()
                    time.sleep(0.3)
                    marque_cell.clear()
                    marque_cell.send_keys(article['marque'])
                    marque_cell.send_keys(Keys.TAB)
                    time.sleep(0.3)

                if qty_voulue is not None and qty_restante <= 0:
                    break

            if qty_voulue is not None and qty_restante > 0:
                self.logger.warning(
                    f" {article['code']}: quantité partielle, {qty_restante} unité(s) non réparties"
                )

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
            #         self.logger.error(f" {msg}")
            #         return False
            #     else:
            #         self.logger.info(f"{msg}")
            #         return True
            # except:
            #     self.logger.info("Enregistré")
            #     return True
            time.sleep(4)
            s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
            s_page_close.click()
            time.sleep(2)
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
            wait = WebDriverWait(driver, 2)
            dialog = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "s_alertbox")))

            # Cliquer sur OK
            ok_button = dialog.find_element(By.LINK_TEXT, "OK")
            ok_button.click()
            self.logger.info("Popup 'Oui' cliquée")
            time.sleep(1)
        except:
            # Pas de popup
            pass