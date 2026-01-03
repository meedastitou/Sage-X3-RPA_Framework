# -*- coding: utf-8 -*-
"""
Configuration pour l'envoi des résultats vers le web
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration de l'endpoint web
WEB_ENDPOINT_CONFIG = {
    # URL de l'endpoint pour recevoir les résultats
    'url': os.getenv('WEB_ENDPOINT_URL', 'http://jbel-annour.ma/resultat'),
    
    # Timeout en secondes
    'timeout': int(os.getenv('WEB_ENDPOINT_TIMEOUT', '30')),
    
    # Activer/désactiver l'envoi
    'enabled': os.getenv('WEB_ENDPOINT_ENABLED', 'True').lower() == 'true',
    
    # Mode d'envoi: 'json', 'multipart', 'base64'
    'mode': os.getenv('WEB_ENDPOINT_MODE', 'json'),
    
    # Inclure le fichier rapport Excel
    'include_file': os.getenv('WEB_ENDPOINT_INCLUDE_FILE', 'True').lower() == 'true',
    
    # Headers personnalisés (optionnel)
    'headers': {
        'Authorization': os.getenv('WEB_ENDPOINT_AUTH_TOKEN', ''),
        'X-API-Key': os.getenv('WEB_ENDPOINT_API_KEY', '')
    },
    
    # Retry en cas d'échec
    'retry_enabled': os.getenv('WEB_ENDPOINT_RETRY', 'True').lower() == 'true',
    'retry_count': int(os.getenv('WEB_ENDPOINT_RETRY_COUNT', '3')),
    'retry_delay': int(os.getenv('WEB_ENDPOINT_RETRY_DELAY', '5'))
}
