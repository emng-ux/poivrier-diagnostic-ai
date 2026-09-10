# -*- coding: utf-8 -*-
"""
agent.py — Agro-Expert Pepper
Agent IA agentique bilingue FR/EN de diagnostic des maladies du poivrier
Source de verite : base Supabase IPC + Claude API

Usage:
    py agent/agent.py  (mode console interactif)
"""

import os
import sys
import json
import anthropic
from supabase import create_client

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Configuration ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SUPABASE_URL      = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
MODEL             = "claude-haiku-4-5"  # Rapide et economique
MAX_TOKENS        = 1500

# ── System Prompt bilingue ─────────────────────────────────────
SYSTEM_PROMPT_FR = """Tu es Agro-Expert Pepper, un agent IA specialise dans le diagnostic des maladies et ravageurs du poivrier (Piper nigrum L.).

Ta source de verite unique : le guide officiel IPC "Diseases and Insect Pests of Black Pepper" (Sarma et al., 2013), dont les donnees sont stockees dans ta base de donnees.

WORKFLOW OBLIGATOIRE en 3 phases :

PHASE 1 - INVESTIGATION (🔍) :
- Accueille le conseiller et demande les symptomes observes
- Pose des questions ciblees sur : partie de la plante affectee, aspect visuel, odeur, rapidite d'apparition, saison
- Si deux maladies sont possibles, pose UNE question de differenciation precise

PHASE 2 - DIAGNOSTIC (🧠) :
- Identifie la maladie/ravageur avec niveau de confiance (ELEVE/MOYEN/FAIBLE)
- Cite les symptomes caracteristiques du livre IPC
- Si confiance FAIBLE, indique quelle observation supplementaire confirmerait le diagnostic

PHASE 3 - PRESCRIPTION (💊) :
- Traitement chimique avec doses EXACTES (ex: Oxychlorure de cuivre 0,2% = 2g/L)
- Alternatives biologiques
- Mesures culturales
- Si l'utilisateur donne le volume de son pulverisateur, calcule la dose totale

REGLES :
- Reponds toujours en francais (sauf si l'utilisateur ecrit en anglais)
- Ne jamais inventer des informations hors de la base IPC
- Etre concis et pratique pour le terrain
- Generer un rapport WhatsApp si demande
"""

SYSTEM_PROMPT_EN = """You are Agro-Expert Pepper, an AI agent specialized in diagnosing diseases and pests of black pepper (Piper nigrum L.).

Your single source of truth: the official IPC guide "Diseases and Insect Pests of Black Pepper" (Sarma et al., 2013), stored in your database.

MANDATORY WORKFLOW in 3 phases:

PHASE 1 - INVESTIGATION (🔍):
- Welcome the advisor and ask for observed symptoms
- Ask targeted questions about: plant part affected, visual appearance, smell, speed of onset, season
- If two diseases are possible, ask ONE precise differentiating question

PHASE 2 - DIAGNOSIS (🧠):
- Identify the disease/pest with confidence level (HIGH/MODERATE/LOW)
- Cite characteristic symptoms from the IPC book
- If confidence is LOW, indicate what additional observation would confirm diagnosis

PHASE 3 - PRESCRIPTION (💊):
- Chemical treatment with EXACT doses (e.g., Copper oxychloride 0.2% = 2g/L)
- Biological alternatives
- Cultural measures
- If user gives sprayer volume, calculate total dose

RULES:
- Always respond in English (unless user writes in French)
- Never invent information outside IPC database
- Be concise and practical for field use
- Generate WhatsApp report if requested
"""


class AgroExpertPepper:
    """Agent de diagnostic des maladies du poivrier."""

    def __init__(self, lang: str = "fr"):
        self.lang = lang
        self.conversation_history = []
        self.current_diagnosis = None

        # Clients API
        self.claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        try:
            self.supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            self.db_available = True
        except Exception:
            self.supabase = None
            self.db_available = False

        # Charger la base de connaissances depuis Supabase
        self.knowledge_base = self._load_knowledge_base()

    def _load_knowledge_base(self) -> str:
        """Charge les donnees depuis Supabase pour enrichir le contexte."""
        if not self.db_available:
            return ""

        try:
            resp = self.supabase.table("diseases").select(
                "slug, name_fr, name_en, causal_organism, plant_parts_affected, severity, summary_fr, summary_en"
            ).execute()

            diseases = resp.data
            if not diseases:
                return ""

            lines = ["=== BASE DE CONNAISSANCES IPC (Supabase) ==="]
            for d in diseases:
                name = d.get("name_fr") if self.lang == "fr" else d.get("name_en")
                summary = d.get("summary_fr") if self.lang == "fr" else d.get("summary_en")
                lines.append(f"\n• {name} ({d.get('causal_organism', 'N/A')})")
                lines.append(f"  Parties: {d.get('plant_parts_affected', '')}")
                lines.append(f"  Severite: {d.get('severity', '')}")
                if summary:
                    lines.append(f"  Resume: {summary[:200]}...")

            return "\n".join(lines)
        except Exception as e:
            return f"[DB non disponible: {e}]"

    def search_disease(self, query: str) -> list:
        """Recherche une maladie dans Supabase par mots-cles."""
        if not self.db_available:
            return []
        try:
            resp = self.supabase.table("diseases").select(
                "*, symptoms(*), treatments(*)"
            ).execute()
            return resp.data or []
        except Exception:
            return []

    def get_disease_details(self, slug: str) -> dict:
        """Recupere les details complets d'une maladie."""
        if not self.db_available:
            return {}
        try:
            resp = self.supabase.table("diseases").select(
                "*, symptoms(*), treatments(*)"
            ).eq("slug", slug).execute()
            return resp.data[0] if resp.data else {}
        except Exception:
            return {}

    def calculate_dose(self, dose_rate: float, dose_unit: str,
                       sprayer_volume: float, product: str) -> str:
        """Calcule la dose pour un volume de pulverisateur donne."""
        if dose_unit in ("g/L", "mL/L"):
            total = round(dose_rate * sprayer_volume, 1)
            unit_label = "g" if dose_unit == "g/L" else "mL"
            if self.lang == "fr":
                return (f"Pour votre pulverisateur de {sprayer_volume}L :\n"
                        f"Melangez {total}{unit_label} de {product} dans {sprayer_volume}L d'eau")
            else:
                return (f"For your {sprayer_volume}L sprayer:\n"
                        f"Mix {total}{unit_label} of {product} in {sprayer_volume}L of water")
        return ""

    def generate_whatsapp_report(self, disease_name: str, symptoms: str,
                                  treatment: str, urgency: str) -> str:
        """Genere un compte-rendu terrain format WhatsApp."""
        from datetime import date
        today = date.today().strftime("%d/%m/%Y")

        if self.lang == "fr":
            return f"""📋 COMPTE-RENDU VISITE TERRAIN
━━━━━━━━━━━━━━━━━━━━
Date: {today}
Culture: Poivrier (Piper nigrum)
Outil: Agro-Expert Pepper

🔍 SYMPTOMES OBSERVES:
{symptoms}

🧠 DIAGNOSTIC:
{disease_name}

💊 TRAITEMENT RECOMMANDE:
{treatment}

⚠️ URGENCE: {urgency}
━━━━━━━━━━━━━━━━━━━━
Source: IPC - Diseases & Pests of Black Pepper"""
        else:
            return f"""📋 FIELD VISIT REPORT
━━━━━━━━━━━━━━━━━━━━
Date: {today}
Crop: Black Pepper (Piper nigrum)
Tool: Agro-Expert Pepper

🔍 OBSERVED SYMPTOMS:
{symptoms}

🧠 DIAGNOSIS:
{disease_name}

💊 RECOMMENDED TREATMENT:
{treatment}

⚠️ URGENCY: {urgency}
━━━━━━━━━━━━━━━━━━━━
Source: IPC - Diseases & Pests of Black Pepper"""

    def get_system_prompt(self) -> str:
        """Construit le system prompt avec la base de connaissances."""
        base = SYSTEM_PROMPT_FR if self.lang == "fr" else SYSTEM_PROMPT_EN
        if self.knowledge_base:
            base += f"\n\n{self.knowledge_base}"
        return base

    def chat(self, user_message: str) -> str:
        """Envoie un message et retourne la reponse de l'agent."""
        # Detection de langue automatique
        if any(w in user_message.lower() for w in
               ["bonjour", "symptome", "maladie", "feuille", "tige",
                "racine", "traitement", "dose", "pulverisateur"]):
            self.lang = "fr"
        elif any(w in user_message.lower() for w in
                 ["hello", "symptom", "disease", "leaf", "stem",
                  "root", "treatment", "dose", "sprayer"]):
            self.lang = "en"

        # Ajouter le message utilisateur a l'historique
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        try:
            response = self.claude.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self.get_system_prompt(),
                messages=self.conversation_history
            )
            reply = response.content[0].text

            # Ajouter la reponse a l'historique
            self.conversation_history.append({
                "role": "assistant",
                "content": reply
            })

            return reply

        except Exception as e:
            error_msg = (
                f"Erreur de connexion a l'API: {e}"
                if self.lang == "fr"
                else f"API connection error: {e}"
            )
            return error_msg

    def reset(self):
        """Remet l'agent a zero pour un nouveau diagnostic."""
        self.conversation_history = []
        self.current_diagnosis = None


def run_console():
    """Mode console interactif."""
    print("=" * 55)
    print("  AGRO-EXPERT PEPPER — Agent IA de Diagnostic")
    print("  Poivrier (Piper nigrum) | IPC Knowledge Base")
    print("=" * 55)
    print("Tapez 'quitter' pour arreter | 'reset' pour recommencer")
    print("Type 'quit' to stop | 'reset' to restart")
    print("-" * 55)

    agent = AgroExpertPepper(lang="fr")

    # Message de bienvenue
    welcome = agent.chat(
        "Bonjour, je suis pret a vous aider. Presentez-vous."
    )
    print(f"\n🌿 Agent: {welcome}\n")

    while True:
        try:
            user_input = input("👤 Vous: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAu revoir!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quitter", "quit", "exit"):
            print("Au revoir! / Goodbye!")
            break

        if user_input.lower() == "reset":
            agent.reset()
            print("\n🌿 Agent: Nouveau diagnostic demarre.\n")
            continue

        response = agent.chat(user_input)
        print(f"\n🌿 Agent: {response}\n")


if __name__ == "__main__":
    run_console()
