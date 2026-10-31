query_sold_fournisseur = f"""
SELECT
    (
    F.Soldedépart +
    F.enReception +
    F.enFacturation +
    F.facture +
    F.retourNF +
    F.Réglement +
    F.ECART_AUT
    ) AS Solde
FROM BASE1.SITUATION_FOU F
WHERE F.BPRNUM_0 = '{{code_fournisseur}}'
"""