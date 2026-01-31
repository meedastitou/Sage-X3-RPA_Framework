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
import re


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
        email_achteur=""
        try:
            # 1. LIRE ET VALIDER L'EXCEL
            df = self._lire_et_valider_excel(excel_file)
            email_achteur = df.iloc[0]['email_expediteur']

            # 2. REGROUPER LES DONNÉES PAR FOURNISSEUR
            fournisseurs = self._regrouper_donnees(df)

            # 3. AFFICHER LE RÉSUMÉ
            self._afficher_resume(fournisseurs)

            # 4. CONNEXION SAGE
            self.connect_sage()

            # 5. TRAITER CHAQUE FOURNISSEUR SÉPARÉMENT
            for idx_fournisseur, (code_fournisseur, data_fournisseur) in enumerate(fournisseurs.items(), 1):
                self.logger.info("" + "="*80)
                self.logger.info(f"🏢 TRAITEMENT FOURNISSEUR {idx_fournisseur}/{len(fournisseurs)}: {code_fournisseur}")
                self.logger.info("="*80)

                # Réinitialiser les compteurs et résultats pour ce fournisseur
                self.articles_traites = 0
                self.articles_echec = 0
                self.das_traitees = 0
                self.das_echec = 0
                self.validation_passed = False
                self.bc_numbers = []
                self.message_final = ""

                # IMPORTANT: Vider les résultats précédents pour ce nouveau fournisseur
                self.results = []

                # IMPORTANT: Réinitialiser les erreurs du fournisseur précédent
                self.error_screenshot = None
                self.popup_messages = []

                # PHASE 1 : TRAITER LES ARTICLES DE CE FOURNISSEUR
                self.logger.info("="*80)
                self.logger.info(f"🔧 PHASE 1 : TRAITEMENT DES ARTICLES - Fournisseur {code_fournisseur}")
                self.logger.info("="*80)
                articles_ok = self._traiter_tous_articles(data_fournisseur)

                if not articles_ok:
                    self.logger.error("" + "="*80)
                    self.logger.error(f"❌ ÉCHEC PHASE 1 pour fournisseur {code_fournisseur}")
                    self.logger.error("❌ ARRÊT DU PROCESSUS - BC NON GÉNÉRÉ pour ce fournisseur")
                    self.logger.error("="*80)

                    # Ajouter un résultat final d'échec pour ce fournisseur
                    self.add_result({
                        'type': 'BILAN_FINAL',
                        'fournisseur': code_fournisseur,
                        'phase': 'Articles',
                        'statut': 'ECHEC',
                        'articles_traites': self.articles_traites,
                        'articles_echec': self.articles_echec,
                        'das_traitees': 0,
                        'das_echec': 0,
                        'bc_genere': False,
                        'message': f'Échec lors du traitement des articles pour fournisseur {code_fournisseur} ({self.articles_echec} échec(s)). BC non généré.'
                    })
                    self.save_report()

                    # ✨ ENVOYER LES RÉSULTATS VERS LE WEB MÊME EN CAS D'ÉCHEC
                    self.logger.info("✨ Envoi des résultats vers l'endpoint web...")
                    web_result = self.send_results_to_web(email_achteur)
                    if web_result and web_result.get('success'):
                        self.logger.info("✅ Résultats envoyés vers l'endpoint web avec succès")
                    elif web_result and not web_result.get('success'):
                        self.logger.warning(f"⚠️ Échec envoi web: {web_result.get('message')}")

                    continue  # Passer au fournisseur suivant

                # PHASE 2 : TRAITER LES DEMANDES D'ACHAT DE CE FOURNISSEUR
                self.logger.info("" + "="*80)
                self.logger.info(f"📋 PHASE 2 : TRAITEMENT DES DEMANDES D'ACHAT - Fournisseur {code_fournisseur}")
                self.logger.info("="*80)
                das_ok = self._traiter_toutes_das(data_fournisseur)

                if not das_ok:
                    self.logger.error("" + "="*80)
                    self.logger.error(f"❌ ÉCHEC PHASE 2 pour fournisseur {code_fournisseur}")
                    self.logger.error("❌ ARRÊT DU PROCESSUS - BC NON GÉNÉRÉ pour ce fournisseur")
                    self.logger.error("="*80)

                    # Ajouter un résultat final d'échec pour ce fournisseur
                    self.add_result({
                        'type': 'BILAN_FINAL',
                        'fournisseur': code_fournisseur,
                        'phase': 'Demandes_Achat',
                        'statut': 'ECHEC',
                        'articles_traites': self.articles_traites,
                        'articles_echec': self.articles_echec,
                        'das_traitees': self.das_traitees,
                        'das_echec': self.das_echec,
                        'bc_genere': False,
                        'message': f'Échec lors du traitement des DAs pour fournisseur {code_fournisseur} ({self.das_echec} échec(s)). BC non généré.'
                    })
                    self.save_report()

                    # ✨ ENVOYER LES RÉSULTATS VERS LE WEB MÊME EN CAS D'ÉCHEC
                    self.logger.info("✨ Envoi des résultats vers l'endpoint web...")
                    web_result = self.send_results_to_web(email_achteur)
                    if web_result and web_result.get('success'):
                        self.logger.info("✅ Résultats envoyés vers l'endpoint web avec succès")
                    elif web_result and not web_result.get('success'):
                        self.logger.warning(f"⚠️ Échec envoi web: {web_result.get('message')}")

                    continue  # Passer au fournisseur suivant

                # PHASE 3 : GÉNÉRER LE BON DE COMMANDE POUR CE FOURNISSEUR
                self.logger.info("" + "="*80)
                self.logger.info(f"✅ VALIDATION COMPLÈTE RÉUSSIE - Fournisseur {code_fournisseur}")
                self.logger.info("="*80)
                self.logger.info(f"✅ Articles traités avec succès: {self.articles_traites}/{self.articles_traites + self.articles_echec}")
                self.logger.info(f"✅ DAs traitées avec succès: {self.das_traitees}/{self.das_traitees + self.das_echec}")

                bc_numbers = self._generer_bon_de_commande(data_fournisseur)
                bc_genere = len(bc_numbers) > 0

                # Déterminer le statut final basé sur la génération de BC
                statut_final = 'SUCCES' if bc_genere else 'ECHEC'
                message_final = f'Tous les traitements réussis pour fournisseur {code_fournisseur}. BC généré avec succès: {bc_numbers}' if bc_genere else f'Articles et DAs traités avec succès pour fournisseur {code_fournisseur} mais échec de génération BC.'

                # Mettre à jour validation_passed pour ce fournisseur
                self.validation_passed = bc_genere

                # Stocker bc_numbers et message_final pour l'envoi web
                self.bc_numbers = bc_numbers
                self.message_final = message_final

                # Ajouter un résultat final pour ce fournisseur
                self.add_result({
                    'type': 'BILAN_FINAL',
                    'fournisseur': code_fournisseur,
                    'phase': 'Complete',
                    'statut': statut_final,
                    'articles_traites': self.articles_traites,
                    'articles_echec': self.articles_echec,
                    'das_traitees': self.das_traitees,
                    'das_echec': self.das_echec,
                    'bc_genere': bc_genere,
                    'bc_numbers': bc_numbers,
                    'message': message_final
                })

                self.save_report()

                # ✨ ENVOYER LES RÉSULTATS VERS LE WEB APRÈS CHAQUE FOURNISSEUR
                self.logger.info("✨ Envoi des résultats vers l'endpoint web...")
                web_result = self.send_results_to_web(email_achteur)

                if web_result and web_result.get('success'):
                    self.logger.info("✅ Résultats envoyés vers l'endpoint web avec succès")
                elif web_result and not web_result.get('success'):
                    self.logger.warning(f"⚠️ Échec envoi web: {web_result.get('message')}")

                self.logger.info("" + "="*80)
                self.logger.info(f"🎉 FOURNISSEUR {code_fournisseur} TRAITÉ AVEC SUCCÈS")
                self.logger.info("="*80)

            # FIN DU TRAITEMENT DE TOUS LES FOURNISSEURS
            self.logger.info("" + "="*80)
            self.logger.info("🎉 TOUS LES FOURNISSEURS ONT ÉTÉ TRAITÉS")
            self.logger.info("="*80)

            self.validation_passed = True

        except Exception as e:
            self.logger.error(f"❌ ERREUR CRITIQUE: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

            # Capturer screenshot et popup en cas d'erreur critique
            error_info = self.handle_error_with_screenshot(
                error_message=str(e),
                context="Erreur Critique - Execute"
            )

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
                'message': f'Erreur critique: {str(e)}',
                'error_info': error_info
            })

            self.save_report()

            # ✨ ENVOYER LES RÉSULTATS (même en cas d'erreur)
            self.logger.info("✨ Envoi des résultats vers l'endpoint web malgré l'erreur critique...")
            self.send_results_to_web(email_achteur)
        
        finally:
            self.logger.info("Deconnexion du robot...")
            self.disconnect_sage()
    
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
        self.logger.info("🔄 REGROUPEMENT DES DONNÉES PAR FOURNISSEUR")
        self.logger.info("="*80)

        # Structure: {code_fournisseur: {email, tel, das, tous_articles}}
        fournisseurs = {}

        for _, row in df.iterrows():
            code_fournisseur = str(row['Code_Fournisseur'])
            email = str(row['Email_Fournisseur'])
            tel = str(row['TEL_Fournisseu'])
            numero_da = str(row['Numero_DA'])
            acheteur = str(row['Acheteur'])
            code_article = str(row['Code_Article'])
            montant = str(row['Montant'])
            marque = str(row['Marque'])
            affaire = str(row['Affaire'])

            # Initialiser le fournisseur s'il n'existe pas
            if code_fournisseur not in fournisseurs:
                fournisseurs[code_fournisseur] = {
                    'fournisseur': code_fournisseur,
                    'email': email,
                    'tel': tel,
                    'das': {},
                    'tous_articles': {}
                }

            # Ajouter la DA si elle n'existe pas pour ce fournisseur
            if numero_da not in fournisseurs[code_fournisseur]['das']:
                fournisseurs[code_fournisseur]['das'][numero_da] = {
                    'acheteur': acheteur,
                    'articles': []
                }

            # Ajouter l'article à la DA
            fournisseurs[code_fournisseur]['das'][numero_da]['articles'].append({
                'code': code_article,
                'montant': montant,
                'marque': marque,
                'affaire': affaire
            })

            # Ajouter l'article unique pour ce fournisseur
            if code_article not in fournisseurs[code_fournisseur]['tous_articles']:
                fournisseurs[code_fournisseur]['tous_articles'][code_article] = {
                    'montant': montant,
                    'fournisseur': code_fournisseur,
                    'marque': marque,
                    'affaire': affaire
                }

        return fournisseurs
    
    def _afficher_resume(self, fournisseurs: Dict[str, Any]):
        """Afficher un résumé de la structure par fournisseur"""
        self.logger.info("="*80)
        self.logger.info("📊 RÉSUMÉ DU TRAITEMENT")
        self.logger.info("="*80)

        self.logger.info(f"🏢 Nombre de fournisseurs: {len(fournisseurs)}")

        for code_fournisseur, data in fournisseurs.items():
            self.logger.info(f"{'─'*80}")
            self.logger.info(f"🏢 Fournisseur: {code_fournisseur}")
            self.logger.info(f"   Email: {data['email']}")
            self.logger.info(f"   Tél: {data['tel']}")

            self.logger.info(f"📦 {len(data['tous_articles'])} Article(s) unique(s) à traiter:")
            for article, info in data['tous_articles'].items():
                self.logger.info(f"   • {article}: {info['montant']} MAD")

            self.logger.info(f"📋 {len(data['das'])} Demande(s) d'Achat à traiter:")
            for da_num, da_info in data['das'].items():
                self.logger.info(f"   • {da_num} ({da_info['acheteur']}): {len(da_info['articles'])} article(s)")

        self.logger.info(f"{'─'*80}")
        self.logger.info("⚠️  MODE STRICT ACTIVÉ:")
        self.logger.info("   ✅ TOUS les articles doivent réussir")
        self.logger.info("   ✅ TOUTES les DAs doivent réussir")
        self.logger.info("   ❌ Un seul échec = Arrêt complet")
        self.logger.info("="*80)
    
    def _traiter_tous_articles(self, structure: Dict[str, Any]) -> bool:
        """Traiter tous les articles UNIQUES avec validation stricte"""
        self.navigate_to_module(self.url_article)
        time.sleep(5)

        driver = self.driver_manager.driver
        self.wait_for_spinner_to_disappear(driver, timeout=90000)

        total_articles = len(structure['tous_articles'])

        try: 
            for idx, (code_article, info_article) in enumerate(structure['tous_articles'].items(), 1):
                self.logger.info(f"{'─'*80}")
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
            
            self.logger.info(f"✅ Articles traités: {self.articles_traites}, Échecs: {self.articles_echec}")
            driver = self.driver_manager.driver

            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

            s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
            s_page_close.click()
            time.sleep(2)

        self.logger.info(f"✅ PHASE 1 RÉUSSIE: {self.articles_traites}/{total_articles} articles traités")
        self.save_report(incremental=True)
        return True
    
    def _traiter_toutes_das(self, structure: Dict[str, Any]) -> bool:
        """Traiter toutes les DAs UNIQUES avec validation stricte"""
        self.navigate_to_module(self.url_demande_achat)
        time.sleep(5)

        driver = self.driver_manager.driver
        self.wait_for_spinner_to_disappear(driver, timeout=90000)

        total_das = len(structure['das'])
        try:
            for idx, (numero_da, info_da) in enumerate(structure['das'].items(), 1):
                self.logger.info(f"{'─'*80}")
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
            self.logger.info(f"✅ DAs traitées: {self.das_traitees}, Échecs: {self.das_echec}")
            driver = self.driver_manager.driver

            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)

            s_page_close = driver.find_element(By.CSS_SELECTOR, "a.s_page_close")
            s_page_close.click()
            time.sleep(2)
        
        self.logger.info(f"✅ PHASE 2 RÉUSSIE: {self.das_traitees}/{total_das} DAs traitées")
        self.save_report(incremental=True)
        return True
    
    def _generer_bon_de_commande(self, structure: Dict[str, Any]) -> List[str]:
        """Générer la bonne de commande et retourner la liste des numéros de BC"""
        self.logger.info("="*80)
        self.logger.info("🧾 GÉNÉRATION DE LA BONNE DE COMMANDE")
        self.logger.info("="*80)

        driver = self.driver_manager.driver

        try:
            
            # Naviguer vers le module bonne de commande
            self.navigate_to_module(self.url_bonne_commande)
            # generation automatique de la BC
            time.sleep(5)
            self.wait_for_spinner_to_disappear(driver, timeout=900000000)
            self.wait_for_element_to_appear(driver, By.CSS_SELECTOR, ".s-inplace-input.s-readonly", timeout=900000000)

            bc_inputs = driver.find_elements(By.CSS_SELECTOR, ".s-inplace-input.s-readonly")
            self.logger.info(f"Nombre d'inputs BC trouvés: {len(bc_inputs)}")
            bc_numbers = []
            for input_field in bc_inputs:
                value = input_field.get_attribute("value")
                self.logger.info(f"Valeur trouvée dans input BC: '{value}'")
                if value:
                    # Chercher le motif BC suivi de chiffres
                    match = re.search(r'BC(\d+)', value)
                    if match:
                        bc_number = match.group(1)  # Juste les chiffres
                        bc_numbers.append(bc_number)
                        self.logger.info(f"BC trouvé: {bc_number} dans: '{value}'")

            self.logger.info(f"Total BC trouvés: {len(bc_numbers)}")
            self.logger.info(f"Liste: {bc_numbers}")

            return bc_numbers

        except Exception as e:
            self.logger.error(f"❌ Erreur génération bonne de commande: {e}")

            # Capturer screenshot et popup en cas d'erreur
            error_info = self.handle_error_with_screenshot(
                error_message=str(e),
                context="Génération Bonne de Commande"
            )

            driver.save_screenshot("error_generation_bonne_commande.png")
            return []
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
            
            
            # 1. Trouver la section "Articles" 
            articles_section = driver.find_element(By.XPATH, 
                "//header[.//a[contains(text(), 'Articles')]]/following-sibling::div[1]"
            )
            table_head = articles_section.find_element(By.CLASS_NAME, "s-grid-table-head")

            # 2. Directement: trouver le premier input dans le deuxième tr
            filter_row = table_head.find_element(By.XPATH, ".//tr[2]")
            chercher_article = filter_row.find_element(By.XPATH, ".//td[1]//input")

            # 3. Rechercher l'article
            chercher_article.click()
            time.sleep(0.5)
            chercher_article.clear()
            chercher_article.send_keys(code_article)
            chercher_article.send_keys(Keys.TAB)
            time.sleep(1)

            table_body = articles_section.find_element(By.CLASS_NAME, "s-grid-table-body")

            # 4. Cliquer sur l'article
            premier_ligne_recherche = table_body.find_element(By.XPATH, ".//tr[1]")
            click_on_article = premier_ligne_recherche.find_element(By.XPATH, ".//td[1]//div")

            click_on_article.click()
            time.sleep(1)
            
            # 0. verifier if BC_auto is checked
            BC_auto_input = self.get_input_by_label("BC Auto.")
            BC_auto_label = driver.find_element(By.CSS_SELECTOR, f"label[for='{BC_auto_input.get_attribute('id')}']")
            if BC_auto_input.is_selected():
                self.logger.info("BC_auto déjà cochée")
            else:
                BC_auto_label.click()
                self.logger.info("✅ BC_auto cochée")
            

            # 3. Modifier le fournisseur
            self.logger.info(f"🔄 Modification fournisseur: {code_fournisseur}")
            changer_fournisseur = self.get_input_by_label("Fournisseur")
            time.sleep(0.5)
            changer_fournisseur.click()
            time.sleep(0.5)
            changer_fournisseur.clear()
            changer_fournisseur.send_keys(code_fournisseur)
            if(changer_fournisseur.get_attribute('value').strip() != code_fournisseur):
                resultat['message'] = f'Erreur de format du code fournisseur pour l\'article {code_article} (valeur: {code_fournisseur})'
                self.logger.error(f"❌ {resultat['message']}")
                return resultat
            changer_fournisseur.send_keys(Keys.TAB)
            time.sleep(1)

            # 4. Modifier l'affaire
            self.logger.info(f"🔄 Modification affaire: {affaire}")
            if not(affaire == 'nan' or affaire.strip() == ''):
                changer_affaire = self.get_input_by_label("Affaire")
                time.sleep(0.5)
                changer_affaire.click()
                time.sleep(0.5)
                changer_affaire.clear()
                changer_affaire.send_keys(affaire)
                changer_affaire.send_keys(Keys.TAB)
                time.sleep(1)
            

            # 5. Modifier le tarif
            # prend juste 4 chiffres apres la virgule
            montant = f"{float(montant):.4f}"
            self.logger.info(f"💰 Modification Prix: {montant}")
            change_tarif = self.get_input_by_label("Prix")
            change_tarif.click()
            time.sleep(0.5)
            change_tarif.clear()
            change_tarif.send_keys(montant)
            # if(change_tarif.get_attribute('value').replace(',','.').strip() != montant):
            #     resultat['message'] = f'Erreur de format du tarif pour l\'article {code_article} (valeur: {montant})'
            #     self.logger.error(f"❌ {resultat['message']}")
            #     return resultat
            change_tarif.send_keys(Keys.TAB)
            time.sleep(1)

            elements_existe = len(driver.find_elements(By.CSS_SELECTOR, "article.s_alertbox_content")) > 0

            if elements_existe:
                pre_elements = driver.find_elements(By.CSS_SELECTOR, "pre.s_alertbox_msg")
                error_message = pre_elements[0].text
                resultat['message'] = f'Tarif non valide de l\'article {code_article} (valeur: {montant}) \n {error_message}'
                self.logger.error(f"❌ {resultat['message']}")

                # Capturer screenshot et popup
                error_info = self.handle_error_with_screenshot(
                    error_message=resultat['message'],
                    context=f"Article {code_article} - Validation tarif"
                )
                resultat['error_info'] = error_info

                return resultat

            # 6. Modifier la marque
            self.logger.info(f"💰 Modification marque: {marque}")
            change_marque = self.get_input_by_label("Marque")
            change_marque.click()
            time.sleep(0.5)
            change_marque.clear()
            change_marque.send_keys(marque)
            if(change_marque.get_attribute('value').strip() != marque.strip()):
                resultat['message'] = f'Erreur de format de la marque pour l\'article {code_article} (valeur: {marque})'
                self.logger.error(f"❌ {resultat['message']}")
                return resultat
            change_marque.send_keys(Keys.TAB)
            time.sleep(1)
            
            self.logger.info(f"✅ Marque modifiée: {marque}")
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

            # Capturer screenshot et popup en cas d'exception
            error_info = self.handle_error_with_screenshot(
                error_message=str(e),
                context=f"Article {code_article} - Exception"
            )
            resultat['error_info'] = error_info
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

             # 1. Trouver la section "Demandes d'Achat" 
            demmande_achat_section = driver.find_element(By.XPATH, 
                "//header[.//a[contains(text(), 'Demandes')]]/following-sibling::div[1]"
            )
            table_head = demmande_achat_section.find_element(By.CLASS_NAME, "s-grid-table-head")

            # 2. Directement: trouver le premier input dans le deuxième tr
            filter_row = table_head.find_element(By.XPATH, ".//tr[2]")
            chercher_da = filter_row.find_element(By.XPATH, ".//td[2]//input")

            # 3. Rechercher l'article
            chercher_da.click()
            time.sleep(0.5)
            chercher_da.clear()
            chercher_da.send_keys(numero_da)
            chercher_da.send_keys(Keys.TAB)
            time.sleep(1)

            table_body = demmande_achat_section.find_element(By.CLASS_NAME, "s-grid-table-body")

            # 4. Cliquer sur l'article
            premier_ligne_recherche = table_body.find_element(By.XPATH, ".//tr[1]")
            click_on_da = premier_ligne_recherche.find_element(By.XPATH, ".//td[2]//div")

            click_on_da.click()
            time.sleep(1)
            

            # 3. Validation acheteur
            self.logger.info(f"✅ Validation acheteur: {acheteur}")
            validation_acheteur = self.get_input_by_label("Validation Acheteur")
            label_validation_acheteur = driver.find_element(By.CSS_SELECTOR, f"label[for='{validation_acheteur.get_attribute('id')}']")
            if validation_acheteur.is_selected():
                self.logger.info("✅ 1 - Case deja cochée")
            else:
                label_validation_acheteur.click()
                self.logger.info("✅ 2 - Case cochée")

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

            # Capturer screenshot et popup en cas d'exception
            error_info = self.handle_error_with_screenshot(
                error_message=str(e),
                context=f"DA {numero_da} - Exception"
            )
            resultat['error_info'] = error_info

        return resultat
    
    def enregistrer_article(self) -> bool:
        """Enregistrer les modifications de l'article"""
        driver = self.driver_manager.driver
        
        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_save")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            save_btn.click()

            time.sleep(5)

            self.wait_for_spinner_to_disappear(driver, timeout=6000)
            
            self.logger.info("💾 Enregistrement article...")
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur enregistrement article: {e}")

            # Capturer screenshot et popup en cas d'erreur
            self.handle_error_with_screenshot(
                error_message=str(e),
                context="Enregistrement Article"
            )

            driver.save_screenshot("screenShots/error_enregistrement_article.png")
            return False
    
    def enregistrer_demande_achat(self) -> bool:
        """Enregistrer les modifications de la DA"""
        driver = self.driver_manager.driver
        
        try:
            save_btn = driver.find_element(By.CSS_SELECTOR, "div.s_page_action_i.s_page_action_i_save")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_btn)
            time.sleep(0.5)
            
            save_btn.click()
            time.sleep(5)
            self.wait_for_spinner_to_disappear(driver, timeout=60000)
            self.logger.info("💾 Enregistrement DA...")
            
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur enregistrement DA: {e}")

            # Capturer screenshot et popup en cas d'erreur
            self.handle_error_with_screenshot(
                error_message=str(e),
                context="Enregistrement DA"
            )

            driver.save_screenshot("error_enregistrement_da.png")
            return False

