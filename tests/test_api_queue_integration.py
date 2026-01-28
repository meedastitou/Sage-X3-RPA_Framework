# -*- coding: utf-8 -*-
"""
Tests d'intégration pour l'API Queue-Based
Vérifie que l'API enqueue correctement les tâches et que le statut est récupérable
"""
import sys
import os
import json
import uuid
import traceback
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Essayer d'importer TestClient de différentes sources
try:
    # Essayer d'abord fastapi.testclient (pour les versions plus récentes)
    from fastapi.testclient import TestClient
except ImportError:
    try:
        # Fallback pour starlette.testclient (pour les versions comme la vôtre)
        from starlette.testclient import TestClient
    except ImportError:
        raise ImportError("Impossible d'importer TestClient. Installez fastapi avec: pip install fastapi")

from api.main import app, UPLOAD_DIR
from utils.queue_manager import load_queue, QUEUE_FILE

# Client de test FastAPI
client = TestClient(app)


def setup_module():
    """Préparation avant les tests"""
    # S'assurer que le dossier uploads existe
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Optionnel: sauvegarder la queue existante
    if os.path.exists(QUEUE_FILE):
        import shutil
        shutil.copy2(QUEUE_FILE, f"{QUEUE_FILE}.backup")


def teardown_module():
    """Nettoyage après les tests"""
    # Optionnel: nettoyer les fichiers de test créés
    # Supprimer la queue de test et restaurer l'originale si nécessaire
    if os.path.exists(QUEUE_FILE):
        os.remove(QUEUE_FILE)
    
    # Restaurer la backup si elle existe
    backup_file = f"{QUEUE_FILE}.backup"
    if os.path.exists(backup_file):
        import shutil
        shutil.copy2(backup_file, QUEUE_FILE)
        os.remove(backup_file)


class TestAPIHealth:
    """Tests de santé de l'API"""

    def test_root_endpoint(self):
        """Test 1: Vérifier que l'API répond"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Sage X3 RPA API"
        assert "bonne_commande_data" in data["endpoints"]

    def test_health_endpoint(self):
        """Test 2: Vérifier le health check"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestBonneCommandeDataEndpoint:
    """Tests pour l'endpoint POST /api/bonne-commande/data"""

    def test_enqueue_task_success(self):
        """Test 3: Vérifier que l'API enqueue correctement une tâche"""
        payload = {
            "donnees": [
                {
                    "Numero_DA": "DA170753",
                    "Acheteur": "RACH",
                    "Code_Fournisseur": "T1398",
                    "Email_Fournisseur": "exemple1@fournisseur1.com",
                    "TEL_Fournisseu": "2126 00 00 00 00",
                    "Code_Article": "A00001",
                    "Montant": 20,
                    "Marque": "DELL",
                    "Affaire": ""
                }
            ],
            "email_expediteur": "test@example.com",
            "headless": True
        }

        response = client.post("/api/bonne-commande/data", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Vérifier la structure de la réponse
        assert "task_id" in data
        assert data["status"] == "pending"
        assert data["module"] == "bonne_commande_api"
        assert data["started_at"] is None
        assert data["completed_at"] is None

        # Vérifier que la tâche est dans la queue
        queue_tasks = load_queue()
        task_ids = [t["id"] for t in queue_tasks]
        assert data["task_id"] in task_ids

    def test_enqueue_missing_email(self):
        """Test 4: Vérifier l'erreur si email manquant"""
        payload = {
            "donnees": [
                {
                    "Numero_DA": "DA170754",
                    "Acheteur": "TEST"
                }
            ],
            "email_expediteur": "",
            "headless": True
        }

        response = client.post("/api/bonne-commande/data", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        # Vérifier que l'erreur concerne l'email (peut être en français ou anglais)
        detail_lower = data["detail"].lower()
        assert any(keyword in detail_lower for keyword in ["email", "expediteur"])

    def test_enqueue_multiple_rows(self):
        """Test 5: Vérifier que plusieurs lignes sont enqueued correctement"""
        payload = {
            "donnees": [
                {
                    "Numero_DA": "DA170755",
                    "Acheteur": "RACH",
                    "Code_Fournisseur": "T1398",
                    "Email_Fournisseur": "fournisseur1@test.com",
                    "TEL_Fournisseu": "0600000001",
                    "Code_Article": "A00001",
                    "Montant": 100,
                    "Marque": "HP",
                    "Affaire": "AFF001"
                },
                {
                    "Numero_DA": "DA170756",
                    "Acheteur": "RACH",
                    "Code_Fournisseur": "T1399",
                    "Email_Fournisseur": "fournisseur2@test.com",
                    "TEL_Fournisseu": "0600000002",
                    "Code_Article": "A00002",
                    "Montant": 200,
                    "Marque": "DELL",
                    "Affaire": "AFF002"
                }
            ],
            "email_expediteur": "multi@example.com",
            "headless": True
        }

        response = client.post("/api/bonne-commande/data", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"


class TestTaskStatusEndpoint:
    """Tests pour l'endpoint GET /api/task/{task_id}"""

    def test_get_task_from_queue(self):
        """Test 6: Récupérer le statut d'une tâche depuis la queue"""
        # D'abord créer une tâche
        payload = {
            "donnees": [
                {
                    "Numero_DA": "DA170757",
                    "Acheteur": "TEST",
                    "Code_Fournisseur": "T0001",
                    "Email_Fournisseur": "test@fournisseur.com",
                    "TEL_Fournisseu": "0600000000",
                    "Code_Article": "A00003",
                    "Montant": 50,
                    "Marque": "LENOVO",
                    "Affaire": ""
                }
            ],
            "email_expediteur": "status@example.com",
            "headless": True
        }

        create_response = client.post("/api/bonne-commande/data", json=payload)
        task_id = create_response.json()["task_id"]

        # Récupérer le statut
        status_response = client.get(f"/api/task/{task_id}")

        assert status_response.status_code == 200
        data = status_response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "pending"

    def test_get_task_not_found(self):
        """Test 7: Erreur 404 si tâche non trouvée"""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/task/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert any(keyword in data["detail"].lower() for keyword in ["trouvée", "found", "existe"])


class TestExcelFileCreation:
    """Tests pour la création des fichiers Excel"""

    def test_excel_file_created(self):
        """Test 8: Vérifier que le fichier Excel est créé"""
        payload = {
            "donnees": [
                {
                    "Numero_DA": "DA170758",
                    "Acheteur": "FILE_TEST",
                    "Code_Fournisseur": "T9999",
                    "Email_Fournisseur": "excel@test.com",
                    "TEL_Fournisseu": "0699999999",
                    "Code_Article": "A99999",
                    "Montant": 999,
                    "Marque": "TEST",
                    "Affaire": "TEST_AFF"
                }
            ],
            "email_expediteur": "excel@example.com",
            "headless": True
        }

        response = client.post("/api/bonne-commande/data", json=payload)
        task_id = response.json()["task_id"]

        # Attendre un peu pour que le fichier soit créé
        import time
        time.sleep(0.5)

        # Trouver la tâche dans la queue
        queue_tasks = load_queue()
        task = next((t for t in queue_tasks if t["id"] == task_id), None)

        assert task is not None
        assert "file" in task
        assert task["file"].endswith(".xlsx")

        # Vérifier que le fichier existe
        file_path = task["file"]
        # Le chemin peut être relatif ou absolu
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.path.dirname(QUEUE_FILE), file_path)
        
        assert os.path.exists(file_path), f"Le fichier {file_path} n'existe pas"


class TestQueueFormat:
    """Tests pour le format de la queue"""

    def test_queue_task_format(self):
        """Test 9: Vérifier le format des tâches dans la queue"""
        payload = {
            "donnees": [
                {
                    "Numero_DA": "DA170759",
                    "Acheteur": "FORMAT_TEST",
                    "Code_Fournisseur": "T0000",
                    "Email_Fournisseur": "format@test.com",
                    "TEL_Fournisseu": "0600000000",
                    "Code_Article": "A00000",
                    "Montant": 0,
                    "Marque": "TEST",
                    "Affaire": ""
                }
            ],
            "email_expediteur": "format@example.com",
            "headless": True
        }

        response = client.post("/api/bonne-commande/data", json=payload)
        task_id = response.json()["task_id"]

        # Attendre un peu
        import time
        time.sleep(0.5)

        # Vérifier le format dans la queue
        queue_tasks = load_queue()
        task = next((t for t in queue_tasks if t["id"] == task_id), None)

        assert task is not None

        # Vérifier tous les champs requis
        required_fields = ["id", "status", "task_type", "file", "email", "created_at"]
        for field in required_fields:
            assert field in task, f"Champ manquant: {field}"

        assert task["task_type"] == "bon_commande"
        assert task["email"] == "format@example.com"
        assert task["status"] == "pending"


def run_all_tests():
    """Exécuter tous les tests manuellement"""
    test_classes = [
        TestAPIHealth,
        TestBonneCommandeDataEndpoint,
        TestTaskStatusEndpoint,
        TestExcelFileCreation,
        TestQueueFormat
    ]

    total = 0
    passed = 0
    failed = 0

    print("=" * 60)
    print("TESTS D'INTÉGRATION API QUEUE-BASED")
    print("=" * 60)

    for test_class in test_classes:
        print(f"\n📦 {test_class.__name__}")
        print("-" * 40)

        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith("test_")]

        for method_name in methods:
            total += 1
            method = getattr(instance, method_name)

            try:
                method()
                print(f"  ✅ {method_name}")
                passed += 1
            except AssertionError as e:
                print(f"  ❌ {method_name}: {e}")
                failed += 1
            except Exception as e:
                print(f"  ❌ {method_name}: Exception - {e}")
                traceback.print_exc()
                failed += 1

    print("\n" + "=" * 60)
    print(f"RÉSULTATS: {passed}/{total} tests passés")
    if failed > 0:
        print(f"⚠️  {failed} tests échoués")
    else:
        print("🎉 Tous les tests sont passés!")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    try:
        setup_module()
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Erreur lors de l'exécution des tests: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        teardown_module()