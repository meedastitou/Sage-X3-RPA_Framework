# -*- coding: utf-8 -*-
"""
Module BonneCommand - Robot principal OPTIMISÉ avec VALIDATION STRICTE
Si UN SEUL échec → ARRÊT COMPLET, pas de génération de BC
Envoi automatique des résultats vers endpoint web
"""
from typing import Dict, Any, List
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from collections import defaultdict

from core.base_robot import BaseRobot
from core.web_result_mixin import WebResultMixin
from utils.excel_handler import ExcelHandler


class BonneCommandeRobot(BaseRobot, WebResultMixin):
    """Robot pour la gestion automatique des bons de commande avec validation stricte et envoi web"""
    
    def __init__(self, headless: bool = False):
        """
        Initialiser le robot bonne de commande
        
        Args:
            headless: Mode sans interface
        """
        # Initialiser BaseRobot
        BaseRobot.__init__(self, 'bonne_commande')
        
        # Initialiser WebResultMixin
        WebResultMixin.__init__(self)
        
        self.excel_handler = ExcelHandler()
        self.driver_manager.headless = headless
        
        # URLs des modules
        self.url_article = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESITM%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%278ecdb3d1-8ca7-40ca-af08-76cb58c70740~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"
        self.url_demande_achat = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DGESPSH%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%278ecdb3d1-8ca7-40ca-af08-76cb58c70740~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"
        self.url_bonne_commande = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DXBCAUTO%252F2%252F%252FM%252F"

        # Compteurs pour validation stricte
        self.articles_traites = 0
        self.articles_echec = 0
        self.das_traitees = 0
        self.das_echec = 0
        self.validation_passed = False
        
        self.logger.info(f"🤖 Robot Bonne de Commande initialisé (MODE STRICT + ENVOI WEB)")
    
    def execute(self, excel_file: str, url: str = None):
        """
        Exécuter le traitement des bons de commande avec validation stricte
        
        Args:
            excel_file: Chemin du fichier Excel
            url: URL (non utilisé, gardé pour compatibilité)
        """
        try:
            # 1. LIRE ET VALIDER L'EXCEL
            df = self._lire_et_valider_excel(excel_file)
            
            # 2. REGROUPER LES DONNÉES PAR STRUCTURE
            structure_donnees = self._regrouper_donnees(df)
            
            # 3. AFFICHER LE RÉSUMÉ
            self._afficher_resume(structure_donnees)
            
            # 4. CONNEXION SAGE
            self.connect_sage()
            
            # 5. PHASE 1 : TRAITER LES ARTICLES (VALIDATION STRICTE)
            self.logger.info("\n" + "="*80)
            self.logger.info("🔧 PHASE 1 : TRAITEMENT DES ARTICLES (MODE STRICT)")
            self.logger.info("="*80)
            articles_ok = self._traiter_tous_articles(structure_donnees)
            
            if not articles_ok:
                self.logger.error("\n" + "="*80)
                self.logger.error("❌ ÉCHEC PHASE 1 : Au moins un article en erreur")
                self.logger.error("❌ ARRÊT DU PROCESSUS - BC NON GÉNÉRÉ")
                self.logger.error("="*80)
                
                # Ajouter un résultat final d'échec
                self.add_result({
                    'type': 'BILAN_FINAL',
                    'phase': 'Articles',
                    'statut': 'ECHEC',
                    'articles_traites': self.articles_traites,
                    'articles_echec': self.articles_echec,
                    'das_traitees': 0,
                    'das_echec': 0,
                    'bc_genere': False,
                    'message': f'Échec lors du traitement des articles ({self.articles_echec} échec(s)). BC non généré.'
                })
                self.save_report()
                
                # ✨ ENVOYER LES RÉSULTATS VERS LE WEB
                self.send_results_to_web()
                
                return
            
            # 6. PHASE 2 : TRAITER LES DEMANDES D'ACHAT (VALIDATION STRICTE)
            self.logger.info("\n" + "="*80)
            self.logger.info("📋 PHASE 2 : TRAITEMENT DES DEMANDES D'ACHAT (MODE STRICT)")
            self.logger.info("="*80)
            das_ok = self._traiter_toutes_das(structure_donnees)
            
            if not das_ok:
                self.logger.error("\n" + "="*80)
                self.logger.error("❌ ÉCHEC PHASE 2 : Au moins une DA en erreur")
                self.logger.error("❌ ARRÊT DU PROCESSUS - BC NON GÉNÉRÉ")
                self.logger.error("="*80)
                
                # Ajouter un résultat final d'échec
                self.add_result({
                    'type': 'BILAN_FINAL',
                    'phase': 'Demandes_Achat',
                    'statut': 'ECHEC',
                    'articles_traites': self.articles_traites,
                    'articles_echec': self.articles_echec,
                    'das_traitees': self.das_traitees,
                    'das_echec': self.das_echec,
                    'bc_genere': False,
                    'message': f'Échec lors du traitement des DAs ({self.das_echec} échec(s)). BC non généré.'
                })
                self.save_report()
                
                # ✨ ENVOYER LES RÉSULTATS VERS LE WEB
                self.send_results_to_web()
                
                return
            
            # 7. TOUT EST OK → GÉNÉRER LE BON DE COMMANDE
            self.logger.info("\n" + "="*80)
            self.logger.info("✅ VALIDATION COMPLÈTE RÉUSSIE")
            self.logger.info("="*80)
            self.logger.info(f"✅ Articles traités avec succès: {self.articles_traites}/{self.articles_traites + self.articles_echec}")
            self.logger.info(f"✅ DAs traitées avec succès: {self.das_traitees}/{self.das_traitees + self.das_echec}")
            
            # TODO: Ajouter ici la logique de génération de BC
            bc_genere = self._generer_bon_de_commande(structure_donnees)
            
            # Ajouter un résultat final de succès
            self.add_result({
                'type': 'BILAN_FINAL',
                'phase': 'Complete',
                'statut': 'SUCCES',
                'articles_traites': self.articles_traites,
                'articles_echec': self.articles_echec,
                'das_traitees': self.das_traitees,
                'das_echec': self.das_echec,
                'bc_genere': bc_genere,
                'message': 'Tous les traitements réussis. BC généré avec succès.' if bc_genere else 'Traitements réussis mais erreur génération BC.'
            })
            
            self.save_report()
            
            self.logger.info("\n" + "="*80)
            self.logger.info("🎉 PROCESSUS TERMINÉ AVEC SUCCÈS")
            self.logger.info("="*80)
            
            self.validation_passed = True
            
            # ✨ ENVOYER LES RÉSULTATS VERS LE WEB
            web_result = self.send_results_to_web()
            
            if web_result and web_result.get('success'):
                self.logger.info("✅ Résultats envoyés vers l'endpoint web avec succès")
            elif web_result and not web_result.get('success'):
                self.logger.warning(f"⚠️ Échec envoi web: {web_result.get('message')}")
            
        except Exception as e:
            self.logger.error(f"\n❌ ERREUR CRITIQUE: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            # Ajouter un résultat d'erreur critique
            self.add_result({
                'type': 'BILAN_FINAL',
                'phase': 'Erreur_Critique',
                'statut': 'ERREUR',
                'articles_traites': self.articles_traites,
                'articles_echec': self.articles_echec,
                'das_traitees': self.das_traitees,
                'das_echec': self.das_echec,
                'bc_genere': False,
                'message': f'Erreur critique: {str(e)}'
            })
            
            self.save_report()
            
            # ✨ ENVOYER LES RÉSULTATS (même en cas d'erreur)
            self.send_results_to_web()
    
    def _lire_et_valider_excel(self, excel_file: str) -> pd.DataFrame:
        """Lire et valider le fichier Excel"""
        self.logger.info("="*80)
        self.logger.info("📖 LECTURE DU FICHIER EXCEL")
        self.logger.info("="*80)
        
        df = self.excel_handler.read_excel(
            excel_file,
            required_columns=[
                'Numero_DA', 
                'Acheteur', 
                'Code_Fournisseur',
                'Email_Fournisseur',
                'TEL_Fournisseu', 
                'Code_Article', 
                'Montant',
                'Marque',
                'Affaire'
            ]
        )
        
        self.logger.info(f"✅ {len(df)} lignes lues")
        
        # Vérifier les données vides
        lignes_invalides = []
        for idx, row in df.iterrows():
            colonnes_vides = []
            for col in ['Numero_DA', 'Code_Fournisseur', 'Code_Article', 'Montant', 'Marque']:
                if pd.isna(row[col]) or str(row[col]).strip() == '':
                    colonnes_vides.append(col)
            
            if colonnes_vides:
                lignes_invalides.append(idx)
                self.logger.warning(f"⚠️ Ligne {idx+1} ignorée - Colonnes vides: {', '.join(colonnes_vides)}")
        
        if lignes_invalides:
            df = df.drop(df.index[lignes_invalides])
            self.logger.warning(f"⚠️ {len(lignes_invalides)} ligne(s) invalide(s) ignorée(s)")
        
        self.logger.info(f"✅ {len(df)} lignes valides à traiter")
        return df
    
    def _regrouper_donnees(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Regrouper les données par Fournisseur → DA → Articles"""
        self.logger.info("="*80)
        self.logger.info("🔄 REGROUPEMENT DES DONNÉES")
        self.logger.info("="*80)
        
        fournisseur = df['Code_Fournisseur'].iloc[0]
        email = df['Email_Fournisseur'].iloc[0]
        tel = df['TEL_Fournisseu'].iloc[0]
        
        das = {}
        tous_articles = {}
        
        for _, row in df.iterrows():
            numero_da = str(row['Numero_DA'])
            acheteur = str(row['Acheteur'])
            code_article = str(row['Code_Article'])
            montant = str(row['Montant'])
            marque = str(row['Marque'])
            affaire = str(row['Affaire'])
            
            if numero_da not in das:
                das[numero_da] = {
                    'acheteur': acheteur,
                    'articles': []
                }
            
            das[numero_da]['articles'].append({
                'code': code_article,
                'montant': montant,
                'marque': marque,
                'affaire': affaire
            })
            
            if code_article not in tous_articles:
                tous_articles[code_article] = {
                    'montant': montant,
                    'fournisseur': fournisseur,
                    'marque': marque,
                    'affaire': affaire
                }
        
        structure = {
            'fournisseur': fournisseur,
            'email': email,
            'tel': tel,
            'das': das,
            'tous_articles': tous_articles
        }
        
        return structure
    
    def _afficher_resume(self, structure: Dict[str, Any]):
        """Afficher un résumé de la structure"""
        self.logger.info("="*80)
        self.logger.info("📊 RÉSUMÉ DU TRAITEMENT")
        self.logger.info("="*80)
        
        self.logger.info(f"\n🏢 Fournisseur: {structure['fournisseur']}")
        self.logger.info(f"   Email: {structure['email']}")
        self.logger.info(f"   Tél: {structure['tel']}")
        
        self.logger.info(f"\n📦 {len(structure['tous_articles'])} Article(s) unique(s) à traiter:")
        for article, info in structure['tous_articles'].items():
            self.logger.info(f"   • {article}: {info['montant']} MAD")
        
        self.logger.info(f"\n📋 {len(structure['das'])} Demande(s) d'Achat à traiter:")
        for da_num, da_info in structure['das'].items():
            self.logger.info(f"   • {da_num} ({da_info['acheteur']}): {len(da_info['articles'])} article(s)")
        
        self.logger.info("\n⚠️  MODE STRICT ACTIVÉ:")
        self.logger.info("   ✅ TOUS les articles doivent réussir")
        self.logger.info("   ✅ TOUTES les DAs doivent réussir")
        self.logger.info("   ❌ Un seul échec = Arrêt complet")
        self.logger.info("="*80)
    
    def _traiter_tous_articles(self, structure: Dict[str, Any]) -> bool:
        """Traiter tous les articles UNIQUES avec validation stricte"""
        self.navigate_to_module(self.url_article)
        time.sleep(2)
        
        total_articles = len(structure['tous_articles'])

        try: 
            for idx, (code_article, info_article) in enumerate(structure['tous_articles'].items(), 1):
                self.logger.info(f"\n{'─'*80}")
                self.logger.info(f"📦 Article {idx}/{total_articles}: {code_article}")
                self.logger.info(f"{'─'*80}")
                
                resultat = self.traiter_article(
                    code_article=code_article,
                    code_fournisseur=structure['fournisseur'],
                    montant=info_article['montant'],
                    marque=info_article.get('marque',''),
                    affaire=info_article.get('affaire','')
                )
                
                self.add_result(resultat)
                
                if resultat['statut'] == 'Succes':
                    self.articles_traites += 1
                    self.logger.info(f"✅ Article {code_article} traité avec succès ({self.articles_traites}/{total_articles})")
                else:
                    self.articles_echec += 1
                    self.logger.error(f"❌ ÉCHEC Article {code_article}: {resultat['message']}")
                    self.logger.error(f"❌ ARRÊT IMMÉDIAT - Article en échec détecté")
                    
                    self.save_report(incremental=True)
                    return False
                
                time.sleep(2)
        except Exception as e:
            self.logger.error(f"❌ ERREUR lors du traitement des articles: {e}")
            self.save_report(incremental=True)
            return False
        finally:
            self.logger.info(f"\n✅ Articles traités: {self.articles_traites}, Échecs: {self.articles_echec}")
            driver = self.driver_manager.driver

            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

            s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
            s_page_close.click()
            time.sleep(2)

        self.logger.info(f"\n✅ PHASE 1 RÉUSSIE: {self.articles_traites}/{total_articles} articles traités")
        self.save_report(incremental=True)
        return True
    
    def _traiter_toutes_das(self, structure: Dict[str, Any]) -> bool:
        """Traiter toutes les DAs UNIQUES avec validation stricte"""
        self.navigate_to_module(self.url_demande_achat)
        time.sleep(2)
        
        total_das = len(structure['das'])
        try:
            for idx, (numero_da, info_da) in enumerate(structure['das'].items(), 1):
                self.logger.info(f"\n{'─'*80}")
                self.logger.info(f"📋 DA {idx}/{total_das}: {numero_da}")
                self.logger.info(f"   Acheteur: {info_da['acheteur']}")
                self.logger.info(f"   Articles: {len(info_da['articles'])}")
                self.logger.info(f"{'─'*80}")
                
                resultat = self.traiter_demande_achat(
                    numero_da=numero_da,
                    acheteur=info_da['acheteur']
                )
                
                self.add_result(resultat)
                
                if resultat['statut'] == 'Succes':
                    self.das_traitees += 1
                    self.logger.info(f"✅ DA {numero_da} traitée avec succès ({self.das_traitees}/{total_das})")
                else:
                    self.das_echec += 1
                    self.logger.error(f"❌ ÉCHEC DA {numero_da}: {resultat['message']}")
                    self.logger.error(f"❌ ARRÊT IMMÉDIAT - DA en échec détectée")
                    
                    self.save_report(incremental=True)
                    return False
                
                time.sleep(2)
        except Exception as e:
            self.logger.error(f"❌ ERREUR lors du traitement des DAs: {e}")
            self.save_report(incremental=True)
            return False
        finally:
            self.logger.info(f"\n✅ DAs traitées: {self.das_traitees}, Échecs: {self.das_echec}")
            driver = self.driver_manager.driver

            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

            s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
            s_page_close.click()
            time.sleep(2)
        
        self.logger.info(f"\n✅ PHASE 2 RÉUSSIE: {self.das_traitees}/{total_das} DAs traitées")
        self.save_report(incremental=True)
        return True
    
    def _generer_bon_de_commande(self, structure: Dict[str, Any]) -> bool:
        """Générer la bonne de commande"""
        self.logger.info("="*80)
        self.logger.info("🧾 GÉNÉRATION DE LA BONNE DE COMMANDE")
        self.logger.info("="*80)
        
        driver = self.driver_manager.driver
        
        try:
            # Naviguer vers le module bonne de commande
            self.navigate_to_module(self.url_bonne_commande)
            # generation automatique de la BC
            time.sleep(60)
            # input("Appuyez sur Entrée après la génération automatique de la BC...")
            # bc_genereted = driver.find_element(By.ID, '2-75-input')
            # text_bc_generated = bc_genereted.text

            # numero_bc = text_bc_generated.split()[-1]

            # Télécharger la bonne de commande
            # button_telecharge = driver.find_element(By.CSS_SELECTOR, "div.s_tracker_btn_i.s_btn_i.s_sagearmonyeicon")
            # button_telecharge.click()

            # self.logger.info(f"✅ Bonne de commande générée: {numero_bc}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erreur génération bonne de commande: {e}")
            driver.save_screenshot("error_generation_bonne_commande.png")
            return False
        finally:
            self.logger.info("="*80)
            self.logger.info("🔒 Fermeture du module Bonne de Commande")
            driver = self.driver_manager.driver

            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

            s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
            s_page_close.click()
            time.sleep(2)
        
    def traiter_article(self, code_article: str, code_fournisseur: str, montant: str, marque: str, affaire: str) -> Dict[str, Any]:
        """
        Traiter un article (modifier fournisseur et tarif)
        
        Returns:
            Dictionnaire avec résultats
        """
        resultat = {
            'type': 'Article',
            'code_article': code_article,
            'code_fournisseur': code_fournisseur,
            'montant': montant,
            'marque': marque,
            'affaire': affaire,
            'statut': 'Echec',
            'message': ''
        }
        
        driver = self.driver_manager.driver
        
        try:
            
            
            # 1. Rechercher l'article
            self.logger.info(f"🔍 Recherche article: {code_article}")
            chercher_article = driver.find_element(By.ID, "2-565-input")
            chercher_article.click()
            time.sleep(0.5)
            chercher_article.clear()
            chercher_article.send_keys(code_article)
            chercher_article.send_keys(Keys.TAB)
            time.sleep(1)
            
            # 2. Cliquer sur l'article
            click_on_article = driver.find_element(By.CSS_SELECTOR, "div.s-inplace-value-read")
            click_on_article.click()
            time.sleep(1)


            # 0. verifier if BC_auto is checked
            BC_auto = driver.find_element(By.ID, "2-178-input")
            BC_auto_label = driver.find_element(By.CSS_SELECTOR, "label[for='2-178-input']")
            if BC_auto.is_selected():
                self.logger.info("BC_auto déjà cochée")
            else:
                BC_auto_label.click()
                self.logger.info("✅ BC_auto cochée")


            # 3. Modifier le fournisseur
            self.logger.info(f"🔄 Modification fournisseur: {code_fournisseur}")
            changer_fournisseur = driver.find_element(By.ID, "2-179-input")
            time.sleep(0.5)
            changer_fournisseur.click()
            time.sleep(0.5)
            changer_fournisseur.clear()
            changer_fournisseur.send_keys(code_fournisseur)
            changer_fournisseur.send_keys(Keys.TAB)
            time.sleep(1)

            # 4. Modifier l'affaire
            self.logger.info(f"🔄 Modification affaire: {affaire}")
            if not(affaire == 'nan' or affaire.strip() == ''):
                changer_affaire = driver.find_element(By.ID, "2-180-input")
                time.sleep(0.5)
                changer_affaire.click()
                time.sleep(0.5)
                changer_affaire.clear()
                changer_affaire.send_keys(affaire)
                changer_affaire.send_keys(Keys.TAB)
                time.sleep(1)
            

            # 5. Modifier le tarif
            self.logger.info(f"💰 Modification tarif: {montant}")
            change_tarif = driver.find_element(By.ID, "2-181-input")
            change_tarif.click()
            time.sleep(0.5)
            change_tarif.clear()
            change_tarif.send_keys(montant)
            change_tarif.send_keys(Keys.TAB)
            time.sleep(1)

            elements_existe = len(driver.find_elements(By.CSS_SELECTOR, "article.s_alertbox_content")) > 0

            if elements_existe:
                pre_elements = driver.find_elements(By.CSS_SELECTOR, "pre.s_alertbox_msg")
                error_message = pre_elements[0].text
                resultat['message'] = f'Tarif non valide de l\'article {code_article} (valeur: {montant}) \n {error_message}'
                self.logger.error(f"❌ {resultat['message']}")
                return resultat

            # 6. Modifier la marque
            self.logger.info(f"💰 Modification marque: {marque}")
            change_marque = driver.find_element(By.ID, "2-182-input")
            change_marque.click()
            time.sleep(0.5)
            change_marque.clear()
            change_marque.send_keys(marque)
            change_marque.send_keys(Keys.TAB)
            time.sleep(1)

            # 7. Enregistrer
            if self.enregistrer_article():
                resultat['statut'] = 'Succes'
                resultat['message'] = 'Article traité avec succès'
                self.logger.info(f"✅ Article {code_article} traité")
            else:
                resultat['message'] = 'Erreur lors de l\'enregistrement'
            time.sleep(20)
        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f"❌ Erreur traitement article: {e}")
        finally:
            pass
        return resultat
    
    def traiter_demande_achat(self, numero_da: str, acheteur: str) -> Dict[str, Any]:
        """
        Traiter une demande d'achat
        
        Returns:
            Dictionnaire avec résultats
        """
        resultat = {
            'type': 'Demande_Achat',
            'numero_da': numero_da,
            'acheteur': acheteur,
            'statut': 'Echec',
            'message': ''
        }
        
        driver = self.driver_manager.driver
        
        try:

            # 1. Rechercher la DA
            self.logger.info(f"🔍 Recherche DA: {numero_da}")
            chercher_da = driver.find_element(By.ID, "2-109-input")
            chercher_da.click()
            time.sleep(0.5)
            chercher_da.clear()
            chercher_da.send_keys(numero_da)
            chercher_da.send_keys(Keys.TAB)
            time.sleep(1)
            
            # 2. Cliquer sur la DA
            click_on_da = driver.find_element(By.CSS_SELECTOR, "div.s-inplace-value-read")
            click_on_da.click()
            time.sleep(1)
            
            # 3. Validation acheteur
            self.logger.info(f"✅ Validation acheteur: {acheteur}")
            validation_acheteur = driver.find_element(By.ID, "2-80-input")
            label_validation_acheteur = driver.find_element(By.CSS_SELECTOR, "label[for='2-80-input']")
            if validation_acheteur.is_selected():
                self.logger.info("✅ 1 - Case cochée")
            else:
                label_validation_acheteur.click()
                self.logger.info("✅ 2 - Case cochée")
                # elements_existe = len(driver.find_elements(By.CSS_SELECTOR, "article.s_alertbox_content")) > 0

                # if elements_existe:
                #     pre_elements = driver.find_elements(By.CSS_SELECTOR, "pre.s_alertbox_msg")
                #     error_message = pre_elements[0].text
                #     resultat['message'] = f'Erreur validation acheteur DA {numero_da} \n {error_message}'
                #     self.logger.error(f"❌ {resultat['message']}")
                #     return resultat
    
                self.logger.info("Case déjà cochée")

            time.sleep(1)

            # 4. Enregistrer
            if self.enregistrer_demande_achat():
                resultat['statut'] = 'Succes'
                resultat['message'] = 'DA traitée avec succès'
                self.logger.info(f"✅ DA {numero_da} traitée")
            else:
                resultat['message'] = 'Erreur lors de l\'enregistrement'
            time.sleep(20)
        except Exception as e:
            resultat['message'] = f'Erreur: {str(e)}'
            self.logger.error(f"❌ Erreur traitement DA: {e}")
        
        return resultat
    
    def enregistrer_article(self) -> bool:
        """Enregistrer les modifications de l'article"""
        driver = self.driver_manager.driver
        
        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_save")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()

            time.sleep(2)
            s_lock_long_spinners = len(driver.find_elements(By.CSS_SELECTOR, "div.s_lock_long_spin")) > 0
            if s_lock_long_spinners:
                WebDriverWait(driver, 30).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.s_lock_long_spin"))
                )
                self.logger.info("⏳ Attente de la fin du chargement...")
            # time.sleep(30)
            
            self.logger.info("💾 Enregistrement article...")
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur enregistrement article: {e}")
            driver.save_screenshot("error_enregistrement_article.png")
            return False
    
    def enregistrer_demande_achat(self) -> bool:
        """Enregistrer les modifications de la DA"""
        driver = self.driver_manager.driver
        
        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_save")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            
            save_btn.click()
            self.logger.info("💾 Enregistrement DA...")
            time.sleep(2)
            
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur enregistrement DA: {e}")
            driver.save_screenshot("error_enregistrement_da.png")
            return False

