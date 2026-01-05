# -*- coding: utf-8 -*-
"""
Configuration centralisée du projet Sage X3 RPA
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Chemins de base
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
INPUT_DIR = DATA_DIR / 'input'
OUTPUT_DIR = DATA_DIR / 'output'
LOGS_DIR = OUTPUT_DIR / 'logs'

# Configuration Sage X3
SAGE_CONFIG = {
    'url': os.getenv('SAGE_URL', 'http://192.168.1.241:8124/'),
    'username': os.getenv('SAGE_USERNAME', 'CPT02'),
    'password': os.getenv('SAGE_PASSWORD', 'ZAINAB@2023'),
    'environment': os.getenv('SAGE_ENVIRONMENT', 'PREPROD'),
    'timeout': int(os.getenv('SAGE_TIMEOUT', '10')),
}
# Configuration Sage X3
SAGE_CONFIG_TEST = {
    'url': os.getenv('SAGE_URL_TEST', 'http://192.168.1.252:8124/'),
    'username': os.getenv('SAGE_USERNAME_TEST', 'dev'),
    'password': os.getenv('SAGE_PASSWORD_TEST', '123456789'),
    'environment': os.getenv('SAGE_ENVIRONMENT_TEST', 'PREPROD'),
    'timeout': int(os.getenv('SAGE_TIMEOUT_TEST', '10')),
}
# Configuration Selenium
SELENIUM_CONFIG = {
    'profile_path': os.getenv('CHROME_PROFILE_PATH', str(BASE_DIR / 'chrome_profile')),
    'headless': os.getenv('CHROME_HEADLESS', 'False').lower() == 'true',
    'download_dir': str(OUTPUT_DIR / 'rapports'),
    'page_load_timeout': int(os.getenv('PAGE_LOAD_TIMEOUT', '90')),
}

# Configuration Base de données
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'database': os.getenv('DB_NAME', 'sage_rpa'),
    'username': os.getenv('DB_USER', 'admin'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'driver': os.getenv('DB_DRIVER', 'mysql'),  # mysql, postgresql, sqlserver
}

# Configuration IA
AI_CONFIG = {
    'provider': os.getenv('AI_PROVIDER', 'groq'),  # groq, openai, anthropic
    'api_key': os.getenv('AI_API_KEY', ''),
    'base_url': os.getenv('AI_BASE_URL', 'https://api.groq.com/openai/v1'),
    'model': os.getenv('AI_MODEL', 'llama-3.3-70b-versatile'),
    'temperature': float(os.getenv('AI_TEMPERATURE', '0.1')),
}

# Configuration Logging
LOGGING_CONFIG = {
    'level': os.getenv('LOG_LEVEL', 'INFO'),
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
    'file_enabled': True,
    'console_enabled': True,
}

# Configuration Modules
MODULES_CONFIG = {
    'lettrage': {
        'enabled': True,
        'max_retries': 3,
        'retry_delay': 3,  # secondes
        'save_incremental': True,
    },
    'facturation': {
        'enabled': False,
        'max_retries': 3,
    },
    'reporting': {
        'enabled': False,
    }
}

# Créer les dossiers s'ils n'existent pas
for directory in [DATA_DIR, INPUT_DIR, OUTPUT_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
