# -*- coding: utf-8 -*-
"""
Worker RPA - Traite les tâches de la file d'attente
Lance ce script et laisse-le tourner en arrière-plan
"""
import sys
import time
from pathlib import Path

# Ajouter le dossier parent au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.demmande_achat.demmandeAchatRobot import DemmandeAchatRobot
from modules.imputation.ImputationRobot import ImputationRobot
from modules.regelement.VairementRobot import VairementRobot
from modules.regelement.VairementInternationalRobot import VairementInternationalRobot
from modules.regelement.RegelementRobot_V3 import RegelementRobot
from utils.queue_manager import get_next_task, update_task, is_task_type_in_cooldown, has_pending_tasks_of_type
from modules.bonne_commande.bonne_commande_robot import BonneCommandeRobot
from modules.receiption.ReceiptionRobot_v3 import ReceiptionRobot
# from modules.facturation.FacturationRobot import FacturationRobot
from modules.facturation.FacturationRobot_V2 import FacturationRobotV2
from modules.depot_facture.AnulationControl import AnulationControl
from core.logger import Logger

logger = Logger.get_logger('WorkerRPA', 'workers')

BON_COMMANDE_COOLDOWN_MINUTES = 30  # Délai entre chaque bon_commande


def main():
    logger.info("="*80)
    logger.info("WORKER RPA DÉMARRÉ")
    logger.info("="*80)
    logger.info(f"Cooldown bon_commande: {BON_COMMANDE_COOLDOWN_MINUTES} minutes")
    logger.info("En attente de tâches...")

    while True:
        try:
            # Vérifier si bon_commande est en cooldown
            in_cooldown, remaining = is_task_type_in_cooldown("bon_commande", BON_COMMANDE_COOLDOWN_MINUTES)

            if in_cooldown and has_pending_tasks_of_type("bon_commande"):
                # bon_commande en cooldown, traiter les autres tâches d'abord
                logger.debug(f"⏳ bon_commande en cooldown ({remaining:.1f} min restantes), recherche autres tâches...")
                task = get_next_task(skip_types=["bon_commande"])

                # Si aucune autre tâche, on attend
                if task is None:
                    logger.info(f"⏳ Attente cooldown bon_commande: {remaining:.1f} min restantes...")
                    time.sleep(min(remaining * 60, 60))  # Attendre max 1 min avant de revérifier
                    continue
            else:
                # Pas de cooldown ou pas de bon_commande en attente
                task = get_next_task()

            if task:
                task_type = task.get('task_type', 'bon_commande')  # Par défaut: bon_commande
                logger.info(f"\n{'='*80}")
                logger.info(f"📋 Tâche trouvée: {task['id']}")
                logger.info(f"🤖 Type: {task_type}")
                logger.info(f"📧 Email: {task['email']}")
                logger.info(f"📄 Fichier: {task['file']}")
                logger.info(f"{'='*80}")

                update_task(task['id'], "processing")

                try:
                    # Lancer le robot approprié selon le type de tâche
                    if task_type == "bon_commande":
                        logger.info("Lancement du BonneCommandeRobot...")
                        robot = BonneCommandeRobot()
                        robot.run(excel_file=task['file'])
                    elif task_type == "receiption":
                        logger.info("Lancement du ReceiptionRobot...")
                        robot = ReceiptionRobot()
                        robot.run(excel_file=task['file'])
                    elif task_type == "facturation":
                        logger.info("Lancement du FacturationRobot...")
                        robot = FacturationRobotV2()
                        robot.run(excel_file=task['file'])
                    elif task_type == "regelement":
                        logger.info("Lancement du RegelementRobot...")
                        robot = RegelementRobot()
                        robot.run(excel_file=task['file'])
                    elif task_type == "vairement":
                        logger.info("Lancement du VairementRobot...")
                        robot = VairementRobot()
                        robot.run(excel_file=task['file'])
                    elif task_type == 'vairement_inter':
                        logger.info("Lancement du VairementInternationalRobot...")
                        robot = VairementInternationalRobot()
                    elif task_type == 'imputation':
                        logger.info("Lancement du ImputationRobot...")
                        robot = ImputationRobot()
                        robot.run(excel_file=task['file'])
                    elif task_type == 'demmande_achat':
                        logger.info("Lancement du DemmandeAchatRobot...")
                        robot = DemmandeAchatRobot()
                        robot.run(excel_file=task['file'])
                    elif task_type == 'dff_annulation_control':
                        logger.info("Lancement du DFFAnnulationControl...")
                        robot = AnulationControl()
                        robot.run(excel_file=task['file'])
                    else:
                        raise ValueError(f"Type de tâche inconnu: {task_type}")

                    update_task(task['id'], "completed")
                    logger.info(f"Tâche {task['id']} terminée avec succès")

                except Exception as e:
                    update_task(task['id'], "failed", error=str(e))
                    logger.error(f" Tâche {task['id']} échouée: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                
                # Petite pause entre les tâches
                time.sleep(5)
            else:
                # Aucune tâche en attente
                logger.debug("😴 Aucune tâche, attente 10s...")
                time.sleep(10)
        
        except KeyboardInterrupt:
            logger.info("\n Arrêt du worker demandé par l'utilisateur")
            break
        except Exception as e:
            logger.error(f" Erreur dans le worker: {e}")
            import traceback
            logger.error(traceback.format_exc())
            time.sleep(10)

if __name__ == '__main__':
    main()