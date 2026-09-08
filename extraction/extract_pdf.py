"""
==============================================================
AGRO-EXPERT PEPPER — Script d'extraction OCR du livre IPC
==============================================================
Extraction complète du PDF scanné :
  - OCR de toutes les pages via Claude Vision API
  - Structuration automatique des données par maladie/ravageur
  - Export JSON prêt à ingérer dans Supabase

Usage :
    python extract_pdf.py --pdf PATH_TO_PDF --output ./data
    python extract_pdf.py --pdf PATH_TO_PDF --pages 19-28 --output ./data

Auteur : projet poivrier-diagnostic-ai
"""

import anthropic
import pymupdf
import base64
import json
import os
import time
import argparse
import logging
from pathlib import Path
from typing import Optional

# ─── Configuration ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("extraction.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# Structure du livre IPC — sections identifiées par audit
BOOK_STRUCTURE = {
    "front_matter": {"pages": [1, 16], "type": "meta"},
    "major_diseases_intro": {"pages": [17, 18], "type": "section_header"},
    "phytophthora_rots": {
        "pages": [19, 28],
        "type": "disease",
        "slug": "phytophthora-rots",
        "name_en": "Phytophthora rots",
        "name_fr": "Pourriture à Phytophthora"
    },
    "slow_decline": {
        "pages": [29, 35],
        "type": "disease",
        "slug": "slow-decline-yellows",
        "name_en": "Slow Decline (Yellows)",
        "name_fr": "Déclin lent (Jaunisse)"
    },
    "root_rot_fusarium": {
        "pages": [37, 40],
        "type": "disease",
        "slug": "root-rot-fusarium",
        "name_en": "Root Rot (Fusarium solani)",
        "name_fr": "Pourriture racinaire (Fusarium)"
    },
    "yellow_wilt": {
        "pages": [39, 40],
        "type": "disease",
        "slug": "yellow-wilt",
        "name_en": "Yellow Wilt",
        "name_fr": "Flétrissement jaune"
    },
    "anthracnose": {
        "pages": [41, 44],
        "type": "disease",
        "slug": "anthracnose-disease",
        "name_en": "Anthracnose disease",
        "name_fr": "Anthracnose"
    },
    "stunted_disease": {
        "pages": [45, 52],
        "type": "disease",
        "slug": "stunted-disease-complex",
        "name_en": "Stunted disease complex",
        "name_fr": "Complexe de rabougrissement"
    },
    "velvet_blight": {
        "pages": [53, 54],
        "type": "disease",
        "slug": "velvet-blight",
        "name_en": "Velvet Blight",
        "name_fr": "Brûlure veloutée"
    },
    "white_root_rot": {
        "pages": [55, 60],
        "type": "disease",
        "slug": "white-root-rot",
        "name_en": "White Root Rot",
        "name_fr": "Pourriture blanche des racines"
    },
    "stump_rot": {
        "pages": [61, 64],
        "type": "disease",
        "slug": "stump-rot",
        "name_en": "Stump Rot",
        "name_fr": "Pourriture du collet"
    },
    "phyllody_disease": {
        "pages": [65, 68],
        "type": "disease",
        "slug": "phyllody-disease",
        "name_en": "Phyllody disease",
        "name_fr": "Maladie phyllode"
    },
    "insect_pests_intro": {"pages": [69, 70], "type": "section_header"},
    "stem_borer": {
        "pages": [71, 75],
        "type": "pest",
        "slug": "stem-borer",
        "name_en": "Stem Borer",
        "name_fr": "Foreur de tiges"
    },
    "mealy_bug": {
        "pages": [77, 79],
        "type": "pest",
        "slug": "mealy-bug",
        "name_en": "Mealy Bug",
        "name_fr": "Cochenille farineuse"
    },
    "tingid_bug": {
        "pages": [81, 83],
        "type": "pest",
        "slug": "tingid-bug",
        "name_en": "Tingid Bug",
        "name_fr": "Punaise tingide"
    },
    "pollu_beetle": {
        "pages": [85, 91],
        "type": "pest",
        "slug": "pollu-beetle",
        "name_en": '"Pollu" Beetle',
        "name_fr": 'Coléoptère "Pollu"'
    },
    "scale_insect": {
        "pages": [93, 95],
        "type": "pest",
        "slug": "scale-insect",
        "name_en": "Scale Insect",
        "name_fr": "Cochenille à bouclier"
    },
    "topshoot_borer": {
        "pages": [97, 99],
        "type": "pest",
        "slug": "topshoot-borer",
        "name_en": "Topshoot Borer",
        "name_fr": "Foreur des pousses apicales"
    },
    "leaf_gall_thrips": {
        "pages": [97, 100],
        "type": "pest",
        "slug": "leaf-gall-thrips",
        "name_en": "Leaf Gall Thrips",
        "name_fr": "Thrips des galles foliaires"
    },
    "minor_pests": {
        "pages": [101, 102],
        "type": "pest",
        "slug": "minor-pests",
        "name_en": "Minor Pests",
        "name_fr": "Ravageurs mineurs"
    },
    "nursery_management": {"pages": [103, 110], "type": "management"},
    "annexes": {"pages": [111, 116], "type": "appendix"}
}

# Prompt OCR structuré pour Claude Vision
OCR_SYSTEM_PROMPT = """You are an expert agronomist and OCR specialist extracting scientific data 
from a scanned book about black pepper (Piper nigrum) diseases and pests.
Extract ALL text exactly as written, preserving scientific names in italics.
Return ONLY valid JSON, no markdown, no explanations."""

OCR_USER_PROMPT = """Extract ALL text from this page of the IPC book "Diseases and Insect Pests 
of Black Pepper". 

Return a JSON object with this exact structure:
{
  "page_number": <integer>,
  "section_title": "<title if visible, else null>",
  "disease_summary_table": {
    "causal_organism": "<value or null>",
    "distribution": "<value or null>",
    "plant_parts_affected": "<value or null>"
  },
  "text_blocks": [
    {
      "heading": "<heading text or null>",
      "content": "<full paragraph text>"
    }
  ],
  "image_captions": ["<caption 1>", "<caption 2>"],
  "page_type": "<one of: cover, content, section_header, blank>",
  "raw_text": "<all text concatenated, preserving structure>"
}

Rules:
- Extract every single word visible on the page
- Preserve scientific names exactly (Phytophthora capsici, etc.)
- Extract all dosage information precisely (0.2%, 5-10 litres/vine, etc.)
- Extract all treatment details completely
- If a word is unclear, mark it as [unclear]"""


def pdf_page_to_base64(doc: pymupdf.Document, page_num: int, dpi: int = 200) -> str:
    """Convertit une page PDF en image base64 pour Claude Vision."""
    page = doc[page_num]
    mat = pymupdf.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=pymupdf.csRGB)
    img_bytes = pix.tobytes("jpeg", jpg_quality=92)
    return base64.standard_b64encode(img_bytes).decode("utf-8")


def ocr_page_with_claude(
    client: anthropic.Anthropic,
    doc: pymupdf.Document,
    page_num: int,
    retries: int = 3
) -> Optional[dict]:
    """OCR d'une page avec Claude Vision. Retourne JSON structuré."""
    for attempt in range(retries):
        try:
            img_b64 = pdf_page_to_base64(doc, page_num)

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=OCR_SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": OCR_USER_PROMPT + f"\n\nThis is page {page_num + 1} of the book."
                        }
                    ]
                }]
            )

            text = response.content[0].text.strip()
            # Nettoyer les éventuels backticks markdown
            text = text.replace("```json", "").replace("```", "").strip()
            result = json.loads(text)
            result["page_number"] = page_num + 1  # Force le bon numéro
            log.info(f"  ✅ Page {page_num + 1} extraite ({len(text)} chars)")
            return result

        except json.JSONDecodeError as e:
            log.warning(f"  ⚠️  Page {page_num + 1} JSON invalide (tentative {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(2)
        except anthropic.RateLimitError:
            wait = 30 * (attempt + 1)
            log.warning(f"  ⏳ Rate limit, attente {wait}s...")
            time.sleep(wait)
        except Exception as e:
            log.error(f"  ❌ Page {page_num + 1} erreur: {e}")
            if attempt < retries - 1:
                time.sleep(5)

    return {"page_number": page_num + 1, "error": "OCR failed after retries", "raw_text": ""}


def extract_images_from_pdf(doc: pymupdf.Document, output_dir: Path) -> list[dict]:
    """Extrait toutes les images du PDF et retourne leurs métadonnées."""
    img_dir = output_dir / "images_raw"
    img_dir.mkdir(exist_ok=True)

    all_images = []
    xref_seen = set()

    for page_num in range(len(doc)):
        page = doc[page_num]
        for img in page.get_images(full=True):
            xref = img[0]
            if xref in xref_seen:
                continue
            xref_seen.add(xref)

            try:
                base_img = doc.extract_image(xref)
                w, h = base_img["width"], base_img["height"]
                size_kb = len(base_img["image"]) / 1024

                # Filtrer les petites images décoratives
                if w < 200 or h < 200 or size_kb < 20:
                    continue

                # Nom de fichier
                ext = base_img["ext"]
                filename = f"page{page_num+1:03d}_xref{xref}.{ext}"
                filepath = img_dir / filename

                # Sauvegarder
                with open(filepath, "wb") as f:
                    f.write(base_img["image"])

                # Identifier la section
                section_slug = _find_section_for_page(page_num + 1)

                img_meta = {
                    "filename": filename,
                    "local_path": str(filepath),
                    "book_page": page_num + 1,
                    "xref_id": xref,
                    "width_px": w,
                    "height_px": h,
                    "file_size_kb": round(size_kb, 1),
                    "format": ext,
                    "section_slug": section_slug,
                    "storage_path": f"diseases/{section_slug}/{filename}",
                    "caption_en": None,    # sera enrichi par OCR
                    "caption_fr": None,
                    "image_type": None,    # sera classifié par Claude Vision
                    "plant_part": None
                }
                all_images.append(img_meta)
                log.debug(f"  📸 Image extraite: {filename} ({w}x{h}, {size_kb:.0f}KB)")

            except Exception as e:
                log.warning(f"  ⚠️  Erreur extraction xref {xref}: {e}")

    log.info(f"✅ {len(all_images)} images extraites")
    return all_images


def _find_section_for_page(page_num: int) -> str:
    """Trouve la section correspondant à un numéro de page."""
    for slug, info in BOOK_STRUCTURE.items():
        start, end = info["pages"]
        if start <= page_num <= end:
            return slug
    return "unknown"


def classify_image_with_claude(
    client: anthropic.Anthropic,
    img_path: str,
    section_name: str
) -> dict:
    """Classifie une image et génère sa légende FR/EN via Claude Vision."""
    with open(img_path, "rb") as f:
        img_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    prompt = f"""This image is from a book about black pepper (Piper nigrum) diseases, 
from the section about "{section_name}".

Analyze this image and return a JSON object:
{{
  "image_type": "<one of: symptom, pathogen, disease_cycle, treatment, healthy, field, pest_adult, pest_larva, pest_damage>",
  "plant_part": "<one of: leaf, stem, root, berry, spike, whole_plant, soil, microscope, null>",
  "caption_en": "<descriptive caption in English, max 100 chars>",
  "caption_fr": "<descriptive caption in French, max 100 chars>",
  "tags": ["<tag1>", "<tag2>"],
  "diagnostic_value": "<high/medium/low — how useful for field diagnosis>"
}}

Return ONLY valid JSON."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": img_b64
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        text = response.content[0].text.strip().replace("```json", "").replace("```", "")
        return json.loads(text)
    except Exception as e:
        log.warning(f"  ⚠️  Classification image échouée: {e}")
        return {
            "image_type": "symptom",
            "plant_part": None,
            "caption_en": "Black pepper disease symptom",
            "caption_fr": "Symptôme de maladie du poivrier",
            "tags": [],
            "diagnostic_value": "medium"
        }


def structure_disease_data(
    client: anthropic.Anthropic,
    section_slug: str,
    section_info: dict,
    ocr_pages: list[dict]
) -> dict:
    """
    Prend les pages OCR d'une section et produit une fiche structurée 
    prête pour Supabase.
    """
    combined_text = "\n\n".join(
        p.get("raw_text", "") for p in ocr_pages if p.get("raw_text")
    )

    if not combined_text.strip():
        log.warning(f"  ⚠️  Pas de texte pour section {section_slug}")
        return {}

    prompt = f"""You are an expert agronomist. Based on the following OCR text from a book 
about black pepper diseases, extract structured data for the disease/pest: 
"{section_info.get('name_en', 'Unknown')}".

OCR TEXT:
{combined_text}

Return a JSON object with this exact structure:
{{
  "causal_organism": "<scientific name(s)>",
  "pathogen_type": "<fungus|bacterium|nematode|virus|insect|phytoplasma|mite>",
  "distribution": "<countries/regions>",
  "plant_parts_affected": "<comma-separated>",
  "plant_parts_array": ["leaf", "stem", "root", "berry", "spike"],
  "season": "<when does the disease occur>",
  "favorable_conditions": "<temperature, humidity, etc.>",
  "severity": "<critical|high|medium|low>",
  "economic_impact": "<description of losses>",
  "spread_mode": "<how the disease spreads>",
  "resistant_varieties": "<variety names if mentioned, else null>",
  "summary_en": "<2-3 sentence expert summary>",
  "symptoms": [
    {{
      "description_en": "<symptom description>",
      "plant_part": "<leaf|stem|root|berry|spike|whole_plant>",
      "disease_phase": "<early|advanced|aerial|soil>",
      "visual_cues": ["<cue1>", "<cue2>"],
      "keywords_en": ["<kw1>", "<kw2>", "<kw3>"]
    }}
  ],
  "treatments": [
    {{
      "treatment_type": "<chemical|biological|cultural|physical|integrated>",
      "title_en": "<short title>",
      "description_en": "<full description with doses>",
      "product_name": "<product name or null>",
      "active_ingredient": "<active ingredient or null>",
      "dose_rate": <number or null>,
      "dose_unit": "<g/L|g/vine|mL/L|% or null>",
      "dose_concentration": "<0.2% etc. or null>",
      "application_volume_min": <number or null>,
      "application_volume_max": <number or null>,
      "application_method": "<soil drench|foliar spray|soil broadcast|null>",
      "application_frequency": "<text description or null>",
      "pre_harvest_interval": <days or null>,
      "compatibility_notes": "<any warnings or null>"
    }}
  ]
}}

Be thorough and extract ALL treatments and ALL symptoms mentioned.
Return ONLY valid JSON."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip().replace("```json", "").replace("```", "")
        structured = json.loads(text)
        structured["slug"] = section_slug
        structured["name_en"] = section_info.get("name_en", "")
        structured["name_fr"] = section_info.get("name_fr", "")
        structured["category"] = section_info.get("type", "disease")
        structured["book_page_start"] = section_info["pages"][0]
        structured["book_page_end"] = section_info["pages"][1]
        structured["source"] = "IPC-2013"
        log.info(f"  ✅ Structure créée pour {section_slug}")
        return structured
    except Exception as e:
        log.error(f"  ❌ Structuration échouée pour {section_slug}: {e}")
        return {}


def translate_to_french(
    client: anthropic.Anthropic,
    disease_data: dict
) -> dict:
    """Traduit les champs clés en français."""
    fields_to_translate = [
        "summary_en", "season", "favorable_conditions",
        "spread_mode", "economic_impact"
    ]

    texts_en = {k: disease_data.get(k, "") for k in fields_to_translate if disease_data.get(k)}

    if not texts_en:
        return disease_data

    prompt = f"""Translate these agronomic texts about black pepper diseases from English to French.
Return a JSON object with the same keys but French values.
Be precise with scientific and agronomic terminology.

Texts to translate:
{json.dumps(texts_en, ensure_ascii=False, indent=2)}

Return ONLY valid JSON."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip().replace("```json", "").replace("```", "")
        translations = json.loads(text)

        for key, val in translations.items():
            disease_data[key.replace("_en", "_fr")] = val
            if key == "summary_en":
                disease_data["summary_fr"] = val

        # Traduire les symptômes
        for i, sym in enumerate(disease_data.get("symptoms", [])):
            if sym.get("description_en"):
                resp = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=500,
                    messages=[{"role": "user", "content":
                        f'Translate to French (agronomic): "{sym["description_en"]}". Return only the translation.'}]
                )
                disease_data["symptoms"][i]["description_fr"] = resp.content[0].text.strip()
                time.sleep(0.5)

        # Traduire les traitements
        for i, tr in enumerate(disease_data.get("treatments", [])):
            if tr.get("description_en"):
                resp = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=800,
                    messages=[{"role": "user", "content":
                        f'Translate to French (agronomic): "{tr["description_en"]}". Return only the translation.'}]
                )
                disease_data["treatments"][i]["description_fr"] = resp.content[0].text.strip()
                if tr.get("title_en"):
                    resp2 = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=100,
                        messages=[{"role": "user", "content":
                            f'Translate to French: "{tr["title_en"]}". Return only the translation.'}]
                    )
                    disease_data["treatments"][i]["title_fr"] = resp2.content[0].text.strip()
                time.sleep(0.5)

        log.info(f"  🇫🇷 Traduction FR complète pour {disease_data.get('slug', '?')}")

    except Exception as e:
        log.warning(f"  ⚠️  Traduction partielle: {e}")

    return disease_data


def run_extraction(
    pdf_path: str,
    output_dir: str,
    api_key: str,
    page_range: Optional[tuple] = None,
    skip_ocr: bool = False,
    skip_images: bool = False
):
    """Pipeline principal d'extraction."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    client = anthropic.Anthropic(api_key=api_key)
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)

    log.info(f"📖 PDF ouvert: {total_pages} pages")
    log.info(f"📁 Dossier de sortie: {output}")

    # ── ÉTAPE 1 : Extraction des images ──────────────────────
    if not skip_images:
        log.info("\n━━━ ÉTAPE 1 : Extraction des images ━━━")
        images = extract_images_from_pdf(doc, output)

        log.info(f"\n━━━ Classification des images avec Claude Vision ━━━")
        for i, img_meta in enumerate(images):
            if i % 10 == 0:
                log.info(f"  Classification image {i+1}/{len(images)}...")
            section_name = BOOK_STRUCTURE.get(
                img_meta["section_slug"], {}
            ).get("name_en", "black pepper disease")
            classification = classify_image_with_claude(
                client, img_meta["local_path"], section_name
            )
            img_meta.update(classification)
            time.sleep(1)  # Rate limiting

        # Sauvegarder métadonnées images
        img_output = output / "images_metadata.json"
        with open(img_output, "w", encoding="utf-8") as f:
            json.dump(images, f, ensure_ascii=False, indent=2)
        log.info(f"✅ Métadonnées images sauvegardées: {img_output}")
    else:
        images = []
        img_output = output / "images_metadata.json"
        if img_output.exists():
            with open(img_output) as f:
                images = json.load(f)

    # ── ÉTAPE 2 : OCR de toutes les pages ────────────────────
    if not skip_ocr:
        log.info("\n━━━ ÉTAPE 2 : OCR Claude Vision ━━━")
        ocr_results = []

        page_start = (page_range[0] - 1) if page_range else 0
        page_end   = (page_range[1] - 1) if page_range else total_pages - 1

        # Checkpoint : charger résultats déjà extraits
        checkpoint_file = output / "ocr_checkpoint.json"
        processed_pages = set()
        if checkpoint_file.exists():
            with open(checkpoint_file) as f:
                ocr_results = json.load(f)
                processed_pages = {r["page_number"] for r in ocr_results}
            log.info(f"  📌 Checkpoint: {len(processed_pages)} pages déjà traitées")

        for page_num in range(page_start, page_end + 1):
            if (page_num + 1) in processed_pages:
                log.debug(f"  ⏭️  Page {page_num+1} déjà extraite, skip")
                continue

            log.info(f"  🔍 OCR page {page_num+1}/{total_pages}...")
            result = ocr_page_with_claude(client, doc, page_num)
            if result:
                ocr_results.append(result)

            # Checkpoint toutes les 5 pages
            if len(ocr_results) % 5 == 0:
                with open(checkpoint_file, "w", encoding="utf-8") as f:
                    json.dump(ocr_results, f, ensure_ascii=False, indent=2)
                log.info(f"  💾 Checkpoint sauvegardé ({len(ocr_results)} pages)")

            time.sleep(1.5)  # Rate limiting

        # Sauvegarde finale OCR
        ocr_file = output / "ocr_all_pages.json"
        with open(ocr_file, "w", encoding="utf-8") as f:
            json.dump(ocr_results, f, ensure_ascii=False, indent=2)
        log.info(f"✅ OCR complet sauvegardé: {ocr_file}")

    else:
        ocr_file = output / "ocr_all_pages.json"
        with open(ocr_file, encoding="utf-8") as f:
            ocr_results = json.load(f)
        log.info(f"  📌 OCR chargé depuis checkpoint: {len(ocr_results)} pages")

    # ── ÉTAPE 3 : Structuration par maladie/ravageur ─────────
    log.info("\n━━━ ÉTAPE 3 : Structuration des données ━━━")
    all_diseases = []

    for slug, section_info in BOOK_STRUCTURE.items():
        if section_info["type"] not in ("disease", "pest"):
            continue

        start, end = section_info["pages"]
        # Filtrer les pages OCR de cette section
        section_pages = [
            p for p in ocr_results
            if start <= p.get("page_number", 0) <= end
        ]

        if not section_pages:
            log.warning(f"  ⚠️  Aucune page OCR pour section {slug}")
            continue

        log.info(f"  🔬 Structuration: {section_info['name_en']} ({len(section_pages)} pages)")
        disease_data = structure_disease_data(client, slug, section_info, section_pages)

        if not disease_data:
            continue

        # Associer les images
        disease_images = [
            img for img in images
            if img.get("section_slug") == slug
        ]
        disease_data["images"] = disease_images

        log.info(f"  🇫🇷 Traduction en français...")
        disease_data = translate_to_french(client, disease_data)

        all_diseases.append(disease_data)
        time.sleep(2)

    # ── ÉTAPE 4 : Export final ────────────────────────────────
    log.info("\n━━━ ÉTAPE 4 : Export final ━━━")

    # JSON complet
    final_output = output / "diseases_complete.json"
    with open(final_output, "w", encoding="utf-8") as f:
        json.dump(all_diseases, f, ensure_ascii=False, indent=2)
    log.info(f"✅ Export complet: {final_output}")
    log.info(f"   → {len(all_diseases)} maladies/ravageurs structurés")

    # Résumé
    total_symptoms  = sum(len(d.get("symptoms", [])) for d in all_diseases)
    total_treatments = sum(len(d.get("treatments", [])) for d in all_diseases)
    total_img = sum(len(d.get("images", [])) for d in all_diseases)

    summary = {
        "extraction_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pdf_path": pdf_path,
        "total_pages": total_pages,
        "diseases_extracted": len(all_diseases),
        "total_symptoms": total_symptoms,
        "total_treatments": total_treatments,
        "total_images": total_img,
        "sections": [
            {
                "slug": d["slug"],
                "name_en": d["name_en"],
                "name_fr": d["name_fr"],
                "symptoms": len(d.get("symptoms", [])),
                "treatments": len(d.get("treatments", [])),
                "images": len(d.get("images", []))
            }
            for d in all_diseases
        ]
    }

    summary_file = output / "extraction_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log.info(f"\n{'='*60}")
    log.info(f"EXTRACTION TERMINÉE")
    log.info(f"  Maladies/Ravageurs : {len(all_diseases)}")
    log.info(f"  Symptômes          : {total_symptoms}")
    log.info(f"  Traitements        : {total_treatments}")
    log.info(f"  Images             : {total_img}")
    log.info(f"{'='*60}")

    return all_diseases


def main():
    parser = argparse.ArgumentParser(
        description="Extraction OCR du livre IPC Black Pepper"
    )
    parser.add_argument("--pdf", required=True, help="Chemin vers le PDF")
    parser.add_argument("--output", default="./data", help="Dossier de sortie")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY"),
                        help="Clé API Anthropic (ou var ANTHROPIC_API_KEY)")
    parser.add_argument("--pages", help="Plage de pages ex: 19-28", default=None)
    parser.add_argument("--skip-ocr", action="store_true",
                        help="Sauter l'OCR (utiliser checkpoint existant)")
    parser.add_argument("--skip-images", action="store_true",
                        help="Sauter l'extraction des images")

    args = parser.parse_args()

    if not args.api_key:
        log.error("❌ Clé API Anthropic manquante. Utilisez --api-key ou ANTHROPIC_API_KEY")
        return

    page_range = None
    if args.pages:
        parts = args.pages.split("-")
        page_range = (int(parts[0]), int(parts[1]))

    run_extraction(
        pdf_path=args.pdf,
        output_dir=args.output,
        api_key=args.api_key,
        page_range=page_range,
        skip_ocr=args.skip_ocr,
        skip_images=args.skip_images
    )


if __name__ == "__main__":
    main()
