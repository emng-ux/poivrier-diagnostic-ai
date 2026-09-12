# -*- coding: utf-8 -*-
"""
app.py — Interface Streamlit pour Agro-Expert Pepper
Interface web du diagnostic des maladies et ravageurs du poivrier (Piper nigrum)
Reutilise directement la classe AgroExpertPepper de agent/agent.py
(meme logique Investigation -> Diagnostic -> Prescription, meme connexion
Supabase / Claude API).
Interface entierement bilingue (FR/EN) : textes fixes + reponses de l'agent.

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

st.set_page_config(
    page_title="Agro-Expert Pepper",
    page_icon="🌿",
    layout="centered",
)

# ── Textes bilingues de l'interface fixe ────────────────────────────
UI_TEXT = {
    "fr": {
        "sidebar_caption": "Diagnostic des maladies du poivrier — IPC Knowledge Base",
        "lang_label": "Langue / Language",
        "advisor_label": "👤 Nom du conseiller",
        "advisor_placeholder": "Ex: Jean Mballa",
        "photo_label": "📷 Photo de la plante (optionnel)",
        "photo_help": (
            "La photo sera analysée automatiquement par l'IA avec votre "
            "prochain message décrivant la situation."
        ),
        "photo_caption": "Photo fournie",
        "photo_pending": "📎 Cette photo sera envoyée avec votre prochain message.",
        "reset_button": "🔄 Nouveau diagnostic",
        "whatsapp_button": "📋 Générer le rapport WhatsApp",
        "main_caption": "Diagnostic IA des maladies et ravageurs du poivrier (*Piper nigrum*)",
        "chat_placeholder": "Décrivez les symptômes observés...",
        "spinner": "Analyse en cours...",
        "whatsapp_request": (
            "Genere le rapport WhatsApp du diagnostic en cours. "
            "Utilise exactement la date du jour : {date} et le nom du "
            "conseiller : {nom}. N'utilise aucun placeholder du type "
            "[Aujourd'hui] ou [Votre nom], remplace-les directement par ces "
            "valeurs reelles."
        ),
        "advisor_not_provided": "(non renseigne)",
        "welcome_prompt": "Bonjour, je suis pret a vous aider. Presentez-vous.",
        "lang_switch_hint": (
            "💡 Cette conversation a commencé dans une autre langue. Cliquez "
            "sur « Nouveau diagnostic » ci-dessous pour la recommencer "
            "entièrement en français."
        ),
    },
    "en": {
        "sidebar_caption": "Black pepper disease diagnosis — IPC Knowledge Base",
        "lang_label": "Langue / Language",
        "advisor_label": "👤 Advisor name",
        "advisor_placeholder": "e.g. John Doe",
        "photo_label": "📷 Plant photo (optional)",
        "photo_help": (
            "The photo will be automatically analyzed by the AI with your "
            "next message describing the situation."
        ),
        "photo_caption": "Photo provided",
        "photo_pending": "📎 This photo will be sent with your next message.",
        "reset_button": "🔄 New diagnosis",
        "whatsapp_button": "📋 Generate WhatsApp report",
        "main_caption": "AI diagnosis of black pepper (*Piper nigrum*) diseases and pests",
        "chat_placeholder": "Describe the observed symptoms...",
        "spinner": "Analyzing...",
        "whatsapp_request": (
            "Generate the WhatsApp report for the current diagnosis. "
            "Use exactly today's date: {date} and the advisor's name: "
            "{nom}. Do not use any placeholder like [Today] or [Your name], "
            "replace them directly with these real values."
        ),
        "advisor_not_provided": "(not provided)",
        "welcome_prompt": "Hello, I am ready to help you. Please introduce yourself.",
        "lang_switch_hint": (
            "💡 This conversation started in another language. Click "
            "\"New diagnosis\" below to restart it fully in English."
        ),
    },
}

# La cle du widget radio persiste dans st.session_state entre les reruns :
# on peut donc lire la langue choisie AVANT de redessiner le widget lui-meme,
# ce qui permet de traduire immediatement tout le texte fixe (y compris ce
# qui est affiche au-dessus du selecteur).
_lang_choice_prev = st.session_state.get("lang_radio", "Français")
CUR_LANG = "fr" if _lang_choice_prev == "Français" else "en"
T = UI_TEXT[CUR_LANG]

# ── Initialisation de l'agent (une seule fois par session) ────────
if "agent" not in st.session_state:
    st.session_state.agent = AgroExpertPepper(lang=CUR_LANG)
    st.session_state.messages = []
    st.session_state.conversation_lang = CUR_LANG
    welcome = st.session_state.agent.chat(
        UI_TEXT[CUR_LANG]["welcome_prompt"], auto_detect_lang=False
    )
    st.session_state.messages.append({"role": "assistant", "content": welcome})

# ── Barre laterale ──────────────────────────────────────────────
with st.sidebar:
    st.title("🌿 Agro-Expert Pepper")
    st.caption(T["sidebar_caption"])

    lang_choice = st.radio(
        T["lang_label"], ["Français", "English"], key="lang_radio"
    )
    st.session_state.agent.lang = "fr" if lang_choice == "Français" else "en"

    if st.session_state.get("conversation_lang") != st.session_state.agent.lang:
        st.info(T["lang_switch_hint"])

    st.divider()

    conseiller_nom = st.text_input(
        T["advisor_label"],
        value=st.session_state.get("conseiller_nom", ""),
        placeholder=T["advisor_placeholder"],
    )
    st.session_state.conseiller_nom = conseiller_nom

    st.divider()

    uploaded_photo = st.file_uploader(
        T["photo_label"],
        type=["jpg", "jpeg", "png"],
        help=T["photo_help"],
    )
    if uploaded_photo is not None:
        st.image(uploaded_photo, caption=T["photo_caption"], use_container_width=True)
        st.caption(T["photo_pending"])

    st.divider()

    if st.button(T["reset_button"], use_container_width=True):
        st.session_state.agent.reset()
        st.session_state.messages = []
        st.session_state.photo_analyzed_signature = None
        st.session_state.conversation_lang = st.session_state.agent.lang
        welcome = st.session_state.agent.chat(
            UI_TEXT[st.session_state.agent.lang]["welcome_prompt"],
            auto_detect_lang=False,
        )
        st.session_state.messages.append({"role": "assistant", "content": welcome})
        st.rerun()

    if st.button(T["whatsapp_button"], use_container_width=True):
        today_str = date.today().strftime("%d/%m/%Y")
        nom = st.session_state.get("conseiller_nom", "").strip()
        cur_t = UI_TEXT[st.session_state.agent.lang]
        nom_txt = nom if nom else cur_t["advisor_not_provided"]
        request_msg = cur_t["whatsapp_request"].format(date=today_str, nom=nom_txt)

        st.session_state.messages.append({"role": "user", "content": request_msg})
        reply = st.session_state.agent.chat(request_msg, auto_detect_lang=False)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()

# ── Titre principal ───────────────────────────────────────────────
st.title("🌿 Agro-Expert Pepper")
st.caption(T["main_caption"])

# ── Historique de conversation ────────────────────────────────────
for msg in st.session_state.messages:
    avatar = "🌿" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ── Zone de saisie ─────────────────────────────────────────────────
user_input = st.chat_input(T["chat_placeholder"])

if user_input:
    # Si une photo a ete uploadee et n'a pas encore ete envoyee, on la joint
    # a ce message (une seule fois par photo, pas a chaque message suivant).
    photo_bytes = None
    photo_media_type = None
    if uploaded_photo is not None:
        signature = f"{uploaded_photo.name}-{uploaded_photo.size}"
        if st.session_state.get("photo_analyzed_signature") != signature:
            photo_bytes = uploaded_photo.getvalue()
            photo_media_type = uploaded_photo.type or "image/jpeg"
            st.session_state.photo_analyzed_signature = signature

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        if photo_bytes:
            st.image(photo_bytes, width=250)
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🌿"):
        with st.spinner(T["spinner"]):
            reply = st.session_state.agent.chat(
                user_input,
                image_bytes=photo_bytes,
                image_media_type=photo_media_type,
                auto_detect_lang=False,
            )
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
