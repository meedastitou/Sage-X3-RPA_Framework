# 📦 Module Bonne de Commande - Structure Optimisée

## 🎯 Problème Résolu

**Avant** : Code inefficace avec double boucle
-  Boucle 1 : Traiter tous les articles (même en double)
-  Boucle 2 : Traiter toutes les DAs (même en double)
-  Navigation répétée entre les modules
-  Traitement redondant

**Maintenant** : Structure optimisée et professionnelle
- Regroupement intelligent des données
- Traitement unique par article
- Traitement unique par DA
- Navigation efficace (1 seule fois par module)

##  Structure des Données

### Exemple Excel :
```
Numero_DA    | Acheteur | Code_Fournisseur | Code_Article | Montant
DA-2025-001  | RACH     | T1231            | A0005        | 151
DA-2025-001  | RACH     | T1231            | A00002       | 56
DA-2025-002  | RACH     | T1231            | A10003       | 9595
```

### Transformation en structure :
```python
{
    'fournisseur': 'T1231',
    'das': {
        'DA-2025-001': {
            'acheteur': 'RACH',
            'articles': [
                {'code': 'A0005', 'montant': 151},
                {'code': 'A00002', 'montant': 56}
            ]
        },
        'DA-2025-002': {
            'acheteur': 'RACH',
            'articles': [
                {'code': 'A10003', 'montant': 9595}
            ]
        }
    },
    'tous_articles': {
        'A0005': {'montant': 151},
        'A00002': {'montant': 56},
        'A10003': {'montant': 9595}
    }
}
```

## Flux d'Exécution

### 1. Lecture et Validation
- Lire le fichier Excel
- Vérifier les colonnes requises
- Supprimer les lignes invalides

### 2. Regroupement
- Identifier le fournisseur unique
- Regrouper les articles par DA
- Identifier les articles uniques

### 3. Affichage Résumé
```
🏢 Fournisseur: T1231
📦 3 Article(s) unique(s) à traiter:
   • A0005: 151 MAD
   • A00002: 56 MAD
   • A10003: 9595 MAD

📋 2 Demande(s) d'Achat à traiter:
   • DA-2025-001 (RACH): 2 article(s)
   • DA-2025-002 (RACH): 1 article(s)
```

### 4. Traitement Articles
```
🔧 TRAITEMENT DES ARTICLES
─────────────────────────────
📦 Article 1/3: A0005
   Article A0005 traité

📦 Article 2/3: A00002
   Article A00002 traité

📦 Article 3/3: A10003
   Article A10003 traité
```

### 5. Traitement DAs
```
📋 TRAITEMENT DES DEMANDES D'ACHAT
─────────────────────────────────
📋 DA 1/2: DA-2025-001
   Acheteur: RACH
   Articles: 2
   DA DA-2025-001 traitée

📋 DA 2/2: DA-2025-002
   Acheteur: RACH
   Articles: 1
   DA DA-2025-002 traitée
```

## 💻 Utilisation

### Commande de base
```bash
python scripts/run_bonne_commande.py --file data/input/excel/commandes.xlsx
```

### Mode headless
```bash
python scripts/run_bonne_commande.py --file commandes.xlsx --headless
```

## 📋 Format Excel Requis

Colonnes obligatoires :
- `Numero_DA` : Numéro de la demande d'achat
- `Acheteur` : Nom de l'acheteur
- `Code_Fournisseur` : Code du fournisseur
- `Email_Fournisseur` : Email du fournisseur
- `TEL_Fournisseu` : Téléphone du fournisseur
- `Code_Article` : Code de l'article
- `Montant` : Montant/Tarif

## 🎯 Optimisations Appliquées

### 1. Regroupement Intelligent
- **Avant** : 3 lignes Excel → 6 traitements (3 articles + 3 DAs)
- **Maintenant** : 3 lignes Excel → 5 traitements (3 articles uniques + 2 DAs uniques)

### 2. Navigation Efficace
- **Avant** : Navigate → Article1 → Navigate → Article2 → Navigate → Article3 → Navigate → DA1 → Navigate → DA2
- **Maintenant** : Navigate → Article1 → Article2 → Article3 → Navigate → DA1 → DA2

### 3. Code Modulaire
- Méthodes privées `_lire_et_valider_excel()`
- Méthodes privées `_regrouper_donnees()`
- Méthodes privées `_afficher_resume()`
- Méthodes privées `_traiter_tous_articles()`
- Méthodes privées `_traiter_toutes_das()`
- Méthodes publiques `traiter_article()`
- Méthodes publiques `traiter_demande_achat()`

### 4. Gestion d'Erreurs
- Validation des données
- Try/catch à chaque étape
- Screenshots en cas d'erreur
- Logs détaillés

### 5. Rapports
- Résultats enregistrés après chaque phase
- Rapport Excel final
- Logs complets

##  Rapport Généré

Le rapport Excel contient :
- Type (Article/Demande_Achat)
- Code article / Numéro DA
- Fournisseur
- Montant
- Statut (Succès/Échec)
- Message d'erreur si échec

## 🔧 Personnalisation

Pour adapter le code à vos besoins :
1. Modifier les IDs des champs dans `traiter_article()`
2. Modifier les IDs des champs dans `traiter_demande_achat()`
3. Ajouter des validations supplémentaires
4. Modifier la structure de regroupement si nécessaire

## 📈 Performance

Pour un fichier avec 100 lignes :
- **Avant** : ~200 opérations (100 articles + 100 DAs)
- **Maintenant** : ~150 opérations (50 articles uniques + 100 DAs)
- **Gain** : 25% plus rapide

---

**Structure professionnelle et scalable !**
