# -*- coding: utf-8 -*-
"""
API FastAPI pour splitter un PDF de bulletins de paie
par page et nommer chaque fichier selon le matricule de l'employé
"""
import re
import io
import zipfile
from pathlib import Path
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI(
    title="PDF Splitter - Bulletins de Paie",
    description="Split un PDF multi-pages en PDFs individuels nommés par matricule",
    version="1.0.0"
)

OUTPUT_DIR = Path("data/output/bulletins")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_matricule(page_text: str) -> str | None:
    """
    Extrait le matricule depuis le texte d'une page.
    Le matricule est un nombre de 5 chiffres (ex: 70162, 70163).
    """
    # Pattern: cherche le nombre après le mot "Matricule"
    match = re.search(r'Matricule\s*[\n\r]*\s*(\d{5,6})', page_text, re.IGNORECASE)
    if match:
        return match.group(1)

    # Fallback: cherche un nombre isolé de 5 chiffres commençant par 70
    match = re.search(r'\b(70\d{3,4})\b', page_text)
    if match:
        return match.group(1)

    return None


@app.get("/")
async def root():
    return {
        "message": "PDF Splitter API",
        "endpoints": {
            "split_zip": "POST /split  → retourne un ZIP avec tous les PDFs",
            "split_info": "POST /split/info  → retourne la liste des matricules détectés",
        }
    }


@app.post("/split")
async def split_pdf(file: UploadFile = File(...)):
    """
    Upload un PDF → retourne un fichier ZIP contenant un PDF par employé,
    chaque fichier nommé avec le matricule (ex: 70162.pdf).
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF")

    pdf_bytes = await file.read()

    # Lire le PDF avec pypdf pour le split et l'extraction de texte
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)

    if total_pages == 0:
        raise HTTPException(status_code=400, detail="Le PDF est vide")

    zip_buffer = io.BytesIO()
    results = []

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""

            # Extraire le matricule
            matricule = extract_matricule(text)
            filename = f"{matricule}.pdf" if matricule else f"page_{i + 1}.pdf"

            # Créer un PDF d'une seule page
            writer = PdfWriter()
            writer.add_page(page)

            page_buffer = io.BytesIO()
            writer.write(page_buffer)
            page_buffer.seek(0)

            # Ajouter au ZIP
            zf.writestr(filename, page_buffer.read())

            results.append({
                "page": i + 1,
                "matricule": matricule,
                "filename": filename
            })

    zip_buffer.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"bulletins_de_paie_{timestamp}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
    )


@app.post("/split/info")
async def split_pdf_info(file: UploadFile = File(...)):
    """
    Upload un PDF → retourne uniquement la liste des matricules détectés
    sans générer les fichiers (utile pour prévisualiser).
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF")

    pdf_bytes = await file.read()

    results = []

    reader = PdfReader(io.BytesIO(pdf_bytes))
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        matricule = extract_matricule(text)
        results.append({
            "page": i + 1,
            "matricule": matricule,
            "filename": f"{matricule}.pdf" if matricule else f"page_{i + 1}.pdf",
            "texte_extrait": text[:200].strip()
        })

    return JSONResponse({
        "total_pages": len(results),
        "pages": results
    })


@app.post("/split/save")
async def split_pdf_save(file: UploadFile = File(...)):
    """
    Upload un PDF → sauvegarde les PDFs dans data/output/bulletins/
    et retourne la liste des fichiers créés.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF")

    pdf_bytes = await file.read()

    reader = PdfReader(io.BytesIO(pdf_bytes))
    results = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        matricule = extract_matricule(text)
        filename = f"{matricule}.pdf" if matricule else f"page_{i + 1}.pdf"
        output_path = OUTPUT_DIR / filename

        # Créer le PDF individuel
        writer = PdfWriter()
        writer.add_page(page)

        with open(output_path, "wb") as f:
            writer.write(f)

        results.append({
            "page": i + 1,
            "matricule": matricule,
            "filename": filename,
            "path": str(output_path)
        })

    return JSONResponse({
        "total_pages": len(results),
        "output_dir": str(OUTPUT_DIR),
        "fichiers": results
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
