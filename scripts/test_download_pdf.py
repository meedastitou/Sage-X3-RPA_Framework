# -*- coding: utf-8 -*-
"""
Script de test pour télécharger un PDF via Chrome
Utilise le driver_manager configuré pour téléchargement automatique
"""
import sys
import os
import time
import glob

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.driver_manager import DriverManager
from config.settings import SELENIUM_CONFIG
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def test_download_pdf():
    """Test de téléchargement de PDF"""
    
    # download dans le folder SELENIUM_CONFIG['document_genere']/downloads
    download_dir = os.path.join(SELENIUM_CONFIG['document_genere'], "downloads")
    os.makedirs(download_dir, exist_ok=True)

    pdf_url = "https://www.univ-usto.dz/images/coursenligne/gm_MI.pdf"

    print("="*60)
    print("🧪 TEST TÉLÉCHARGEMENT PDF")
    print("="*60)
    print(f"📁 Dossier de téléchargement: {download_dir}")
    print(f"🔗 URL: {pdf_url}")
    print("="*60)

    # Récupérer les PDFs existants avant le test
    existing_pdfs = set(glob.glob(os.path.join(download_dir, "*.pdf")))
    print(f"📄 PDFs existants: {len(existing_pdfs)}")

    # Initialiser le driver
    driver_manager = DriverManager(headless=False)
    driver = driver_manager.start()

    try:
        # 1. Ouvrir l'URL du PDF
        print("\n📥 Ouverture du PDF...")
        driver.get(pdf_url)
        time.sleep(5)  # Attendre le chargement du PDF viewer

        print("✅ PDF ouvert dans le navigateur")

        # 2. Cliquer sur le bouton de téléchargement (dans le shadow DOM)
        print("\n🖱️ Clic sur le bouton de téléchargement...")

        # Méthode 1: Utiliser JavaScript pour accéder au shadow DOM
        # try:
        #     driver.execute_script("""
        #         // Chercher le bouton de téléchargement dans le PDF viewer
        #         var downloadBtn = document.querySelector('#save');
        #         if (downloadBtn) {
        #             downloadBtn.click();
        #             console.log('Bouton save cliqué');
        #         } else {
        #             // Essayer via le shadow root du PDF viewer
        #             var viewer = document.querySelector('pdf-viewer');
        #             if (viewer && viewer.shadowRoot) {
        #                 var toolbar = viewer.shadowRoot.querySelector('#toolbar');
        #                 if (toolbar && toolbar.shadowRoot) {
        #                     var saveBtn = toolbar.shadowRoot.querySelector('#save');
        #                     if (saveBtn) {
        #                         saveBtn.click();
        #                         console.log('Bouton save cliqué via shadow DOM');
        #                     }
        #                 }
        #             }
        #         }
        #     """)
        #     print("✅ Clic JavaScript exécuté")
        # except Exception as e:
        #     print(f"⚠️ Erreur clic JS: {e}")

        # 3. Attendre le téléchargement
        print("\n⏳ Attente du téléchargement (max 30s)...")
        timeout = 30
        start_time = time.time()
        new_pdf = None

        while time.time() - start_time < timeout:
            time.sleep(1)
            current_pdfs = set(glob.glob(os.path.join(download_dir, "*.pdf")))
            new_pdfs = current_pdfs - existing_pdfs

            # Vérifier aussi les fichiers .crdownload (en cours de téléchargement)
            downloading = glob.glob(os.path.join(download_dir, "*.crdownload"))
            if downloading:
                print(f"   ⏳ Téléchargement en cours: {len(downloading)} fichier(s)")

            if new_pdfs:
                for pdf in new_pdfs:
                    if os.path.exists(pdf) and not pdf.endswith('.crdownload'):
                        file_size = os.path.getsize(pdf)
                        if file_size > 0:
                            new_pdf = pdf
                            break
                if new_pdf:
                    break

            elapsed = int(time.time() - start_time)
            print(f"   ⏳ {elapsed}s écoulées...")

        # 4. Résultat
        print("\n" + "="*60)
        if new_pdf:
            file_size = os.path.getsize(new_pdf) / 1024  # KB
            print(f"✅ SUCCÈS! PDF téléchargé:")
            print(f"   📄 Fichier: {new_pdf}")
            print(f"   📊 Taille: {file_size:.2f} KB")
        else:
            print("❌ ÉCHEC: Aucun nouveau PDF détecté")
            print("\n💡 Suggestions:")
            print("   1. Vérifiez que Chrome n'affiche pas de popup de confirmation")
            print("   2. Le PDF viewer peut avoir un comportement différent")
            print("   3. Essayez de cliquer manuellement pour vérifier")

        print("="*60)

        # Garder le navigateur ouvert pour inspection

        return new_pdf

    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        driver_manager.stop()


if __name__ == "__main__":
    test_download_pdf()
