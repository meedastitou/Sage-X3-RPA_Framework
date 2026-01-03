# -*- coding: utf-8 -*-
"""
Classe de base pour tous les robots RPA
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any
import pandas as pd
from pathlib import Path

from core.sage_connector import SageConnector
from core.driver_manager import DriverManager
from core.logger import Logger
from config.settings import OUTPUT_DIR

class BaseRobot(ABC):
    """Classe de base abstraite pour tous les robots"""
    
    def __init__(self, module_name: str):
        """
        Initialiser le robot
        
        Args:
            module_name: Nom du module (lettrage, facturation, etc.)
        """
        self.module_name = module_name
        self.logger = Logger.get_logger(self.__class__.__name__, module_name)
        
        # Composants réutilisables
        self.driver_manager = DriverManager()
        self.sage_connector = SageConnector(self.driver_manager)
        
        # Données
        self.resultats = []
        self.rapport_path = None
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.logger.info(f"🤖 Initialisation robot: {self.__class__.__name__}")
    
    @abstractmethod
    def execute(self, *args, **kwargs):
        """
        Méthode principale à implémenter par chaque robot
        
        Cette méthode doit contenir la logique métier principale
        """
        
        pass
    
    def connect_sage(self) -> bool:
        """
        Connexion à Sage X3
        
        Returns:
            True si connexion réussie
        """
        return self.sage_connector.connect()
    
    def navigate_to_module(self, url: str) -> bool:
        """
        Naviguer vers un module Sage
        
        Args:
            url: URL du module
        
        Returns:
            True si navigation réussie
        """
        return self.sage_connector.navigate_to_module(url)
    
    def add_result(self, result: Dict[str, Any]):
        """
        Ajouter un résultat à la liste
        
        Args:
            result: Dictionnaire contenant les résultats
        """
        self.resultats.append(result)
        self.logger.debug(f"Résultat ajouté: {result}")
    
    def save_report(self, filename: str = None, incremental: bool = False) -> Path:
        """
        Sauvegarder le rapport Excel
        
        Args:
            filename: Nom personnalisé (optionnel)
            incremental: Mode sauvegarde incrémentale
        
        Returns:
            Chemin du fichier sauvegardé
        """
        try:
            # Créer le nom de fichier
            if not filename:
                if incremental and self.rapport_path:
                    filename = self.rapport_path.name
                else:
                    filename = f"rapport_{self.module_name}_{self.timestamp}.xlsx"
            
            # Chemin complet
            if not self.rapport_path or not incremental:
                self.rapport_path = OUTPUT_DIR / 'rapports' / filename
            
            # Créer DataFrame
            df = pd.DataFrame(self.resultats)
            
            # Sauvegarder
            self.rapport_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_excel(self.rapport_path, index=False)
            
            self.logger.info(f"💾 Rapport sauvegardé: {self.rapport_path} ({len(self.resultats)} ligne(s))")
            return self.rapport_path
            
        except Exception as e:
            self.logger.error(f"❌ Erreur sauvegarde rapport: {e}")
            return None
    
    def generate_summary(self) -> Dict[str, Any]:
        """
        Générer un résumé des résultats
        
        Returns:
            Dictionnaire avec statistiques
        """
        if not self.resultats:
            return {'total': 0, 'succes': 0, 'echecs': 0}
        
        df = pd.DataFrame(self.resultats)
        
        summary = {
            'total': len(df),
            'succes': len(df[df.get('statut', '') == 'Succes']) if 'statut' in df.columns else 0,
            'echecs': len(df[df.get('statut', '') != 'Succes']) if 'statut' in df.columns else 0,
            'timestamp': self.timestamp,
            'module': self.module_name,
        }
        
        return summary
    
    def log_summary(self):
        """Afficher le résumé dans les logs"""
        summary = self.generate_summary()
        
        self.logger.info("\n" + "="*80)
        self.logger.info("📊 RÉSUMÉ FINAL")
        self.logger.info("="*80)
        self.logger.info(f"Total: {summary['total']}")
        self.logger.info(f"✅ Succès: {summary['succes']}")
        self.logger.info(f"❌ Échecs: {summary['echecs']}")
        
        if summary['total'] > 0:
            taux = (summary['succes'] / summary['total']) * 100
            self.logger.info(f"📈 Taux de réussite: {taux:.1f}%")
        
        self.logger.info("="*80)
    
    def cleanup(self):
        """Nettoyage et déconnexion"""
        try:
            if self.sage_connector:
                self.sage_connector.disconnect()
            self.logger.info("✅ Nettoyage terminé")
        except Exception as e:
            self.logger.error(f"❌ Erreur nettoyage: {e}")
    
    def run(self, *args, **kwargs):
        """
        Exécuter le robot avec gestion d'erreur
        
        Template Method Pattern
        """
        try:
            self.logger.info(f"🚀 Démarrage: {self.__class__.__name__}")
            
            # Exécuter la logique métier
            result = self.execute(*args, **kwargs)
            
            # Générer le rapport final
            self.log_summary()
            self.save_report()
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Erreur fatale: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise
        
        finally:
            self.cleanup()
    
    def __enter__(self):
        """Context manager: entrée"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: sortie"""
        self.cleanup()
