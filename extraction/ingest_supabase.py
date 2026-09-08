"""
==============================================================
AGRO-EXPERT PEPPER — Ingestion des données dans Supabase
==============================================================
Lit le fichier diseases_complete.json produit par extract_pdf.py
et insère tout dans Supabase :
  - Table diseases
  - Table symptoms
  - Table treatments
  - Table images (métadonnées)
  - Upload des images vers Supabase Storage
  - Génération des embeddings vectoriels

Usage :
    python ingest_supabase.py --data ./data/diseases_complete.json
    python ingest_supabase.py --data ./data/diseases_complete.json --dry-run
"""

import os
import json
import time
import argparse
import logging
from pathlib import Path

import anthropic
from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI via Anthropic embedding
STORAGE_BUCKET  = "pepper-diseases"


def get_embedding(client_openai, text: str) -> list[float]:
    """Génère un embedding vectoriel via OpenAI (1536 dimensions)."""
    try:
        # Note: on utilise openai directement pour les embeddings
        import openai
        response = openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text[:8000]  # limite de tokens
        )
        return response.data[0].embedding
    except Exception as e:
        log.warning(f"  ⚠️  Embedding échoué: {e}")
        return [0.0] * 1536


def upload_image_to_storage(
    supabase: Client,
    local_path: str,
    storage_path: str
) -> str | None:
    """Upload une image vers Supabase Storage et retourne l'URL publique."""
    try:
        with open(local_path, "rb") as f:
            img_bytes = f.read()

        supabase.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=img_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )
        # URL publique
        url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)
        return url
    except Exception as e:
        log.warning(f"  ⚠️  Upload image échoué ({storage_path}): {e}")
        return None


def upsert_disease(supabase: Client, disease: dict, embedding: list) -> str | None:
    """Insère ou met à jour une maladie dans Supabase. Retourne l'UUID."""
    # Correspondance categorie
    category_map = {"disease": 1, "pest": 2, "nutritional": 3}
    category_id = category_map.get(disease.get("category", "disease"), 1)

    record = {
        "slug":                   disease.get("slug"),
        "category_id":            category_id,
        "name_fr":                disease.get("name_fr", ""),
        "name_en":                disease.get("name_en", ""),
        "causal_organism":        disease.get("causal_organism"),
        "causal_organism_fr":     disease.get("causal_organism_fr"),
        "pathogen_type":          disease.get("pathogen_type"),
        "distribution":           disease.get("distribution"),
        "plant_parts_affected":   disease.get("plant_parts_affected"),
        "plant_parts_array":      disease.get("plant_parts_array", []),
        "season":                 disease.get("season"),
        "favorable_conditions":   disease.get("favorable_conditions"),
        "summary_fr":             disease.get("summary_fr") or disease.get("summary_en"),
        "summary_en":             disease.get("summary_en"),
        "severity":               disease.get("severity", "medium"),
        "economic_impact":        disease.get("economic_impact"),
        "spread_mode":            disease.get("spread_mode"),
        "resistant_varieties":    disease.get("resistant_varieties"),
        "book_page_start":        disease.get("book_page_start"),
        "book_page_end":          disease.get("book_page_end"),
        "source":                 disease.get("source", "IPC-2013"),
        "is_major":               True,
        "embedding":              embedding
    }

    try:
        resp = supabase.table("diseases").upsert(
            record, on_conflict="slug"
        ).execute()
        disease_id = resp.data[0]["id"]
        log.info(f"  ✅ Disease upserted: {disease['slug']} → {disease_id}")
        return disease_id
    except Exception as e:
        log.error(f"  ❌ Upsert disease échoué ({disease.get('slug')}): {e}")
        return None


def insert_symptoms(
    supabase: Client,
    disease_id: str,
    symptoms: list,
    embed_fn
):
    """Insère tous les symptômes d'une maladie."""
    if not symptoms:
        return

    # Supprimer les anciens symptômes
    supabase.table("symptoms").delete().eq("disease_id", disease_id).execute()

    for i, sym in enumerate(symptoms):
        text_for_embedding = f"{sym.get('description_en', '')} {' '.join(sym.get('keywords_en', []))}"
        embedding = embed_fn(text_for_embedding)

        record = {
            "disease_id":      disease_id,
            "description_fr":  sym.get("description_fr") or sym.get("description_en", ""),
            "description_en":  sym.get("description_en", ""),
            "plant_part":      sym.get("plant_part"),
            "plant_part_fr":   sym.get("plant_part_fr"),
            "disease_phase":   sym.get("disease_phase"),
            "visual_cues":     sym.get("visual_cues", []),
            "visual_cues_fr":  sym.get("visual_cues_fr", []),
            "keywords_fr":     sym.get("keywords_fr", []),
            "keywords_en":     sym.get("keywords_en", []),
            "display_order":   i + 1,
            "embedding":       embedding
        }
        try:
            supabase.table("symptoms").insert(record).execute()
        except Exception as e:
            log.warning(f"    ⚠️  Symptôme {i+1} échoué: {e}")
        time.sleep(0.3)

    log.info(f"    ✅ {len(symptoms)} symptômes insérés")


def insert_treatments(supabase: Client, disease_id: str, treatments: list):
    """Insère tous les traitements d'une maladie."""
    if not treatments:
        return

    supabase.table("treatments").delete().eq("disease_id", disease_id).execute()

    type_map_fr = {
        "chemical":    "Chimique",
        "biological":  "Biologique",
        "cultural":    "Cultural",
        "physical":    "Physique",
        "integrated":  "Intégré"
    }
    method_map_fr = {
        "soil drench":    "Trempage du sol",
        "foliar spray":   "Pulvérisation foliaire",
        "soil broadcast": "Épandage au sol"
    }

    for i, tr in enumerate(treatments):
        record = {
            "disease_id":            disease_id,
            "treatment_type":        tr.get("treatment_type", "cultural"),
            "treatment_type_fr":     type_map_fr.get(tr.get("treatment_type", ""), ""),
            "title_fr":              tr.get("title_fr") or tr.get("title_en", ""),
            "title_en":              tr.get("title_en", ""),
            "description_fr":        tr.get("description_fr") or tr.get("description_en", ""),
            "description_en":        tr.get("description_en", ""),
            "product_name":          tr.get("product_name"),
            "active_ingredient":     tr.get("active_ingredient"),
            "dose_rate":             tr.get("dose_rate"),
            "dose_unit":             tr.get("dose_unit"),
            "dose_concentration":    tr.get("dose_concentration"),
            "application_volume_min": tr.get("application_volume_min"),
            "application_volume_max": tr.get("application_volume_max"),
            "application_method":    tr.get("application_method"),
            "application_method_fr": method_map_fr.get(
                tr.get("application_method", ""), ""
            ),
            "application_frequency": tr.get("application_frequency"),
            "application_timing":    tr.get("application_timing"),
            "pre_harvest_interval":  tr.get("pre_harvest_interval"),
            "safety_notes":          tr.get("safety_notes"),
            "compatibility_notes":   tr.get("compatibility_notes"),
            "display_order":         i + 1,
            "is_recommended":        True
        }
        try:
            supabase.table("treatments").insert(record).execute()
        except Exception as e:
            log.warning(f"    ⚠️  Traitement {i+1} échoué: {e}")

    log.info(f"    ✅ {len(treatments)} traitements insérés")


def insert_images(
    supabase: Client,
    disease_id: str,
    images: list,
    upload_files: bool = True
):
    """Insère les métadonnées des images et upload les fichiers."""
    if not images:
        return

    supabase.table("images").delete().eq("disease_id", disease_id).execute()

    for i, img in enumerate(images):
        public_url = None
        if upload_files and img.get("local_path") and os.path.exists(img["local_path"]):
            public_url = upload_image_to_storage(
                supabase,
                img["local_path"],
                img.get("storage_path", f"diseases/{img['filename']}")
            )
            time.sleep(0.5)

        record = {
            "disease_id":    disease_id,
            "storage_path":  img.get("storage_path", ""),
            "public_url":    public_url or img.get("public_url"),
            "filename":      img.get("filename", ""),
            "file_size_kb":  img.get("file_size_kb"),
            "width_px":      img.get("width_px"),
            "height_px":     img.get("height_px"),
            "format":        img.get("format", "jpeg"),
            "caption_fr":    img.get("caption_fr"),
            "caption_en":    img.get("caption_en"),
            "image_type":    img.get("image_type", "symptom"),
            "plant_part":    img.get("plant_part"),
            "book_page":     img.get("book_page"),
            "xref_id":       img.get("xref_id"),
            "tags":          img.get("tags", []),
            "display_order": i + 1,
            "is_primary":    i == 0  # Première image = image principale
        }
        try:
            supabase.table("images").insert(record).execute()
        except Exception as e:
            log.warning(f"    ⚠️  Image {img.get('filename')} échouée: {e}")

    log.info(f"    ✅ {len(images)} images insérées")


def run_ingestion(
    data_file: str,
    supabase_url: str,
    supabase_key: str,
    openai_key: str,
    dry_run: bool = False,
    upload_images: bool = True
):
    """Pipeline principal d'ingestion."""
    log.info(f"📂 Chargement des données: {data_file}")
    with open(data_file, encoding="utf-8") as f:
        diseases = json.load(f)

    log.info(f"   → {len(diseases)} maladies/ravageurs à ingérer")

    if dry_run:
        log.info("🧪 MODE DRY-RUN — Aucune donnée envoyée à Supabase")
        for d in diseases:
            log.info(f"  Would insert: {d.get('slug')} — {d.get('name_en')}")
            log.info(f"    Symptoms: {len(d.get('symptoms', []))}")
            log.info(f"    Treatments: {len(d.get('treatments', []))}")
            log.info(f"    Images: {len(d.get('images', []))}")
        return

    supabase: Client = create_client(supabase_url, supabase_key)

    import openai
    openai.api_key = openai_key
    embed_fn = lambda text: get_embedding(None, text)

    stats = {"diseases": 0, "symptoms": 0, "treatments": 0, "images": 0, "errors": 0}

    for disease in diseases:
        log.info(f"\n🔬 Ingestion: {disease.get('name_en')} ({disease.get('slug')})")

        # Embedding pour la maladie
        embed_text = f"{disease.get('name_en', '')} {disease.get('summary_en', '')} {disease.get('plant_parts_affected', '')}"
        embedding = embed_fn(embed_text)
        time.sleep(0.5)

        # Insert disease
        disease_id = upsert_disease(supabase, disease, embedding)
        if not disease_id:
            stats["errors"] += 1
            continue
        stats["diseases"] += 1

        # Insert symptoms
        symptoms = disease.get("symptoms", [])
        insert_symptoms(supabase, disease_id, symptoms, embed_fn)
        stats["symptoms"] += len(symptoms)
        time.sleep(1)

        # Insert treatments
        treatments = disease.get("treatments", [])
        insert_treatments(supabase, disease_id, treatments)
        stats["treatments"] += len(treatments)
        time.sleep(0.5)

        # Insert images
        images = disease.get("images", [])
        insert_images(supabase, disease_id, images, upload_files=upload_images)
        stats["images"] += len(images)
        time.sleep(1)

    log.info(f"\n{'='*60}")
    log.info(f"INGESTION TERMINÉE")
    log.info(f"  ✅ Maladies  : {stats['diseases']}")
    log.info(f"  ✅ Symptômes : {stats['symptoms']}")
    log.info(f"  ✅ Traitements: {stats['treatments']}")
    log.info(f"  ✅ Images    : {stats['images']}")
    log.info(f"  ❌ Erreurs   : {stats['errors']}")
    log.info(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Ingestion données dans Supabase")
    parser.add_argument("--data", required=True, help="Fichier diseases_complete.json")
    parser.add_argument("--supabase-url", default=os.environ.get("SUPABASE_URL"))
    parser.add_argument("--supabase-key", default=os.environ.get("SUPABASE_SERVICE_KEY"))
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--dry-run", action="store_true", help="Simulation sans écriture")
    parser.add_argument("--no-image-upload", action="store_true", help="Pas d'upload images")

    args = parser.parse_args()

    if not args.dry_run:
        for var, val in [("SUPABASE_URL", args.supabase_url),
                         ("SUPABASE_SERVICE_KEY", args.supabase_key),
                         ("OPENAI_API_KEY", args.openai_key)]:
            if not val:
                log.error(f"❌ Variable manquante: {var}")
                return

    run_ingestion(
        data_file=args.data,
        supabase_url=args.supabase_url or "",
        supabase_key=args.supabase_key or "",
        openai_key=args.openai_key or "",
        dry_run=args.dry_run,
        upload_images=not args.no_image_upload
    )


if __name__ == "__main__":
    main()
