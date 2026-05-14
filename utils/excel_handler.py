# -*- coding: utf-8 -*-
"""
Utilitaires pour la manipulation de fichiers Excel
"""
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
from core.logger import Logger

class ExcelHandler:
    """Gestionnaire de fichiers Excel"""
    
    def __init__(self):
        self.logger = Logger.get_logger('ExcelHandler', 'utils')
    
    def read_excel(self, filepath: str, required_columns: List[str] = None) -> pd.DataFrame:
        """
        Lire un fichier Excel avec validation
        
        Args:
            filepath: Chemin du fichier
            required_columns: Colonnes requises
        
        Returns:
            DataFrame pandas
        """
        try:
            self.logger.info(f"📖 Lecture Excel: {filepath}")
            df = pd.read_excel(filepath)
            
            self.logger.info(f"{len(df)} ligne(s) lues")
            
            # Valider les colonnes requises
            if required_columns:
                missing = [col for col in required_columns if col not in df.columns]
                if missing:
                    raise ValueError(f"Colonnes manquantes: {missing}")
            
            return df
            
        except Exception as e:
            self.logger.error(f" Erreur lecture Excel: {e}")
            raise
    
    def write_excel(self, df: pd.DataFrame, filepath: str, sheet_name: str = 'Sheet1'):
        """
        Écrire un DataFrame dans Excel
        
        Args:
            df: DataFrame à sauvegarder
            filepath: Chemin de destination
            sheet_name: Nom de la feuille
        """
        try:
            # Créer le dossier si nécessaire
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            
            df.to_excel(filepath, sheet_name=sheet_name, index=False)
            self.logger.info(f"💾 Excel sauvegardé: {filepath}")
            
        except Exception as e:
            self.logger.error(f" Erreur écriture Excel: {e}")
            raise
    
    def validate_data(self, df: pd.DataFrame, rules: Dict[str, Any]) -> List[str]:
        """
        Valider les données selon des règles
        
        Args:
            df: DataFrame à valider
            rules: Dictionnaire de règles de validation
        
        Returns:
            Liste des erreurs (vide si tout est ok)
        """
        errors = []
        
        for column, rule in rules.items():
            if column not in df.columns:
                errors.append(f"Colonne manquante: {column}")
                continue
            
            # Vérifier les valeurs null
            if rule.get('not_null', False):
                null_count = df[column].isnull().sum()
                if null_count > 0:
                    errors.append(f"{column}: {null_count} valeur(s) null")
            
            # Vérifier le type
            if 'type' in rule:
                expected_type = rule['type']
                if expected_type == 'string':
                    invalid = df[~df[column].apply(lambda x: isinstance(x, str) or pd.isna(x))]
                    if len(invalid) > 0:
                        errors.append(f"{column}: {len(invalid)} valeur(s) non-string")
        
        return errors
