# -*- coding: utf-8 -*-
"""
Mixin pour ajouter l'envoi automatique des résultats vers un endpoint web
"""
from typing import Dict, Any, Optional
import time

from utils.result_sender import ResultSender
from config.web_endpoint import WEB_ENDPOINT_CONFIG
from core.logger import Logger


class WebResultMixin:
    """
    Mixin pour envoyer automatiquement les résultats vers un endpoint web
    À hériter dans les robots qui doivent envoyer leurs résultats
    """
    
    def __init__(self):
        """Initialiser le mixin"""
        self.web_endpoint_config = WEB_ENDPOINT_CONFIG
        self.result_sender = None
        
        if self.web_endpoint_config['enabled']:
            self.result_sender = ResultSender(
                endpoint_url=self.web_endpoint_config['url'],
                timeout=self.web_endpoint_config['timeout']
            )
            
            if hasattr(self, 'logger'):
                self.logger.info(f"🌐 Envoi web activé: {self.web_endpoint_config['url']}")
    
    def send_results_to_web(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        Envoyer les résultats vers l'endpoint web
        
        Args:
            force: Forcer l'envoi même si désactivé dans la config
        
        Returns:
            Résultat de l'envoi ou None si désactivé
        """
        if not self.web_endpoint_config['enabled'] and not force:
            if hasattr(self, 'logger'):
                self.logger.info("ℹ️ Envoi web désactivé (config)")
            return None
        
        if not self.result_sender:
            self.result_sender = ResultSender(
                endpoint_url=self.web_endpoint_config['url'],
                timeout=self.web_endpoint_config['timeout']
            )
        
        logger = getattr(self, 'logger', Logger.get_logger('WebResultMixin', 'utils'))
        
        logger.info("="*80)
        logger.info("🌐 ENVOI DES RÉSULTATS VERS L'ENDPOINT WEB")
        logger.info("="*80)
        logger.info(f"📡 URL: {self.web_endpoint_config['url']}")
        logger.info(f"📊 Mode: {self.web_endpoint_config['mode']}")
        
        try:
            # Formater les données selon le type de robot
            data = self._format_results_for_web()
            
            # Récupérer le chemin du rapport si disponible
            file_path = str(self.rapport_path) if hasattr(self, 'rapport_path') and self.rapport_path else None
            
            # Choisir le mode d'envoi
            mode = self.web_endpoint_config['mode']
            include_file = self.web_endpoint_config['include_file'] and file_path
            
            # Headers personnalisés (retirer les valeurs vides)
            headers = {k: v for k, v in self.web_endpoint_config['headers'].items() if v}
            
            result = None
            retry_count = self.web_endpoint_config['retry_count'] if self.web_endpoint_config['retry_enabled'] else 1
            
            for attempt in range(1, retry_count + 1):
                try:
                    if mode == 'json' and not include_file:
                        # JSON pur (sans fichier)
                        result = self.result_sender.send_json(data, headers)
                    
                    elif mode == 'multipart' and include_file:
                        # Multipart avec fichier
                        result = self.result_sender.send_with_file(data, file_path, headers)
                    
                    elif mode == 'base64' and include_file:
                        # JSON avec fichier en base64
                        result = self.result_sender.send_base64_file(data, file_path, headers)
                    
                    else:
                        # Par défaut: JSON
                        result = self.result_sender.send_json(data, headers)
                    
                    # Si succès, sortir de la boucle
                    if result.get('success'):
                        logger.info(f"✅ Envoi réussi (tentative {attempt}/{retry_count})")
                        break
                    else:
                        logger.warning(f"⚠️ Échec tentative {attempt}/{retry_count}: {result.get('message')}")
                        if attempt < retry_count:
                            delay = self.web_endpoint_config['retry_delay']
                            logger.info(f"⏳ Nouvelle tentative dans {delay}s...")
                            time.sleep(delay)
                
                except Exception as e:
                    logger.error(f"❌ Erreur tentative {attempt}/{retry_count}: {e}")
                    if attempt < retry_count:
                        delay = self.web_endpoint_config['retry_delay']
                        logger.info(f"⏳ Nouvelle tentative dans {delay}s...")
                        time.sleep(delay)
                    else:
                        result = {
                            'success': False,
                            'error': str(e),
                            'message': f'Erreur après {retry_count} tentatives'
                        }
            
            logger.info("="*80)
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Erreur envoi web: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e),
                'message': f'Erreur critique: {str(e)}'
            }
    
    def _format_results_for_web(self) -> Dict[str, Any]:
        """
        Formater les résultats pour l'envoi web
        À surcharger dans les robots si nécessaire
        
        Returns:
            Dictionnaire de données
        """
        # Détecter le type de robot
        class_name = self.__class__.__name__
        
        if 'BonneCommande' in class_name:
            return self.result_sender.format_bonne_commande_result(self)
        elif 'Lettrage' in class_name:
            return self.result_sender.format_lettrage_result(self)
        else:
            # Format générique
            summary = self.generate_summary() if hasattr(self, 'generate_summary') else {}
            return {
                'module': getattr(self, 'module_name', 'unknown'),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'summary': summary,
                'rapport_path': str(self.rapport_path) if hasattr(self, 'rapport_path') else None
            }
