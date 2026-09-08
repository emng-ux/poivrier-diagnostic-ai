-- =============================================================
-- AGRO-EXPERT PEPPER — Schéma Supabase complet
-- Base de données : maladies et ravageurs du poivrier
-- Source : IPC "Diseases and Insect Pests of Black Pepper"
-- Version : 1.0 | Auteur : projet poivrier-diagnostic-ai
-- =============================================================

-- Extension pour la recherche vectorielle (RAG)
CREATE EXTENSION IF NOT EXISTS vector;

-- Extension pour les UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================
-- TABLE 1 : CATÉGORIES (maladies / ravageurs)
-- =============================================================
CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(20) UNIQUE NOT NULL,  -- ex: 'disease', 'pest'
    name_fr     VARCHAR(100) NOT NULL,
    name_en     VARCHAR(100) NOT NULL
);

INSERT INTO categories (code, name_fr, name_en) VALUES
    ('disease',      'Maladie',           'Disease'),
    ('pest',         'Ravageur',          'Pest'),
    ('nutritional',  'Trouble nutritionnel', 'Nutritional disorder');

-- =============================================================
-- TABLE 2 : MALADIES ET RAVAGEURS (entité principale)
-- =============================================================
CREATE TABLE diseases (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id         INTEGER REFERENCES categories(id) NOT NULL,

    -- Identifiants
    slug                VARCHAR(100) UNIQUE NOT NULL,  -- ex: 'phytophthora-rots'
    book_page_start     INTEGER,   -- page de début dans le livre IPC
    book_page_end       INTEGER,   -- page de fin dans le livre IPC

    -- Noms bilingues
    name_fr             VARCHAR(200) NOT NULL,
    name_en             VARCHAR(200) NOT NULL,
    local_names         JSONB,     -- {"cm_bamileke": "...", "cm_beti": "..."}

    -- Organisme causal
    causal_organism     VARCHAR(300),       -- nom scientifique
    causal_organism_fr  VARCHAR(300),       -- traduction/description fr
    pathogen_type       VARCHAR(50),        -- 'fungus','bacterium','nematode','virus','insect','phytoplasma'

    -- Distribution géographique
    distribution        TEXT,               -- pays/régions affectés
    distribution_africa TEXT,               -- spécifique Afrique/Cameroun

    -- Parties de la plante affectées
    plant_parts_affected  VARCHAR(300),     -- 'feuilles, tiges, racines'
    plant_parts_array     TEXT[],           -- ['leaf','stem','root','berry','spike']

    -- Saison / conditions favorables
    season              TEXT,
    favorable_conditions TEXT,              -- humidité, température, etc.

    -- Résumé bilingue (pour affichage rapide)
    summary_fr          TEXT,
    summary_en          TEXT,

    -- Texte complet extrait du livre (OCR)
    full_text_fr        TEXT,               -- traduit en français
    full_text_en        TEXT,               -- texte original anglais

    -- Niveau de gravité économique
    severity            VARCHAR(20) CHECK (severity IN ('critical','high','medium','low')),
    economic_impact     TEXT,

    -- Vecteur d'embedding pour RAG (recherche sémantique)
    embedding           vector(1536),       -- OpenAI text-embedding-3-small

    -- Mode de propagation
    spread_mode         TEXT,

    -- Variétés résistantes
    resistant_varieties TEXT,

    -- Métadonnées
    is_major            BOOLEAN DEFAULT true,
    is_verified         BOOLEAN DEFAULT false,
    source              VARCHAR(100) DEFAULT 'IPC-2013',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour recherche vectorielle
CREATE INDEX diseases_embedding_idx
    ON diseases USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Index texte pour recherche rapide
CREATE INDEX diseases_name_fr_idx ON diseases USING gin(to_tsvector('french', name_fr));
CREATE INDEX diseases_name_en_idx ON diseases USING gin(to_tsvector('english', name_en));

-- =============================================================
-- TABLE 3 : SYMPTÔMES (détaillés, liés à une maladie)
-- =============================================================
CREATE TABLE symptoms (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    disease_id      UUID REFERENCES diseases(id) ON DELETE CASCADE,

    -- Description bilingue
    description_fr  TEXT NOT NULL,
    description_en  TEXT NOT NULL,

    -- Localisation sur la plante
    plant_part      VARCHAR(50),   -- 'leaf','stem','root','berry','spike','whole_plant'
    plant_part_fr   VARCHAR(50),

    -- Phase de développement
    disease_phase   VARCHAR(50),   -- 'early','advanced','aerial','soil'
    disease_phase_fr VARCHAR(50),

    -- Caractéristiques visuelles clés (pour diagnostic visuel)
    visual_cues     TEXT[],        -- ['black spots','fimbriate margins','foul odor']
    visual_cues_fr  TEXT[],        -- ['taches noires','marges fimbriées','odeur fétide']

    -- Mots-clés pour matching symptômes
    keywords_fr     TEXT[],
    keywords_en     TEXT[],

    -- Vecteur embedding pour ce symptôme
    embedding       vector(1536),

    -- Ordre d'apparition (1 = premier symptôme visible)
    display_order   INTEGER DEFAULT 1,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX symptoms_disease_idx ON symptoms(disease_id);
CREATE INDEX symptoms_plant_part_idx ON symptoms(plant_part);
CREATE INDEX symptoms_embedding_idx
    ON symptoms USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

-- =============================================================
-- TABLE 4 : TRAITEMENTS
-- =============================================================
CREATE TABLE treatments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    disease_id      UUID REFERENCES diseases(id) ON DELETE CASCADE,

    -- Type de traitement
    treatment_type  VARCHAR(30) CHECK (treatment_type IN
                        ('chemical','biological','cultural','physical','integrated')),
    treatment_type_fr VARCHAR(30),

    -- Description bilingue
    title_fr        VARCHAR(200),
    title_en        VARCHAR(200),
    description_fr  TEXT NOT NULL,
    description_en  TEXT NOT NULL,

    -- Produit(s) actif(s)
    product_name    VARCHAR(200),           -- nom commercial ou générique
    active_ingredient VARCHAR(200),         -- matière active
    product_family  VARCHAR(100),           -- fongicide, insecticide, nématicide...

    -- Doses (format structuré pour le calculateur)
    dose_rate       NUMERIC(10,4),          -- ex: 2.0
    dose_unit       VARCHAR(20),            -- 'g/L', 'g/vine', 'mL/L', '%'
    dose_concentration VARCHAR(20),         -- '0.2%', '1%', etc.
    application_volume_min NUMERIC(8,2),    -- litres/pied minimum
    application_volume_max NUMERIC(8,2),    -- litres/pied maximum
    application_volume_unit VARCHAR(20) DEFAULT 'L/vine',

    -- Mode et fréquence d'application
    application_method VARCHAR(100),        -- 'soil drench','foliar spray','soil broadcast'
    application_method_fr VARCHAR(100),
    application_frequency TEXT,             -- '2-3 fois, intervalles 2-3 mois'
    application_timing    TEXT,             -- 'début saison des pluies'

    -- Sécurité
    pre_harvest_interval INTEGER,           -- jours avant récolte
    safety_notes        TEXT,               -- notes de sécurité
    compatibility_notes TEXT,               -- ex: incompatible avec biocontrôle

    -- Source (page du livre)
    source_page     INTEGER,
    is_recommended  BOOLEAN DEFAULT true,
    display_order   INTEGER DEFAULT 1,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX treatments_disease_idx ON treatments(disease_id);
CREATE INDEX treatments_type_idx ON treatments(treatment_type);

-- =============================================================
-- TABLE 5 : IMAGES
-- =============================================================
CREATE TABLE images (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    disease_id      UUID REFERENCES diseases(id) ON DELETE CASCADE,

    -- Stockage Supabase
    storage_path    VARCHAR(500) NOT NULL,  -- chemin dans Supabase Storage
    public_url      VARCHAR(1000),          -- URL publique CDN
    thumbnail_url   VARCHAR(1000),          -- miniature 300px

    -- Métadonnées
    filename        VARCHAR(200) NOT NULL,
    file_size_kb    INTEGER,
    width_px        INTEGER,
    height_px       INTEGER,
    format          VARCHAR(10) DEFAULT 'jpeg',

    -- Description bilingue
    caption_fr      TEXT,
    caption_en      TEXT,

    -- Classification
    image_type      VARCHAR(50) CHECK (image_type IN (
                        'symptom',           -- symptôme sur plante
                        'pathogen',          -- organisme pathogène (microscope)
                        'disease_cycle',     -- cycle de la maladie
                        'treatment',         -- application traitement
                        'healthy',           -- plante saine (référence)
                        'field',             -- vue plantation
                        'pest_adult',        -- ravageur adulte
                        'pest_larva',        -- larve
                        'pest_damage'        -- dégâts
                    )),

    -- Partie de la plante visible
    plant_part      VARCHAR(50),
    plant_part_fr   VARCHAR(50),

    -- Page source dans le livre
    book_page       INTEGER,
    xref_id         INTEGER,    -- xref PyMuPDF pour traçabilité

    -- Embedding visuel (pour recherche par image)
    visual_embedding vector(1536),

    -- Tags pour filtrage
    tags            TEXT[],

    display_order   INTEGER DEFAULT 1,
    is_primary      BOOLEAN DEFAULT false,  -- image principale de la fiche
    is_verified     BOOLEAN DEFAULT false,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX images_disease_idx ON images(disease_id);
CREATE INDEX images_type_idx ON images(image_type);
CREATE INDEX images_primary_idx ON images(disease_id, is_primary);

-- =============================================================
-- TABLE 6 : QUESTIONS DE DIFFÉRENCIATION (diagnostic différentiel)
-- =============================================================
CREATE TABLE differential_questions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    disease_id_1    UUID REFERENCES diseases(id),   -- maladie A
    disease_id_2    UUID REFERENCES diseases(id),   -- maladie B à différencier

    -- Question posée à l'utilisateur
    question_fr     TEXT NOT NULL,
    question_en     TEXT NOT NULL,

    -- Réponses et leur interprétation
    answer_yes_points_to UUID REFERENCES diseases(id),  -- si OUI → cette maladie
    answer_no_points_to  UUID REFERENCES diseases(id),  -- si NON → cette maladie

    explanation_fr  TEXT,
    explanation_en  TEXT,

    display_order   INTEGER DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================
-- TABLE 7 : SESSIONS DE DIAGNOSTIC (logs pour amélioration)
-- =============================================================
CREATE TABLE diagnostic_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Contexte
    session_lang    VARCHAR(5) DEFAULT 'fr',
    user_type       VARCHAR(50),    -- 'farmer','advisor','researcher'
    country         VARCHAR(100),
    region          VARCHAR(100),

    -- Symptômes décrits
    symptoms_described    TEXT,
    plant_parts_reported  TEXT[],
    has_photo             BOOLEAN DEFAULT false,
    has_video             BOOLEAN DEFAULT false,

    -- Résultat du diagnostic
    diagnosed_disease_id  UUID REFERENCES diseases(id),
    confidence_score      NUMERIC(4,2),   -- 0.00 à 1.00
    diagnosis_confirmed   BOOLEAN,        -- confirmé par l'utilisateur

    -- Traitement recommandé suivi?
    treatment_followed    BOOLEAN,
    feedback              TEXT,

    -- Métadonnées
    mode                VARCHAR(20) DEFAULT 'online',  -- 'online','edge'
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================
-- TABLE 8 : PRODUITS PHYTOSANITAIRES (référentiel doses)
-- =============================================================
CREATE TABLE products (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    name            VARCHAR(200) UNIQUE NOT NULL,
    name_fr         VARCHAR(200),
    active_ingredient VARCHAR(200),
    product_family  VARCHAR(100),   -- fongicide, nématicide, insecticide

    -- Dose standard
    standard_dose_rate  NUMERIC(10,4),
    standard_dose_unit  VARCHAR(20),
    standard_concentration VARCHAR(20),

    -- Disponibilité
    available_africa    BOOLEAN DEFAULT NULL,
    commercial_names    TEXT[],     -- noms commerciaux courants

    -- Sécurité
    who_class           VARCHAR(20), -- classification OMS
    pre_harvest_days    INTEGER,

    notes_fr            TEXT,
    notes_en            TEXT,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================
-- TABLE 9 : GLOSSAIRE BILINGUE
-- =============================================================
CREATE TABLE glossary (
    id          SERIAL PRIMARY KEY,
    term_en     VARCHAR(200) UNIQUE NOT NULL,
    term_fr     VARCHAR(200) NOT NULL,
    definition_en TEXT,
    definition_fr TEXT,
    category    VARCHAR(50),   -- 'pathology','treatment','agronomy'
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================
-- FONCTIONS UTILITAIRES
-- =============================================================

-- Fonction : recherche sémantique par symptômes (RAG)
CREATE OR REPLACE FUNCTION search_by_symptoms(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.70,
    match_count     INT   DEFAULT 5,
    lang            TEXT  DEFAULT 'fr'
)
RETURNS TABLE (
    id              UUID,
    name_fr         VARCHAR,
    name_en         VARCHAR,
    similarity      FLOAT,
    summary_fr      TEXT,
    summary_en      TEXT,
    severity        VARCHAR,
    causal_organism VARCHAR
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.name_fr,
        d.name_en,
        1 - (d.embedding <=> query_embedding) AS similarity,
        d.summary_fr,
        d.summary_en,
        d.severity,
        d.causal_organism
    FROM diseases d
    WHERE 1 - (d.embedding <=> query_embedding) > match_threshold
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Fonction : recherche sémantique dans les symptômes
CREATE OR REPLACE FUNCTION search_symptoms_semantic(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.65,
    match_count     INT   DEFAULT 10
)
RETURNS TABLE (
    symptom_id      UUID,
    disease_id      UUID,
    disease_name_fr VARCHAR,
    disease_name_en VARCHAR,
    description_fr  TEXT,
    description_en  TEXT,
    similarity      FLOAT,
    plant_part      VARCHAR
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id,
        s.disease_id,
        d.name_fr,
        d.name_en,
        s.description_fr,
        s.description_en,
        1 - (s.embedding <=> query_embedding) AS similarity,
        s.plant_part
    FROM symptoms s
    JOIN diseases d ON d.id = s.disease_id
    WHERE 1 - (s.embedding <=> query_embedding) > match_threshold
    ORDER BY s.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Fonction : calculateur de dose
CREATE OR REPLACE FUNCTION calculate_dose(
    product_id      UUID,
    sprayer_volume  NUMERIC   -- litres
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    p               products%ROWTYPE;
    total_product   NUMERIC;
    result          JSONB;
BEGIN
    SELECT * INTO p FROM products WHERE id = product_id;
    total_product := p.standard_dose_rate * sprayer_volume;
    result := jsonb_build_object(
        'product_name',      p.name,
        'sprayer_volume_L',  sprayer_volume,
        'dose_rate',         p.standard_dose_rate,
        'dose_unit',         p.standard_dose_unit,
        'total_product',     ROUND(total_product, 1),
        'concentration',     p.standard_concentration,
        'pre_harvest_days',  p.pre_harvest_days
    );
    RETURN result;
END;
$$;

-- Trigger : mise à jour auto du champ updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER diseases_updated_at
    BEFORE UPDATE ON diseases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================
-- ROW LEVEL SECURITY (RLS)
-- =============================================================
ALTER TABLE diseases          ENABLE ROW LEVEL SECURITY;
ALTER TABLE symptoms          ENABLE ROW LEVEL SECURITY;
ALTER TABLE treatments        ENABLE ROW LEVEL SECURITY;
ALTER TABLE images            ENABLE ROW LEVEL SECURITY;
ALTER TABLE diagnostic_sessions ENABLE ROW LEVEL SECURITY;

-- Lecture publique pour maladies, symptômes, traitements, images
CREATE POLICY "Public read diseases"
    ON diseases FOR SELECT USING (true);

CREATE POLICY "Public read symptoms"
    ON symptoms FOR SELECT USING (true);

CREATE POLICY "Public read treatments"
    ON treatments FOR SELECT USING (true);

CREATE POLICY "Public read images"
    ON images FOR SELECT USING (true);

-- Écriture seulement via service role (backend)
CREATE POLICY "Service role write diseases"
    ON diseases FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role write symptoms"
    ON symptoms FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role write treatments"
    ON treatments FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role write images"
    ON images FOR ALL
    USING (auth.role() = 'service_role');

-- Sessions : insert public, lecture service_role seulement
CREATE POLICY "Public insert sessions"
    ON diagnostic_sessions FOR INSERT WITH CHECK (true);

CREATE POLICY "Service read sessions"
    ON diagnostic_sessions FOR SELECT
    USING (auth.role() = 'service_role');

-- =============================================================
-- STORAGE BUCKET (à créer dans Supabase Dashboard ou via API)
-- =============================================================
-- Bucket : pepper-diseases
-- Structure des dossiers :
--   /diseases/{slug}/              → photos par maladie
--   /diseases/{slug}/thumbnails/   → miniatures
--   /pests/{slug}/                 → photos ravageurs
--   /reference/                    → images de référence générales

-- =============================================================
-- VUES UTILES
-- =============================================================

-- Vue : fiche complète d'une maladie
CREATE VIEW disease_full AS
SELECT
    d.*,
    c.name_fr AS category_fr,
    c.name_en AS category_en,
    (SELECT COUNT(*) FROM symptoms s WHERE s.disease_id = d.id) AS symptom_count,
    (SELECT COUNT(*) FROM treatments t WHERE t.disease_id = d.id) AS treatment_count,
    (SELECT COUNT(*) FROM images i WHERE i.disease_id = d.id) AS image_count,
    (SELECT public_url FROM images i WHERE i.disease_id = d.id AND i.is_primary = true LIMIT 1) AS primary_image_url
FROM diseases d
JOIN categories c ON c.id = d.category_id;

-- Vue : résumé pour liste/recherche
CREATE VIEW disease_summary AS
SELECT
    d.id,
    d.slug,
    d.name_fr,
    d.name_en,
    d.causal_organism,
    d.severity,
    d.plant_parts_affected,
    c.name_fr AS category_fr,
    (SELECT public_url FROM images i WHERE i.disease_id = d.id AND i.is_primary = true LIMIT 1) AS thumbnail
FROM diseases d
JOIN categories c ON c.id = d.category_id
ORDER BY d.severity DESC, d.name_fr;

-- =============================================================
-- COMMENTAIRES DE DOCUMENTATION
-- =============================================================
COMMENT ON TABLE diseases IS 'Maladies et ravageurs du poivrier (Piper nigrum) — source IPC 2013';
COMMENT ON TABLE symptoms IS 'Symptômes détaillés par maladie, avec embeddings pour recherche RAG';
COMMENT ON TABLE treatments IS 'Traitements chimiques, biologiques et culturaux avec doses exactes';
COMMENT ON TABLE images IS 'Photos extraites du livre IPC stockées dans Supabase Storage';
COMMENT ON TABLE diagnostic_sessions IS 'Logs des sessions de diagnostic pour amélioration continue';
COMMENT ON FUNCTION search_by_symptoms IS 'Recherche sémantique RAG par description de symptômes';
COMMENT ON FUNCTION calculate_dose IS 'Calculateur de dose produit en fonction du volume du pulvérisateur';
