# -*- coding: utf-8 -*-
"""
Module Signature DA - Robot pour la signature des articles/Demandes d'Achat Sage X3
"""
import os
from typing import Dict, Any
import pandas as pd
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

from core.base_robot import BaseRobot
from core.web_result_mixin import WebResultMixin
from utils.excel_handler import ExcelHandler
from config.settings import GENERATION_BC

class SignatureDARobot(BaseRobot, WebResultMixin):
    """Robot pour la signature automatique des articles/Demandes d'Achat (DA)"""
    WEBHOOK_TIMEOUT = 15      # secondes
    WEBHOOK_MAX_TENTATIVES = 3
    def __init__(self, headless: bool = False):
        """Initialiser le robot de signature DA"""
        BaseRobot.__init__(self, 'signature_da')  # -> déclenche Firefox via FIREFOX_MODULES
        WebResultMixin.__init__(self)

        self.excel_handler = ExcelHandler()
        self.driver_manager.headless = headless

        # Accès direct à l'écran "Consultation demandes d'achat" (CONSCPD)
        # -> plus besoin de passer par Articles + menu "..." > Achats > Demandes
        self.url_demande_achat = "http://192.168.1.241:8124/syracuse-main/html/main.html?url=%2Ftrans%2Fx3%2Ferp%2FBASE1%2F%24sessions%3Ff%3DCONSCPD%252F2%252F%252FM%252F%26profile%3D~(loc~%27fr-FR~role~%279844eacb-4f96-4301-8b0c-dbe4f4d48e4d~ep~%27cb006c17-58a5-4b98-9f2b-474ec03472a3~appConn~())"
        self.webhook_url  = os.path.join(GENERATION_BC['URL_WEBHOOK_GENERATION_BC'])
        
        # Compteurs
        self.articles_signes = 0
        self.articles_echec = 0
        self.articles_signes_liste = []   # DA signées, à envoyer au webhook à la fin



        self.logger.info("🤖 Robot Signature DA initialisé")

    # ------------------------------------------------------------------
    # LECTURE / VALIDATION EXCEL
    # ------------------------------------------------------------------
    def _lire_et_valider_excel(self, excel_file: str) -> pd.DataFrame:
        """Lire et valider le fichier Excel (code_article, numero_da, email_expediteur)"""
        self.logger.info("=" * 80)
        self.logger.info("📖 LECTURE DU FICHIER EXCEL - SIGNATURE DA")
        self.logger.info("=" * 80)

        df = self.excel_handler.read_excel(
            excel_file,
            required_columns=['code_article', 'numero_da', 'email_expediteur']
        )
        self.logger.info(f"✅ {len(df)} lignes lues")

        lignes_invalides = []
        for idx, row in df.iterrows():
            colonnes_vides = [
                col for col in ['code_article', 'numero_da']
                if pd.isna(row[col]) or str(row[col]).strip() == ''
            ]
            if colonnes_vides:
                lignes_invalides.append(idx)
                self.logger.warning(f"⚠️ Ligne {idx+1} ignorée - Colonnes vides: {', '.join(colonnes_vides)}")

        if lignes_invalides:
            df = df.drop(df.index[lignes_invalides])
            self.logger.warning(f"⚠️ {len(lignes_invalides)} ligne(s) invalide(s) ignorée(s)")

        self.logger.info(f"✅ {len(df)} lignes valides à traiter")
        return df

    # ------------------------------------------------------------------
    # SIGNATURE D'UN ARTICLE (accès direct : recherche DA -> coche Sig. -> Signature)
    # ------------------------------------------------------------------
    def _signer_da(self, numero_da: str, lignes: list) -> list:
        """lignes = [(code_article, email_expediteur), ...] pour UNE DA. Retourne une liste de résultats."""
        resultats = []
        codes_coches = []

        def _res(code, email, statut, message):
            return {'type': 'Signature_Article', 'code_article': code, 'numero_da': numero_da,
                    'email_expediteur': email, 'statut': statut, 'message': message}

        try:
            self._ouvrir_panneau_selection()
            self._rechercher_demande_achat(numero_da)
            time.sleep(5)
            self._cliquer_dir_up()

            for code, email in lignes:
                if self._cocher_signature_article(code):
                    codes_coches.append((code, email))
                else:
                    r = _res(code, email, 'Echec', f"Article {code} non trouvé dans la grille de la DA {numero_da}")
                    resultats.append(r)

            if codes_coches:
                self._cliquer_signature()
                if not self._confirmer_popup_signature():
                    raise Exception(f"Popup de confirmation signature non géré pour la DA {numero_da}")
                for code, email in codes_coches:
                    resultats.append(_res(code, email, 'Succes', 'Article signé avec succès'))
                    self.logger.info(f"✅ Article {code} (DA {numero_da}) signé")

        except Exception as e:
            self.logger.error(f"❌ Erreur signature DA {numero_da}: {e}")
            error_info = self.handle_error_with_screenshot(
                error_message=str(e), context=f"DA {numero_da} - Signature"
            )
            # Tous les articles cochés mais non signés passent en échec
            for code, email in codes_coches:
                r = _res(code, email, 'Echec', f'Erreur: {e}')
                r['error_info'] = error_info
                resultats.append(r)
            # Les lignes jamais traitées
            deja = {r['code_article'] for r in resultats}
            for code, email in lignes:
                if code not in deja:
                    r = _res(code, email, 'Echec', f'Erreur: {e}')
                    r['error_info'] = error_info
                    resultats.append(r)

        return resultats

    def _ouvrir_panneau_selection(self):
        """Si le panneau de sélection est replié, le rouvrir (bouton dir_down)."""
        try:
            btn = self._find_visible_element(
                By.XPATH,
                "//a[contains(@class, 's-title-action')]"
                "[.//i[contains(@class, 's_sagearmonyeicon') and normalize-space(text())='dir_down']]",
                timeout=2
            )
            self.driver_manager.safe_click(btn)
            time.sleep(1)
            self.wait_stabilite()
            self.logger.info("✅ Panneau de sélection rouvert (dir_down)")
        except Exception:
            pass  # déjà ouvert

    def _cliquer_dir_up(self):
        try:
            dir_up_button = self._find_visible_element(
                By.XPATH,
                "//a[contains(@class, 's-title-action')]"
                "[.//i[contains(@class, 's_sagearmonyeicon') and normalize-space(text())='dir_up']]",
                timeout=5
            )
        except Exception:
            self.logger.warning("⚠️ 'dir_up' non visible : panneau probablement déjà replié, on continue")
            return
        self.driver_manager.safe_click(dir_up_button)
        time.sleep(1)
        self.wait_stabilite()
        self.logger.info("✅ Bouton 'dir_up' cliqué (panneau de sélection replié)")
    # ------------------------------------------------------------------
    # BOUCLE SUR TOUS LES ARTICLES À SIGNER (une seule navigation vers l'écran CONSCPD)
    # ------------------------------------------------------------------
    def _traiter_toutes_les_signatures(self, df: pd.DataFrame) -> bool:
        """Naviguer une fois vers l'écran Consultation demandes d'achat, puis signer
        les articles DA par DA (une recherche + une signature par DA).
        Le webhook n'est envoyé qu'une seule fois, après traitement de toutes les lignes."""
        self.navigate_to_module(self.url_demande_achat)
        time.sleep(5)

        driver = self.driver_manager.driver
        self.wait_for_spinner_to_disappear(driver, timeout=90000)

        # Normaliser les colonnes utilisées pour le regroupement
        df = df.copy()
        df['code_article'] = df['code_article'].astype(str).str.strip()
        df['numero_da'] = df['numero_da'].astype(str).str.strip()

        total = len(df)
        groupes = list(df.groupby('numero_da', sort=False))
        self.logger.info(f"📊 Total articles à signer: {total} répartis sur {len(groupes)} DA")

        try:
            for num_groupe, (numero_da, groupe) in enumerate(groupes, start=1):
                lignes = [
                    (row['code_article'], row.get('email_expediteur', ''))
                    for _, row in groupe.iterrows()
                ]

                self.logger.info(f"{'─'*80}")
                self.logger.info(f"✍️ DA {num_groupe}/{len(groupes)}: {numero_da} ({len(lignes)} article(s))")
                self.logger.info(f"{'─'*80}")

                for resultat in self._signer_da(numero_da, lignes):
                    self.add_result(resultat)

                    if resultat['statut'] == 'Succes':
                        self.articles_signes += 1
                        self.articles_signes_liste.append({
                            'code_article': resultat['code_article'],
                            'numero_da': resultat['numero_da'],
                        })
                    else:
                        self.articles_echec += 1
                        self.logger.warning(
                            f"⚠️ Échec signature {resultat['code_article']} (DA {numero_da}), on continue..."
                        )

                time.sleep(2)

        except Exception as e:
            self.logger.error(f"❌ ERREUR lors du traitement des signatures: {e}")
            self.save_report(incremental=True)
            return False

        finally:
            self.logger.info(f"✅ Articles signés: {self.articles_signes}, Échecs: {self.articles_echec}")
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            try:
                driver.find_element(By.CSS_SELECTOR, "a.s_page_close").click()
                time.sleep(2)
            except Exception:
                pass

        # Toutes les lignes sont traitées -> envoi unique au webhook
        if self.articles_signes_liste:
            webhook_ok = self._envoyer_das_signees(
                email_f=str(df.iloc[0].get('email_expediteur', ''))
            )
            self.add_result({
                'type': 'Webhook_Signature_DA',
                'statut': 'Succes' if webhook_ok else 'Echec',
                'message': f'{len(self.articles_signes_liste)} DA signée(s) envoyée(s) au webhook'
            })
        else:
            self.add_result({
                'type': 'Webhook_Signature_DA',
                'statut': 'Ignore',
                'message': 'Aucun article signé : webhook non envoyé'
            })

        self.save_report(incremental=True)
        return self.articles_echec == 0

        

        # Toutes les lignes sont traitées -> envoi unique au webhook
        webhook_ok = self._envoyer_das_signees(email_f=str(df.iloc[0].get('email_expediteur', '')))
        self.add_result({
            'type': 'Webhook_Signature_DA',
            'statut': 'Succes' if webhook_ok else 'Echec',
            'message': f'{len(self.articles_signes_liste)} DA signée(s) envoyée(s) au webhook'
        })

        self.save_report(incremental=True)
        return self.articles_echec == 0

    # ------------------------------------------------------------------
    # RECHERCHER LA DEMANDE D'ACHAT PAR SON NUMÉRO
    # ------------------------------------------------------------------
    def _rechercher_demande_achat(self, numero_da: str):
        """
        Saisir le numéro de DA dans "N° demande début", tabuler (copie
        automatique vers "N° demande fin") puis cliquer sur "Recherche".
        """
        driver = self.driver_manager.driver

        # 1. Champ "N° demande début" (par label, pas par id dynamique)
        champ_num_debut = self.get_input_by_label("N° demande début")
        champ_num_debut.click()
        time.sleep(0.5)
        champ_num_debut.clear()
        champ_num_debut.send_keys(numero_da)

        # 2. TAB -> copie automatique dans "N° demande fin"
        champ_num_debut.send_keys(Keys.TAB)
        time.sleep(1)

        # 3. Cliquer sur "Recherche" (élément visible, au cas où une page
        #    précédente resterait ouverte en arrière-plan)
        bouton_recherche = self._find_visible_element(
            By.XPATH, "//a[contains(@class, 's-mn-main-link') and @title='Recherche']"
        )
        self.driver_manager.safe_click(bouton_recherche)
        time.sleep(2)
        self.wait_for_spinner_to_disappear(driver, timeout=90000)

        self.logger.info(f"✅ Recherche effectuée pour la DA {numero_da}")

    # ------------------------------------------------------------------
    # COCHER LA CASE "SIG." DE LA LIGNE CORRESPONDANT AU CODE ARTICLE
    # ------------------------------------------------------------------
    def _cocher_signature_article(self, code_article: str) -> bool:
        """
        Parcourt les lignes VISIBLES de la grille des articles de la DA, trouve
        celle dont le code article correspond (colonne à l'index 7 parmi tous
        les <input> de la ligne, comme dans valider_article_da_v1), et coche
        la case "Sig." (tableau figé, même index de ligne).
        """
        driver = self.driver_manager.driver
        code_article = code_article.strip()

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.s-grid-table-body"))
            )
        except Exception:
            self.logger.error("❌ Timeout: table.s-grid-table-body jamais apparue")
            return False

        self.wait_stabilite()
        time.sleep(2)

        scrollable_rows_all = driver.find_elements(By.CSS_SELECTOR, "table.s-grid-table-body > tr.s-grid-row")
        fixed_rows_all = driver.find_elements(By.CSS_SELECTOR, "table.s-grid-fixed-table-body > tr.s-grid-row")

        try:
            scrollable_rows, fixed_rows = self._get_grille_lignes()
        except Exception as e:
            self.logger.error(f"❌ {e}")
            return False

        self.logger.info(f"🔍 Lignes grille: {len(scrollable_rows)} (données) / {len(fixed_rows)} (figé)")

        self.logger.info(
            f"🔍 Lignes grille: {len(scrollable_rows_all)} total / {len(scrollable_rows)} visibles "
            f"(fixe: {len(fixed_rows_all)} total / {len(fixed_rows)} visibles)"
        )

        if not scrollable_rows or not fixed_rows:
            self.logger.error("❌ Grille des articles de la DA introuvable ou vide (aucune ligne visible)")
            return False


        if len(scrollable_rows) != len(fixed_rows):
            self.logger.error(
                f"❌ Décalage entre le tableau des données ({len(scrollable_rows)} lignes visibles) "
                f"et le tableau figé ({len(fixed_rows)} lignes visibles)"
            )
            return False

        INDEX_CODE_ARTICLE = 7  # même position que cell[7] dans valider_article_da_v1
        articles_trouves = []

        for idx, row in enumerate(scrollable_rows):
            cell = row.find_elements(By.CSS_SELECTOR, "input")

            if len(cell) <= INDEX_CODE_ARTICLE:
                self.logger.warning(
                    f"⚠️ Ligne {idx+1}: seulement {len(cell)} input(s), "
                    f"impossible de lire l'index {INDEX_CODE_ARTICLE}"
                )
                continue

            valeur_article = (cell[INDEX_CODE_ARTICLE].get_attribute("value") or "").strip()
            articles_trouves.append(valeur_article)

            if valeur_article == code_article:
                self.logger.info(f"Article {code_article} trouvé dans la grille (ligne {idx+1})")

                # Scope local à fixed_row -> évite toute collision avec une
                # page fantôme restée ouverte ailleurs dans le DOM
                fixed_row = fixed_rows[idx]
                checkbox_input = fixed_row.find_element(By.CSS_SELECTOR, "input.s-checkbox-input")
                checkbox_label = fixed_row.find_element(By.CSS_SELECTOR, "label.s-inplace-checkbox")

                if checkbox_input.get_attribute("data-s-selected") == "true":
                    self.logger.info(f"ℹ️ Case Sig. déjà cochée pour l'article {code_article} (ligne {idx+1})")
                else:
                    self.driver_manager.scroll_to_element(checkbox_label)
                    self.driver_manager.safe_click(checkbox_label)
                    time.sleep(0.5)
                    self.logger.info(f"✅ Case Sig. cochée pour l'article {code_article} (ligne {idx+1})")

                return True

        self.logger.warning(
            f"⚠️ Article {code_article} non trouvé. Articles présents dans la grille visible: {articles_trouves}"
        )
        return False
    def _get_grille_lignes(self, timeout: int = 15):
        """Retourne (lignes_donnees, lignes_figees) de la grille VISIBLE,
        en attendant que les deux tableaux soient synchronisés."""
        driver = self.driver_manager.driver

        # Grille visible (ignore les pages fantômes)
        table_data = self._find_visible_element(By.CSS_SELECTOR, "table.s-grid-table-body", timeout)

        # Conteneur le plus proche qui contient aussi le tableau figé
        conteneur = table_data.find_element(
            By.XPATH,
            "./ancestor::div[.//table[contains(@class,'s-grid-fixed-table-body')]][1]"
        )

        fin = time.time() + timeout
        data_rows, fixed_rows = [], []
        while time.time() < fin:
            data_rows = conteneur.find_elements(By.CSS_SELECTOR, "table.s-grid-table-body > tr.s-grid-row")
            fixed_rows = conteneur.find_elements(By.CSS_SELECTOR, "table.s-grid-fixed-table-body > tr.s-grid-row")
            if data_rows and len(data_rows) == len(fixed_rows):
                return data_rows, fixed_rows
            time.sleep(0.5)

        raise Exception(f"Grille non synchronisée: {len(data_rows)} lignes données / {len(fixed_rows)} lignes figées")

    # ------------------------------------------------------------------
    # UTILITAIRE : trouver l'élément VISIBLE (ignore les pages fantômes empilées)
    # ------------------------------------------------------------------
    def _find_visible_element(self, by, value, timeout: int = 15):
        """
        Cherche tous les éléments correspondants et retourne le dernier
        actuellement VISIBLE à l'écran (is_displayed()) — évite de cliquer
        sur un élément d'une page Sage restée ouverte en arrière-plan.
        Réessaie pendant `timeout` secondes si rien n'est encore visible.
        """
        driver = self.driver_manager.driver
        end_time = time.time() + timeout
        total_trouves = 0

        while time.time() < end_time:
            elements = driver.find_elements(by, value)
            total_trouves = len(elements)
            visibles = [e for e in elements if e.is_displayed()]
            if visibles:
                return visibles[-1]
            time.sleep(0.3)

        raise Exception(
            f"Aucun élément visible pour {by}='{value}' "
            f"({total_trouves} élément(s) trouvé(s) au total, dont 0 visible)"
        )


    # ------------------------------------------------------------------
    # CLIQUER SUR "..." PUIS SUR "SIGNATURE" (VALIDATION FINALE)
    # ------------------------------------------------------------------
    def _cliquer_signature(self):
        more_button = self._find_visible_element(
            By.CSS_SELECTOR, "a.s_page_header_more[aria-label=\"Afficher plus d'actions\"]"
        )
        self.driver_manager.safe_click(more_button)
        time.sleep(1)

        signature_link = self._find_visible_element(
            By.XPATH, "//a[contains(@class, 's-mn-prefer-link') and @title='Signature']"
        )
        self.driver_manager.safe_click(signature_link)
        time.sleep(2)
        self.wait_stabilite()

        self.logger.info("✅ Action 'Signature' déclenchée")


    # ------------------------------------------------------------------
    # CONFIRMER LE POPUP "Les lignes cochées seront signées; voulez-vous continuer"
    # ------------------------------------------------------------------
    def _confirmer_popup_signature(self, timeout: int = 10) -> bool:
        """
        Clique sur "Oui" dans le popup de confirmation qui apparaît après
        avoir cliqué sur "Signature".

        Returns:
            True si le popup a été trouvé et confirmé, False s'il n'est
            jamais apparu (peut être normal selon le contexte).
        """
        driver = self.driver_manager.driver

        try:
            popup = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article.s_alertbox_content"))
            )
        except Exception:
            self.logger.warning("⚠️ Popup de confirmation signature non apparu (timeout)")
            return False

        try:
            oui_button = popup.find_element(
                By.XPATH,
                ".//div[contains(@class, 's_alertbox_footer')]//a[@aria-label='Oui']"
            )
            self.driver_manager.safe_click(oui_button)
            time.sleep(1.5)
            self.wait_stabilite()
            self.logger.info("✅ Popup de confirmation signature validé (Oui)")
            return True
        except Exception as e:
            self.logger.error(f"❌ Impossible de cliquer sur 'Oui' dans le popup: {e}")
            return False

        
    def _envoyer_das_signees(self, email_f: str = '') -> bool:
        """
        Envoyer en UNE SEULE requête toutes les DA signées au webhook n8n,
        après la fin du traitement de toutes les lignes.
        """
        if not self.webhook_url:
            self.logger.warning("⚠️ URL webhook non configurée : envoi ignoré")
            return False

        if not self.articles_signes_liste:
            self.logger.info("ℹ️ Aucun article signé : webhook non envoyé")
            return False

        payload = {
            'type': 'signature_da',
            'email_expediteur': email_f,
            'total_signes': len(self.articles_signes_liste),
            'total_echecs': self.articles_echec,
            'articles': self.articles_signes_liste,   # [{code_article, numero_da}, ...]
        }

        for tentative in range(1, self.WEBHOOK_MAX_TENTATIVES + 1):
            try:
                response = requests.post(self.webhook_url, json=payload, timeout=self.WEBHOOK_TIMEOUT)
                response.raise_for_status()
                self.logger.info(
                    f"📤 {len(self.articles_signes_liste)} DA signée(s) envoyée(s) au webhook "
                    f"(HTTP {response.status_code})"
                )
                return True
            except requests.RequestException as e:
                self.logger.warning(
                    f"⚠️ Envoi webhook échoué (tentative {tentative}/{self.WEBHOOK_MAX_TENTATIVES}): {e}"
                )
                if tentative < self.WEBHOOK_MAX_TENTATIVES:
                    time.sleep(2)

        self.logger.error("❌ DA signées non envoyées au webhook après toutes les tentatives")
        return False
    # ------------------------------------------------------------------
    # EXECUTE (Template Method — appelé par BaseRobot.run())
    # ------------------------------------------------------------------
    def execute(self, excel_file: str = None, dataframe: pd.DataFrame = None):
        """
        Exécuter la signature des articles

        Args:
            excel_file: chemin du fichier Excel (code_article, numero_da, email_expediteur)
            dataframe: DataFrame déjà chargé (optionnel, ex: appel API)
        """
        email_f = ""
        try:
            df = dataframe if dataframe is not None else self._lire_et_valider_excel(excel_file)

            if df.empty:
                raise ValueError("Aucune ligne valide à traiter")

            email_f = df.iloc[0].get('email_expediteur', '')

            self.connect_sage()

            signatures_ok = self._traiter_toutes_les_signatures(df)

            self.add_result({
                'type': 'BILAN_FINAL',
                'statut': 'SUCCES' if signatures_ok else 'PARTIEL',
                'articles_signes': self.articles_signes,
                'articles_echec': self.articles_echec,
                'message': f'{self.articles_signes} article(s) signé(s), {self.articles_echec} échec(s)'
            })
            self.save_report()
            self.send_results_to_web(email_f)

        except Exception as e:
            self.logger.error(f"❌ ERREUR CRITIQUE: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

            self.add_result({'type': 'ERREUR', 'statut': 'ECHEC', 'message': str(e)})
            self.save_report()
            self.send_results_to_web(email_f)
            raise

        finally:
            self.logger.info("Déconnexion du robot...")
            self.disconnect_sage()