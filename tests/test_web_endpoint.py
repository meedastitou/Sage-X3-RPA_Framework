#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de l'envoi des résultats vers l'endpoint web
"""
import sys
from pathlib import Path

# Ajouter le dossier sage-x3-rpa au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.result_sender import ResultSender


def test_envoi_simple():
    """Test 1: Envoi JSON simple"""
    print("="*80)
    print("TEST 1: Envoi JSON Simple")
    print("="*80)
    
    sender = ResultSender('http://jbel-annour.ma/resultat')
    
    data = {
        'module': 'test',
        'timestamp': '2025-12-29T15:00:00',
        'statut': 'succes',
        'message': 'Test envoi depuis RPA',
        'statistiques': {
            'total': 10,
            'succes': 8,
            'echecs': 2
        }
    }
    
    result = sender.send_json(data)
    
    print(f"\n📊 Résultat:")
    print(f"   Success: {result.get('success')}")
    print(f"   Status: {result.get('status_code')}")
    print(f"   Message: {result.get('message')}")
    
    if not result.get('success'):
        print(f"   Erreur: {result.get('error')}")
    
    print("\n" + "="*80 + "\n")
    
    return result.get('success', False)


def test_envoi_avec_headers():
    """Test 2: Envoi avec authentification"""
    print("="*80)
    print("TEST 2: Envoi avec Headers d'Authentification")
    print("="*80)
    
    sender = ResultSender('http://jbel-annour.ma/resultat')
    
    data = {
        'module': 'test_auth',
        'statut': 'succes'
    }
    
    headers = {
        'Authorization': 'Bearer test_token_123',
        'X-API-Key': 'sk-test-key'
    }
    
    result = sender.send_json(data, headers)
    
    print(f"\n📊 Résultat:")
    print(f"   Success: {result.get('success')}")
    print(f"   Status: {result.get('status_code')}")
    print(f"   Message: {result.get('message')}")
    
    print("\n" + "="*80 + "\n")
    
    return result.get('success', False)


def test_envoi_multipart():
    """Test 3: Envoi multipart avec fichier"""
    print("="*80)
    print("TEST 3: Envoi Multipart avec Fichier")
    print("="*80)
    
    sender = ResultSender('http://jbel-annour.ma/resultat')
    
    # Créer un fichier de test
    test_file = Path(__file__).parent / 'test_report.txt'
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write('Rapport de test\n')
        f.write('Module: test\n')
        f.write('Statut: succès\n')
    
    data = {
        'module': 'test_multipart',
        'statut': 'succes'
    }
    
    result = sender.send_with_file(
        data=data,
        file_path=str(test_file)
    )
    
    print(f"\n📊 Résultat:")
    print(f"   Success: {result.get('success')}")
    print(f"   Status: {result.get('status_code')}")
    print(f"   Message: {result.get('message')}")
    
    # Nettoyer
    test_file.unlink()
    
    print("\n" + "="*80 + "\n")
    
    return result.get('success', False)


def test_envoi_base64():
    """Test 4: Envoi avec fichier encodé en base64"""
    print("="*80)
    print("TEST 4: Envoi JSON avec Fichier Base64")
    print("="*80)
    
    sender = ResultSender('http://jbel-annour.ma/resultat')
    
    # Créer un fichier de test
    test_file = Path(__file__).parent / 'test_report.txt'
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write('Rapport de test en base64\n')
    
    data = {
        'module': 'test_base64',
        'statut': 'succes'
    }
    
    result = sender.send_base64_file(
        data=data,
        file_path=str(test_file)
    )
    
    print(f"\n📊 Résultat:")
    print(f"   Success: {result.get('success')}")
    print(f"   Status: {result.get('status_code')}")
    print(f"   Message: {result.get('message')}")
    
    # Nettoyer
    test_file.unlink()
    
    print("\n" + "="*80 + "\n")
    
    return result.get('success', False)


def main():
    """Lancer tous les tests"""
    print("\n" + "="*80)
    print("🧪 TESTS D'ENVOI VERS L'ENDPOINT WEB")
    print("="*80)
    print(f"📡 URL: http://jbel-annour.ma/resultat")
    print("="*80 + "\n")
    
    input("⚠️  Assurez-vous que votre serveur web est démarré.\nAppuyez sur Entrée pour continuer...")
    
    results = []
    
    # Test 1
    try:
        results.append(('JSON Simple', test_envoi_simple()))
    except Exception as e:
        print(f"❌ Erreur Test 1: {e}\n")
        results.append(('JSON Simple', False))
    
    # Test 2
    try:
        results.append(('Avec Auth', test_envoi_avec_headers()))
    except Exception as e:
        print(f"❌ Erreur Test 2: {e}\n")
        results.append(('Avec Auth', False))
    
    # Test 3
    try:
        results.append(('Multipart', test_envoi_multipart()))
    except Exception as e:
        print(f"❌ Erreur Test 3: {e}\n")
        results.append(('Multipart', False))
    
    # Test 4
    try:
        results.append(('Base64', test_envoi_base64()))
    except Exception as e:
        print(f"❌ Erreur Test 4: {e}\n")
        results.append(('Base64', False))
    
    # Résumé
    print("="*80)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*80)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    total = len(results)
    passed = sum(1 for _, s in results if s)
    
    print("="*80)
    print(f"📈 Score: {passed}/{total} tests réussis")
    print("="*80)
    
    input("\n⏸️ Appuyez sur Entrée pour fermer...")


if __name__ == '__main__':
    main()
