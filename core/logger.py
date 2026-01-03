# -*- coding: utf-8 -*-
"""
Système de logging centralisé
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from config.settings import LOGGING_CONFIG, LOGS_DIR

class Logger:
    """Gestionnaire de logs centralisé"""
    
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name: str, module: str = None) -> logging.Logger:
        """
        Obtenir un logger configuré
        
        Args:
            name: Nom du logger
            module: Module (lettrage, facturation, etc.)
        
        Returns:
            Logger configuré
        """
        # Créer une clé unique
        key = f"{module}.{name}" if module else name
        
        # Retourner le logger s'il existe déjà
        if key in cls._loggers:
            return cls._loggers[key]
        
        # Créer un nouveau logger
        logger = logging.getLogger(key)
        logger.setLevel(getattr(logging, LOGGING_CONFIG['level']))
        
        # Éviter les doublons de handlers
        if logger.handlers:
            return logger
        
        # Formatter
        formatter = logging.Formatter(
            LOGGING_CONFIG['format'],
            datefmt=LOGGING_CONFIG['date_format']
        )
        
        # Console Handler
        if LOGGING_CONFIG['console_enabled']:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # File Handler
        if LOGGING_CONFIG['file_enabled']:
            # Créer le nom de fichier avec timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_filename = f"{module or 'app'}_{timestamp}.log"
            log_path = LOGS_DIR / log_filename
            
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        # Stocker le logger
        cls._loggers[key] = logger
        
        return logger
    
    @classmethod
    def info(cls, name: str, message: str, module: str = None):
        """Log niveau INFO"""
        logger = cls.get_logger(name, module)
        logger.info(message)
    
    @classmethod
    def warning(cls, name: str, message: str, module: str = None):
        """Log niveau WARNING"""
        logger = cls.get_logger(name, module)
        logger.warning(message)
    
    @classmethod
    def error(cls, name: str, message: str, module: str = None):
        """Log niveau ERROR"""
        logger = cls.get_logger(name, module)
        logger.error(message)
    
    @classmethod
    def debug(cls, name: str, message: str, module: str = None):
        """Log niveau DEBUG"""
        logger = cls.get_logger(name, module)
        logger.debug(message)
    
    @classmethod
    def critical(cls, name: str, message: str, module: str = None):
        """Log niveau CRITICAL"""
        logger = cls.get_logger(name, module)
        logger.critical(message)
