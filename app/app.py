# -*- coding: utf-8 -*-
"""
app.py — Interface Streamlit pour Agro-Expert Pepper
Interface web du diagnostic des maladies et ravageurs du poivrier (Piper nigrum)
Reutilise directement la classe AgroExpertPepper de agent/agent.py
(meme logique Investigation -> Diagnostic -> Prescription, meme connexion
Supabase / Claude API).

Usage:
    py -m streamlit run app/app.py
"""

import os
import sys
from datetime import date
import streamlit as st

# Permettre l'import du module agent/ situe a la racine du depot,
# meme quand Streamlit est lance depuis app/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Sur Streamlit Community Cloud, les cles API sont fournies via st.secrets
# (Settings > Secrets), pas via un fichier .env. On les recopie dans les
# variables d'environnement AVANT d'importer agent.agent, qui les lit au
# chargement du module. En local avec un .env, ce bloc ne fait rien de plus.
for _key in ("ANTHROPIC_API_KEY", "SUPABASE_URL", "SUPABASE_ANON_KEY"):
    try:
        if _key in st.secrets:
            os.environ[_key] = st.secrets[_key]
    except Exception:
        pass

from agent.agent import AgroExpertPepper

# ── DIAGNOSTIC TEMPORAIRE (a retirer une fois le probleme resolu) ─
with st.sidebar.expander("🔧 Diagnostic clés API (temporaire)"):
    _k = os.environ.get("ANTHROPIC_API_KEY", "")
    if _k:
        st.write(f"Longueur : {len(_k)} caractères")
        st.write(f"Début : `{_k[:12]}`")
        st.write(f"Fin : `{_k[-6:]}`")
        st.write(f"Espaces début/fin ? {_k != _k.strip()}")
    else:
        st.write("❌ ANTHROPIC_API_KEY est vide ou absente")

st.set_page_config(
    page_title="Agro-Expert Pepper",
    page_icon="🌿",
    layout="centered",
)

# ── Initialisation de l'agent (une seule fois par session) ────────
if "agent" not in st.session_state:
    st.session_state.agent = AgroExpertPepper(lang="fr")
    st.session_state.messages = []
    welcome = st.session_state.agent.chat(
        "Bonjour, je suis pret a vous aider. Presentez-vous."
    )
    st.session_state.messages.append({"role": "assistant", "content": welcome})

# ── Barre laterale ──────────────────────────────────────────────
with st.sidebar:
    st.title("🌿 Agro-Expert Pepper")
    st.caption("Diagnostic des maladies du poivrier — IPC Knowledge Base")

    lang_choice = st.radio("Langue / Language", ["Français", "English"], index=0)
    st.session_state.agent.lang = "fr" if lang_choice == "Français" else "en"

    st.divider()

    conseiller_nom = st.text_input(
        "👤 Nom du conseiller",
        value=st.session_state.get("conseiller_nom", ""),
        placeholder="Ex: Jean Mballa",
    )
    st.session_state.conseiller_nom = conseiller_nom

    st.divider()

    uploaded_photo = st.file_uploader(
        "📷 Photo de la plante (optionnel)",
        type=["jpg", "jpeg", "png"],
        help=(
            "L'analyse automatique d'image n'est pas encore activee : "
            "decrivez dans le message ce que vous observez sur la photo."
        ),
    )
    if uploaded_photo is not None:
        st.image(uploaded_photo, caption="Photo fournie", use_container_width=True)

    st.divider()

    if st.button("🔄 Nouveau diagnostic", use_container_width=True):
        st.session_state.agent.reset()
        st.session_state.messages = []
        welcome = st.session_state.agent.chat(
            "Bonjour, je suis pret a vous aider. Presentez-vous."
        )
        st.session_state.messages.append({"role": "assistant", "content": welcome})
        st.rerun()

    if st.button("📋 Générer le rapport WhatsApp", use_container_width=True):
        today_str = date.today().strftime("%d/%m/%Y")
        nom = st.session_state.get("conseiller_nom", "").strip()
        if st.session_state.agent.lang == "fr":
            nom_txt = nom if nom else "(non renseigne)"
            request_msg = (
                f"Genere le rapport WhatsApp du diagnostic en cours. "
                f"Utilise exactement la date du jour : {today_str} et le nom du "
                f"conseiller : {nom_txt}. N'utilise aucun placeholder du type "
                f"[Aujourd'hui] ou [Votre nom], remplace-les directement par ces "
                f"valeurs reelles."
            )
        else:
            nom_txt = nom if nom else "(not provided)"
            request_msg = (
                f"Generate the WhatsApp report for the current diagnosis. "
                f"Use exactly today's date: {today_str} and the advisor's name: "
                f"{nom_txt}. Do not use any placeholder like [Today] or [Your name], "
                f"replace them directly with these real values."
            )
        st.session_state.messages.append({"role": "user", "content": request_msg})
        reply = st.session_state.agent.chat(request_msg)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()

# ── Titre principal ───────────────────────────────────────────────
st.title("🌿 Agro-Expert Pepper")
st.caption("Diagnostic IA des maladies et ravageurs du poivrier (*Piper nigrum*)")

# ── Historique de conversation ────────────────────────────────────
for msg in st.session_state.messages:
    avatar = "🌿" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ── Zone de saisie ─────────────────────────────────────────────────
placeholder = (
    "Décrivez les symptômes observés..."
    if st.session_state.agent.lang == "fr"
    else "Describe the observed symptoms..."
)
user_input = st.chat_input(placeholder)

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🌿"):
        spinner_text = (
            "Analyse en cours..."
            if st.session_state.agent.lang == "fr"
            else "Analyzing..."
        )
        with st.spinner(spinner_text):
            reply = st.session_state.agent.chat(user_input)
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
