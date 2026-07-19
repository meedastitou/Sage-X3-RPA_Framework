# -*- coding: utf-8 -*-
"""
DBHandler - Gestionnaire base de données MySQL pour Sage X3 RPA
Enregistre toutes les actions : executions, facturations, logs
"""
import json
import logging
from datetime import datetime
from typing import Optional

import mysql.connector
from mysql.connector import Error as MySQLError

from config.settings import DATABASE_CONFIG
from core.logger import Logger


class DBHandler:
    """
    Gestionnaire MySQL pour le logging des actions RPA.

    Usage:
        db = DBHandler()
        exec_id = db.start_execution('facturation', 'fichier.xlsx')
        fact_id = db.log_facture(exec_id, facture_frs='FN001', ...)
        db.update_facture(fact_id, statut='SUCCES', numero_piece='PIH0001')
        db.log(exec_id, 'INFO', 'Traitement termine', entity_type='facturation', entity_id=fact_id)
        db.end_execution(exec_id, statut='SUCCES', nb_succes=4, nb_echec=0)
    """

    def __init__(self):
        self.logger = Logger.get_logger('DBHandler', 'db')
        self._conn = None
        self.logger.info("Initialisation du DBHandler...")
        self._connect()

    # ------------------------------------------------------------------
    # Connexion
    # ------------------------------------------------------------------

    def _connect(self):
        try:
            self.logger.info("Tentative de connexion a MySQL...")
            self._conn = mysql.connector.connect(
                host=DATABASE_CONFIG['host'],
                port=DATABASE_CONFIG['port'],
                database=DATABASE_CONFIG['database'],
                user=DATABASE_CONFIG['username'],
                password=DATABASE_CONFIG['password'],
                charset='utf8mb4',
                autocommit=True,
                connection_timeout=10,
            )
            self.logger.info("Connexion MySQL etablie")
        except MySQLError as e:
            self.logger.error(f"Connexion MySQL echouee: {e}")
            self._conn = None
            raise  # Re-raise the exception to fail __init__

    def _ensure_connected(self) -> bool:
        """Reconnecte si la connexion est perdue."""
        try:
            if self._conn and self._conn.is_connected():
                return True
            self.logger.warning("Connexion MySQL perdue, tentative de reconnexion...")
            self._connect()
            return self._conn is not None
        except Exception:
            return False

    def close(self):
        if self._conn and self._conn.is_connected():
            self._conn.close()
            self.logger.info("Connexion MySQL fermee")

    # ------------------------------------------------------------------
    # rpa_executions
    # ------------------------------------------------------------------

    def start_execution(self, module: str, fichier_excel: str = None) -> Optional[int]:
        """
        Crée une ligne dans rpa_executions au démarrage du robot.

        Returns:
            execution_id ou None si erreur
        """
        if not self._ensure_connected():
            return None
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO rpa_executions (module, fichier_excel, statut)
                VALUES (%s, %s, 'EN_COURS')
                """,
                (module, fichier_excel)
            )
            execution_id = cursor.lastrowid
            cursor.close()
            self.logger.info(f"Execution demarree: id={execution_id}, module={module}")
            return execution_id
        except MySQLError as e:
            self.logger.error(f"start_execution erreur: {e}")
            return None

    def end_execution(self, execution_id: int, statut: str,
                      nb_succes: int = 0, nb_echec: int = 0,
                      message: str = None):
        """
        Met à jour rpa_executions à la fin du robot.

        Args:
            statut: 'SUCCES' | 'PARTIEL' | 'ECHEC'
        """
        if not self._ensure_connected():
            return
        try:
            total = nb_succes + nb_echec
            cursor = self._conn.cursor()
            cursor.execute(
                """
                UPDATE rpa_executions
                SET finished_at = %s,
                    statut      = %s,
                    total       = %s,
                    nb_succes   = %s,
                    nb_echec    = %s,
                    message     = %s
                WHERE id = %s
                """,
                (datetime.now(), statut, total, nb_succes, nb_echec, message, execution_id)
            )
            cursor.close()
            self.logger.info(f"Execution {execution_id} terminee: {statut} ({nb_succes} succes, {nb_echec} echecs)")
        except MySQLError as e:
            self.logger.error(f"end_execution erreur: {e}")

    # ------------------------------------------------------------------
    # rpa_facturations
    # ------------------------------------------------------------------

    def log_facture(self, execution_id: int,
                    facture_frs: str,
                    code_fournisseur: str,
                    codes_reception: list,
                    nom_fournisseur: str = None,
                    dff: str = None,
                    date_facture: str = None) -> Optional[int]:
        """
        Insère une ligne dans rpa_facturations au début du traitement.

        Args:
            date_facture: format 'DD/MM/YYYY' ou 'YYYY-MM-DD'

        Returns:
            facture_id ou None si erreur
        """
        if not self._ensure_connected():
            return None
        try:
            date_sql = self._parse_date(date_facture)
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO rpa_facturations
                    (execution_id, facture_frs, code_fournisseur, nom_fournisseur,
                     dff, date_facture, codes_reception, statut)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'ECHEC')
                """,
                (
                    execution_id,
                    facture_frs,
                    code_fournisseur,
                    nom_fournisseur,
                    dff,
                    date_sql,
                    json.dumps(codes_reception, ensure_ascii=False),
                )
            )
            facture_id = cursor.lastrowid
            cursor.close()
            self.logger.info(f"Facture enregistree: id={facture_id}, frs={facture_frs}")
            return facture_id
        except MySQLError as e:
            self.logger.error(f"log_facture erreur: {e}")
            return None

    def update_facture(self, facture_id: int, statut: str,
                       message: str = None,
                       numero_piece: str = None,
                       screenshot_path: str = None):
        """
        Met à jour le résultat d'une facture après traitement.

        Args:
            statut: 'SUCCES' | 'ECHEC' | 'PARTIEL'
        """
        if not self._ensure_connected():
            return
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                UPDATE rpa_facturations
                SET statut          = %s,
                    message         = %s,
                    numero_piece    = %s,
                    screenshot_path = %s
                WHERE id = %s
                """,
                (statut, message, numero_piece, screenshot_path, facture_id)
            )
            cursor.close()
            self.logger.info(f"Facture {facture_id} mise a jour: {statut}")
        except MySQLError as e:
            self.logger.error(f"update_facture erreur: {e}")

    # ------------------------------------------------------------------
    # rpa_regelements
    # ------------------------------------------------------------------

    def log_regelement(self, execution_id: int,
                       code_fournisseur: str,
                       num_facture: str = None,
                       reference: str = None,
                       montant: float = None,
                       tva: float = None,
                       type_regelement: str = None,
                       nom_fournisseur: str = None) -> Optional[int]:
        """
        Insère une ligne dans rpa_regelements au début du traitement.

        Returns:
            regelement_id ou None si erreur
        """
        if not self._ensure_connected():
            return None
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO rpa_regelements
                    (execution_id, code_fournisseur, nom_fournisseur, num_facture,
                     reference, montant, tva, type_regelement, statut)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ECHEC')
                """,
                (
                    execution_id,
                    code_fournisseur,
                    nom_fournisseur,
                    num_facture,
                    reference,
                    montant,
                    tva,
                    type_regelement,
                )
            )
            regelement_id = cursor.lastrowid
            cursor.close()
            self.logger.info(f"Regelement enregistre: id={regelement_id}, frs={code_fournisseur}")
            return regelement_id
        except MySQLError as e:
            self.logger.error(f"log_regelement erreur: {e}")
            return None

    def update_regelement(self, regelement_id: int, statut: str,
                          message: str = None,
                          numero_piece: str = None,
                          screenshot_path: str = None):
        """
        Met à jour le résultat d'un règlement après traitement.

        Args:
            statut: 'SUCCES' | 'ECHEC' | 'PARTIEL'
        """
        if not self._ensure_connected():
            return
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                UPDATE rpa_regelements
                SET statut          = %s,
                    message         = %s,
                    numero_piece    = %s,
                    screenshot_path = %s
                WHERE id = %s
                """,
                (statut, message, numero_piece, screenshot_path, regelement_id)
            )
            cursor.close()
            self.logger.info(f"Regelement {regelement_id} mis a jour: {statut}")
        except MySQLError as e:
            self.logger.error(f"update_regelement erreur: {e}")

    def check_regelement_exists(self, num_facture: str, days_threshold: int = 3) -> dict:
        """
        Vérifie si un règlement avec ce numéro de facture existe déjà en statut SUCCES.

        Args:
            num_facture: Numéro de facture à vérifier
            days_threshold: Nombre de jours avant d'autoriser un nouveau règlement (défaut: 3)

        Returns:
            dict avec:
                - exists: bool - True si un règlement SUCCES existe
                - can_retry: bool - True si plus de X jours se sont écoulés
                - days_ago: int - Nombre de jours depuis le dernier règlement
                - last_date: datetime - Date du dernier règlement
                - numero_piece: str - Numéro de pièce du dernier règlement
        """
        result = {
            'exists': False,
            'can_retry': True,
            'days_ago': None,
            'last_date': None,
            'numero_piece': None
        }

        if not num_facture or not self._ensure_connected():
            return result

        try:
            cursor = self._conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, numero_piece, created_at,
                       DATEDIFF(NOW(), created_at) AS days_ago
                FROM rpa_regelements
                WHERE num_facture = %s
                  AND statut = 'SUCCES'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (num_facture,)
            )
            row = cursor.fetchone()
            cursor.close()

            if row:
                result['exists'] = True
                result['days_ago'] = row['days_ago']
                result['last_date'] = row['created_at']
                result['numero_piece'] = row['numero_piece']
                result['can_retry'] = row['days_ago'] >= days_threshold

                self.logger.info(
                    f"Regelement existant pour {num_facture}: "
                    f"piece={row['numero_piece']}, il y a {row['days_ago']} jour(s)"
                )

            return result

        except MySQLError as e:
            self.logger.error(f"check_regelement_exists erreur: {e}")
            return result

    # ------------------------------------------------------------------
    # rpa_logs
    # ------------------------------------------------------------------

    def log(self, execution_id: int, level: str, message: str,
            context: str = None,
            entity_type: str = None,
            entity_id: int = None):
        """
        Insère un log détaillé.

        Args:
            level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG'
            entity_type: 'facturation' | 'receiption' | None (log general)
            entity_id: ID dans la table correspondante
        """
        if not self._ensure_connected():
            return
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO rpa_logs
                    (execution_id, entity_type, entity_id, level, message, context)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (execution_id, entity_type, entity_id, level.upper(), message, context)
            )
            cursor.close()
        except MySQLError as e:
            self.logger.error(f"log erreur: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_date(self, date_str: str) -> Optional[str]:
        """
        Convertit 'DD/MM/YYYY' ou 'YYYY-MM-DD' en 'YYYY-MM-DD' pour MySQL.
        Retourne None si invalide.
        """
        if not date_str:
            return None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
            try:
                return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        self.logger.warning(f"Format date non reconnu: {date_str}")
        return None
