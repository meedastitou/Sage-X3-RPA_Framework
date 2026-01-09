# -*- coding: utf-8 -*-
"""
Module pour envoyer les résultats vers un endpoint web
Supporte : JSON, Multipart (avec fichiers), Webhooks
"""
import requests
import json
from typing import Dict, Any, Optional
from pathlib import Path
import base64
from datetime import datetime

from core.logger import Logger


class ResultSender:
    """Classe pour envoyer les résultats vers un endpoint web"""
    
    def __init__(self, endpoint_url: str, timeout: int = 30):
        """
        Initialiser le sender
        
        Args:
            endpoint_url: URL de l'endpoint (ex: http://jbel-annour.ma/resultat)
            timeout: Timeout en secondes
        """
        self.endpoint_url = endpoint_url.rstrip('/')
        self.timeout = timeout
        self.logger = Logger.get_logger('ResultSender', 'api')
    
    def send_json(self, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Envoyer les résultats en JSON
        
        Args:
            data: Dictionnaire de données à envoyer
            headers: Headers HTTP additionnels
        
        Returns:
            Réponse du serveur
        """
        self.logger.info(f"📤 Envoi JSON vers: {self.endpoint_url}")
        
        try:
            default_headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Sage-X3-RPA/1.0'
            }
            
            if headers:
                default_headers.update(headers)
            
            response = requests.post(
                self.endpoint_url,
                json=data,
                headers=default_headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            self.logger.info(f"✅ Envoi réussi (Status: {response.status_code})")
            
            return {
                'success': True,
                'status_code': response.status_code,
                'response': response.json() if response.content else None,
                'message': 'Envoi réussi'
            }
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Erreur envoi: {e}")
            return {
                'success': False,
                'status_code': getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
                'error': str(e),
                'message': f'Erreur envoi: {str(e)}'
            }
    
    def send_with_file(self, data: Dict[str, Any], file_path: Optional[str] = None, 
                       headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Envoyer les résultats avec un fichier (multipart/form-data)
        
        Args:
            data: Dictionnaire de données à envoyer
            file_path: Chemin du fichier rapport Excel à joindre
            headers: Headers HTTP additionnels
        
        Returns:
            Réponse du serveur
        """
        self.logger.info(f"📤 Envoi multipart vers: {self.endpoint_url}")
        
        try:
            files = {}
            if file_path and Path(file_path).exists():
                self.logger.info(f"📎 Fichier joint: {file_path}")
                files['file'] = open(file_path, 'rb')
            
            default_headers = {
                'User-Agent': 'Sage-X3-RPA/1.0'
            }
            
            if headers:
                default_headers.update(headers)
            
            response = requests.post(
                self.endpoint_url,
                data=data,
                files=files if files else None,
                headers=default_headers,
                timeout=self.timeout
            )
            
            # Fermer le fichier
            if files:
                files['file'].close()
            
            response.raise_for_status()
            
            self.logger.info(f"✅ Envoi réussi (Status: {response.status_code})")
            
            return {
                'success': True,
                'status_code': response.status_code,
                'response': response.json() if response.content else None,
                'message': 'Envoi réussi'
            }
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Erreur envoi: {e}")
            return {
                'success': False,
                'status_code': getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
                'error': str(e),
                'message': f'Erreur envoi: {str(e)}'
            }
    
    def send_base64_file(self, data: Dict[str, Any], file_path: Optional[str] = None,
                         headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Envoyer les résultats avec fichier encodé en base64 dans le JSON
        
        Args:
            data: Dictionnaire de données à envoyer
            file_path: Chemin du fichier rapport Excel
            headers: Headers HTTP additionnels
        
        Returns:
            Réponse du serveur
        """
        self.logger.info(f"📤 Envoi JSON+Base64 vers: {self.endpoint_url}")
        
        try:
            # Encoder le fichier en base64 si fourni
            if file_path and Path(file_path).exists():
                self.logger.info(f"📎 Encodage fichier: {file_path}")
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    file_base64 = base64.b64encode(file_content).decode('utf-8')
                
                data['file'] = {
                    'filename': Path(file_path).name,
                    'content': file_base64,
                    'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                }
            
            return self.send_json(data, headers)
            
        except Exception as e:
            self.logger.error(f"❌ Erreur encodage fichier: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Erreur encodage: {str(e)}'
            }
    
    def format_bonne_commande_result(self, robot) -> Dict[str, Any]:
        """
        Formater les résultats du robot Bonne de Commande pour l'envoi

        Args:
            robot: Instance de BonneCommandeRobot

        Returns:
            Dictionnaire formaté
        """
        summary = robot.generate_summary()

        data = {
            'module': 'bonne_commande',
            'timestamp': datetime.now().isoformat(),
            'statut': 'succes' if robot.validation_passed else 'echec',
            'validation_passed': robot.validation_passed,
            'statistiques': {
                'total_articles': robot.articles_traites + robot.articles_echec,
                'articles_traites': robot.articles_traites,
                'articles_echec': robot.articles_echec,
                'total_das': robot.das_traitees + robot.das_echec,
                'das_traitees': robot.das_traitees,
                'das_echec': robot.das_echec
            },
            'bc_genere': robot.validation_passed,
            'rapport_path': str(robot.rapport_path) if robot.rapport_path else None,
            'details': summary
        }

        # Ajouter bc_numbers si disponible
        if hasattr(robot, 'bc_numbers') and robot.bc_numbers:
            data['bc_numbers'] = robot.bc_numbers

        # Ajouter message_final si disponible
        if hasattr(robot, 'message_final') and robot.message_final:
            data['message'] = robot.message_final

        return data
    
    def format_lettrage_result(self, robot) -> Dict[str, Any]:
        """
        Formater les résultats du robot Lettrage pour l'envoi
        
        Args:
            robot: Instance de LettrageRobot
        
        Returns:
            Dictionnaire formaté
        """
        summary = robot.generate_summary()
        
        return {
            'module': 'lettrage',
            'timestamp': datetime.now().isoformat(),
            'statut': 'succes' if summary.get('succes', 0) > 0 else 'echec',
            'statistiques': {
                'total': summary.get('total', 0),
                'succes': summary.get('succes', 0),
                'echecs': summary.get('echecs', 0)
            },
            'rapport_path': str(robot.rapport_path) if robot.rapport_path else None,
            'details': summary
        }


# ============================================================================
# EXEMPLES D'UTILISATION
# ============================================================================

def exemple_envoi_simple():
    """Exemple 1: Envoi simple en JSON"""
    sender = ResultSender('http://jbel-annour.ma/resultat')
    
    data = {
        'module': 'bonne_commande',
        'statut': 'succes',
        'articles_traites': 3,
        'das_traitees': 2,
        'bc_genere': True
    }
    
    result = sender.send_json(data)
    print(result)


def exemple_envoi_avec_fichier():
    """Exemple 2: Envoi avec fichier Excel"""
    sender = ResultSender('http://jbel-annour.ma/resultat')
    
    data = {
        'module': 'bonne_commande',
        'statut': 'succes',
        'articles_traites': 3
    }
    
    result = sender.send_with_file(
        data=data,
        file_path='rapport_bonne_commande_20251229.xlsx'
    )
    print(result)


def exemple_envoi_base64():
    """Exemple 3: Envoi avec fichier en base64"""
    sender = ResultSender('http://jbel-annour.ma/resultat')
    
    data = {
        'module': 'bonne_commande',
        'statut': 'succes'
    }
    
    result = sender.send_base64_file(
        data=data,
        file_path='rapport_bonne_commande_20251229.xlsx'
    )
    print(result)


def exemple_depuis_robot():
    """Exemple 4: Envoi depuis un robot"""
    from modules.bonne_commande.bonne_commande_robot import BonneCommandeRobot
    
    # Créer et exécuter le robot
    robot = BonneCommandeRobot()
    robot.run(excel_file='commandes.xlsx')
    
    # Envoyer les résultats
    sender = ResultSender('http://jbel-annour.ma/resultat')
    
    # Option 1: JSON seulement
    data = sender.format_bonne_commande_result(robot)
    result = sender.send_json(data)
    
    # Option 2: JSON + Fichier
    result = sender.send_with_file(
        data=data,
        file_path=str(robot.rapport_path)
    )
    
    print(result)


if __name__ == '__main__':
    # Tester l'envoi
    exemple_envoi_simple()
