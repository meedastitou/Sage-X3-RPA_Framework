query_ff = """
        WITH 
    -- 1. CTE pour identifier les fournisseurs ayant un règlement
    Fournisseurs_Avec_Reglement AS (
        SELECT DISTINCT pay.BPR_0
        FROM x3.BASE1.PAYMENTH pay
        INNER JOIN BASE1.XREGNLR x ON x.DOCOR_0 = pay.NUM_0
    ),
    -- 2. CTE pour calculer la TVA par facture
    TVA_Factures AS (
        SELECT NUM_0, SUM(AMTTAXLIN1_0) AS TotalTVA
        FROM BASE1.PINVOICED
        GROUP BY NUM_0
    ),
    -- 3. CTE pour préparer les données de base
    Donnies_De_Base AS (
        SELECT
            G.NUM_0                                         AS NumFacture,
            P.BPRVCR_0                                      AS Reference,
            P.BPR_0                                         AS CodeFournisseur,
            P.BPRNAM_0                                      AS Raison,
            G.PAM_0                                         AS ModePaiement,
            G.AMTCUR_0                                      AS Montant,
            (G.AMTCUR_0 - G.PAYCUR_0 - G.TMPCUR_0)          AS ResteAPayer,
            (F.enReception + F.enFacturation + F.facture 
            + F.retourNF + F.Soldedépart + F.Réglement)    AS SoldeFournisseur,
            CASE 
                WHEN G.AMTCUR_0 > 0 
                THEN (T.TotalTVA * (G.AMTCUR_0 - G.PAYCUR_0 - G.TMPCUR_0) / G.AMTCUR_0) 
                ELSE 0 
            END                                             AS MontantTVA
        FROM BASE1.GACCDUDATE G
        INNER JOIN BASE1.PINVOICE P ON P.NUM_0 = G.NUM_0
        INNER JOIN BASE1.SITUATION_FOU F ON F.BPRNUM_0 = P.BPR_0
        LEFT JOIN TVA_Factures T ON T.NUM_0 = P.NUM_0
        WHERE
            G.TYP_0 NOT IN ('ECAHI','FAFHI')
            AND G.TYPDUD_0 = 2
            AND G.DUDSTA_0 = 2
            AND G.BPRTYP_0 = 2
            AND (G.AMTCUR_0 - G.PAYCUR_0 - G.TMPCUR_0) >= 100
            AND (P.XORDRG_0 <> 2 OR P.XDTFNSUI_0 < GETDATE())
            AND (G.AMTCUR_0 - G.PAYCUR_0 - G.TMPCUR_0) > 0
            AND (F.enReception + F.enFacturation + F.facture 
                + F.retourNF + F.Soldedépart + F.Réglement) > 0
            AND G.NUM_0 LIKE 'FF%'
            AND P.BPR_0<>'T3691'

    )

    -- 4. Sélection finale avec alignement parfait des tris (Ordre Croissant du Reste à Payer)
    SELECT
        NumFacture,
        Reference,
        CodeFournisseur,
        Raison,
        ModePaiement,
        Montant,
        ResteAPayer,
        SoldeFournisseur,
        MontantTVA,
        
        -- Le cumul suit STRICTEMENT le même ordre que l'affichage final (ResteAPayer du plus petit au plus grand)
        SUM(ResteAPayer) OVER (
            PARTITION BY CodeFournisseur 
            ORDER BY ResteAPayer ASC, NumFacture ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS CumulResteAPayer,

        -- Calcul de l'écart progressif basé sur ce cumul synchrone
        SoldeFournisseur - SUM(ResteAPayer) OVER (
            PARTITION BY CodeFournisseur 
            ORDER BY ResteAPayer ASC, NumFacture ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS Ecart

    FROM Donnies_De_Base

    ORDER BY 
        CodeFournisseur ASC, 
        ResteAPayer ASC, 
        NumFacture ASC;
    """