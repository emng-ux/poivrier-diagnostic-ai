# -*- coding: utf-8 -*-
"""
app.py — Interface Streamlit pour Agro-Expert Pepper
Interface web du diagnostic des maladies et ravageurs du poivrier (Piper nigrum)
Reutilise directement la classe AgroExpertPepper de agent/agent.py
(meme logique Investigation -> Diagnostic -> Prescription, meme connexion
Supabase / Claude API).
Interface entierement bilingue (FR/EN) : ecran de connexion, panneau admin,
textes fixes, et reponses de l'agent.
Acces protege par compte (auth.py) avec quota mensuel de diagnostics par
utilisateur, ajustable a tout moment par un administrateur.

Usage:
    py -m streamlit run app/app.py
"""

import os
import sys
from datetime import date
import streamlit as st

# Permettre l'import des modules agent/ et app/ situes a la racine du depot,
# meme quand Streamlit est lance depuis app/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Sur Streamlit Community Cloud, les cles API sont fournies via st.secrets
# (Settings > Secrets), pas via un fichier .env. On les recopie dans les
# variables d'environnement AVANT d'importer agent.agent / auth, qui les
# lisent au chargement du module. En local avec un .env, ce bloc ne fait
# rien de plus.
for _key in ("ANTHROPIC_API_KEY", "SUPABASE_URL", "SUPABASE_ANON_KEY"):
    try:
        if _key in st.secrets:
            os.environ[_key] = st.secrets[_key]
    except Exception:
        pass

from agent.agent import AgroExpertPepper
import auth

st.set_page_config(
    page_title="Agro-Expert Pepper",
    page_icon="🌿",
    layout="centered",
)

# ══════════════════════════════════════════════════════════════════
# Habillage visuel : palette inspiree du cycle du poivre (vigne -> grain
# sec), typographie Fraunces (titres) + Work Sans (interface), bandeau
# d'en-tete distinctif, boutons et bulles de chat retravailles.
# ══════════════════════════════════════════════════════════════════
GREEN = "#1B4332"
GREEN_DARK = "#12281F"
CREAM = "#FAF8F3"
SAND = "#EDE6D6"
INK = "#211F1B"
CHILI = "#A83A1D"
GOLD = "#C9A227"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Work+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: 'Work Sans', sans-serif;
}}
h1, h2, h3 {{
    font-family: 'Fraunces', serif !important;
    color: {GREEN} !important;
    font-weight: 600 !important;
}}

/* Bandeau d'en-tete */
.pepper-hero {{
    background: linear-gradient(135deg, {GREEN} 0%, {GREEN_DARK} 100%);
    border-radius: 10px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.5rem;
    color: {CREAM};
}}
.pepper-hero h1 {{
    font-family: 'Fraunces', serif !important;
    color: {CREAM} !important;
    font-size: 2rem !important;
    margin: 0 0 0.25rem 0 !important;
    font-weight: 600 !important;
}}
.pepper-hero p {{
    font-family: 'Work Sans', sans-serif;
    color: {SAND} !important;
    margin: 0;
    font-size: 0.95rem;
    opacity: 0.9;
}}

/* Boutons */
.stButton > button {{
    background-color: {GREEN};
    color: {CREAM};
    border: none;
    border-radius: 6px;
    font-family: 'Work Sans', sans-serif;
    font-weight: 500;
}}
.stButton > button:hover {{
    background-color: {GREEN_DARK};
    color: {CREAM};
}}

/* Barre laterale */
[data-testid="stSidebar"] {{
    background-color: {SAND};
}}

/* Bulles de chat : accent vert cote agent */
[data-testid="stChatMessageAvatarAssistant"] {{
    background-color: {GREEN} !important;
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {{
    border-left: 3px solid {GREEN};
    border-radius: 4px;
    padding-left: 0.75rem;
}}

/* Messages d'erreur / succes gardent leur sens (rouge = alerte, pas decoratif) */
div[data-testid="stAlertContentError"] {{
    color: {CHILI};
}}
</style>
""", unsafe_allow_html=True)


def render_hero(title: str, tagline: str):
    st.markdown(
        f'<div class="pepper-hero"><h1>🌿 {title}</h1><p>{tagline}</p></div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════
# Textes bilingues (interface fixe + ecran de connexion + panneau admin)
# ══════════════════════════════════════════════════════════════════
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
        "quota_exceeded": (
            "🚫 Vous avez atteint votre quota de {quota} diagnostics pour ce "
            "mois-ci ({used}/{quota} utilisés). Le quota se réinitialise le "
            "mois prochain. Contactez un administrateur si vous en avez "
            "besoin de plus."
        ),
        "quota_remaining": "Diagnostics ce mois-ci : {used}/{quota}",
        "quota_unlimited": "Diagnostics ce mois-ci : {used} (illimité)",
        "logout_button": "🚪 Se déconnecter",
        # Ecran de connexion
        "login_caption": "Connexion requise",
        "bootstrap_info": (
            "Aucun compte n'existe encore. Créez le premier compte "
            "administrateur pour commencer."
        ),
        "field_username": "Identifiant",
        "field_password": "Mot de passe",
        "bootstrap_submit": "Créer le compte admin",
        "bootstrap_missing": "Identifiant et mot de passe requis.",
        "bootstrap_success": "Compte admin créé. Connectez-vous ci-dessous.",
        "login_submit": "Se connecter",
        "login_error": "Identifiant ou mot de passe incorrect, ou compte désactivé.",
        "db_error": "Erreur de connexion à la base de comptes : {err}",
        # Panneau admin
        "admin_title": "🛠️ Administration",
        "admin_create_heading": "**Créer un compte**",
        "admin_role_label": "Rôle",
        "admin_quota_label": "Quota mensuel (0 = illimité)",
        "admin_create_button": "Créer",
        "admin_create_success": "Compte '{username}' créé.",
        "admin_create_error": "Erreur : {err}",
        "admin_existing_heading": "**Comptes existants**",
        "admin_account_line": "`{username}` — {role} — quota {quota} — {status}",
        "admin_status_active": "actif",
        "admin_status_inactive": "désactivé",
        "admin_deactivate": "Désactiver",
        "admin_reactivate": "Réactiver",
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
        "quota_exceeded": (
            "🚫 You've reached your quota of {quota} diagnoses for this "
            "month ({used}/{quota} used). The quota resets next month. "
            "Contact an administrator if you need more."
        ),
        "quota_remaining": "Diagnoses this month: {used}/{quota}",
        "quota_unlimited": "Diagnoses this month: {used} (unlimited)",
        "logout_button": "🚪 Log out",
        # Login screen
        "login_caption": "Login required",
        "bootstrap_info": (
            "No account exists yet. Create the first administrator "
            "account to get started."
        ),
        "field_username": "Username",
        "field_password": "Password",
        "bootstrap_submit": "Create admin account",
        "bootstrap_missing": "Username and password are required.",
        "bootstrap_success": "Admin account created. Log in below.",
        "login_submit": "Log in",
        "login_error": "Incorrect username or password, or account disabled.",
        "db_error": "Error connecting to the account database: {err}",
        # Admin panel
        "admin_title": "🛠️ Administration",
        "admin_create_heading": "**Create an account**",
        "admin_role_label": "Role",
        "admin_quota_label": "Monthly quota (0 = unlimited)",
        "admin_create_button": "Create",
        "admin_create_success": "Account '{username}' created.",
        "admin_create_error": "Error: {err}",
        "admin_existing_heading": "**Existing accounts**",
        "admin_account_line": "`{username}` — {role} — quota {quota} — {status}",
        "admin_status_active": "active",
        "admin_status_inactive": "disabled",
        "admin_deactivate": "Disable",
        "admin_reactivate": "Re-enable",
    },
}


def _lang_from_choice(choice: str) -> str:
    return "fr" if choice == "Français" else "en"


# ══════════════════════════════════════════════════════════════════
# AUTHENTIFICATION (ecran obligatoire avant tout usage de l'agent)
# ══════════════════════════════════════════════════════════════════
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if st.session_state.auth_user is None:
    # Selecteur de langue disponible des l'ecran de connexion (avant que le
    # widget principal "lang_radio" n'existe), stocke dans une cle dediee.
    login_lang_choice = st.radio(
        "Langue / Language", ["Français", "English"],
        key="login_lang_radio", horizontal=True,
    )
    LT = UI_TEXT[_lang_from_choice(login_lang_choice)]

    render_hero("Agro-Expert Pepper", LT["login_caption"])

    try:
        bootstrap_needed = not auth.has_any_user()
    except Exception as e:
        st.error(LT["db_error"].format(err=e))
        st.stop()

    if bootstrap_needed:
        st.info(LT["bootstrap_info"])
        with st.form("bootstrap_admin_form"):
            new_username = st.text_input(LT["field_username"])
            new_password = st.text_input(LT["field_password"], type="password")
            submitted = st.form_submit_button(LT["bootstrap_submit"])
        if submitted:
            if not new_username or not new_password:
                st.error(LT["bootstrap_missing"])
            else:
                auth.create_user(
                    new_username, new_password, role="admin", monthly_quota=0
                )
                st.success(LT["bootstrap_success"])
                st.rerun()
    else:
        with st.form("login_form"):
            username = st.text_input(LT["field_username"])
            password = st.text_input(LT["field_password"], type="password")
            submitted = st.form_submit_button(LT["login_submit"])
        if submitted:
            user = auth.verify_login(username, password)
            if user is None:
                st.error(LT["login_error"])
            else:
                st.session_state.auth_user = user
                # La langue choisie sur l'ecran de connexion devient la
                # langue par defaut de l'app une fois connecte.
                st.session_state["lang_radio"] = login_lang_choice
                st.rerun()

    st.stop()

# À partir d'ici, l'utilisateur est authentifié.
CURRENT_USER = st.session_state.auth_user["username"]
CURRENT_ROLE = st.session_state.auth_user.get("role", "conseiller")
CURRENT_QUOTA = st.session_state.auth_user.get("monthly_quota", 15)

# La cle du widget radio persiste dans st.session_state entre les reruns :
# on peut donc lire la langue choisie AVANT de redessiner le widget lui-meme,
# ce qui permet de traduire immediatement tout le texte fixe (y compris ce
# qui est affiche au-dessus du selecteur).
_lang_choice_prev = st.session_state.get("lang_radio", "Français")
CUR_LANG = _lang_from_choice(_lang_choice_prev)
T = UI_TEXT[CUR_LANG]


def _quota_allows(username: str, quota: int) -> bool:
    """Verifie le quota ; affiche un message et retourne False si depasse."""
    allowed, used, q = auth.check_quota(username, quota)
    if not allowed:
        st.error(T["quota_exceeded"].format(used=used, quota=q))
        return False
    return True


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
    st.markdown("### 🌿 Agro-Expert Pepper")
    st.caption(T["sidebar_caption"])

    lang_choice = st.radio(
        T["lang_label"], ["Français", "English"], key="lang_radio"
    )
    st.session_state.agent.lang = "fr" if lang_choice == "Français" else "en"

    if st.session_state.get("conversation_lang") != st.session_state.agent.lang:
        st.info(T["lang_switch_hint"])

    st.divider()

    st.caption(f"👤 {CURRENT_USER} ({CURRENT_ROLE})")
    _used_now = auth.get_usage(CURRENT_USER)
    if CURRENT_QUOTA and CURRENT_QUOTA > 0:
        st.caption(T["quota_remaining"].format(used=_used_now, quota=CURRENT_QUOTA))
    else:
        st.caption(T["quota_unlimited"].format(used=_used_now))
    if st.button(T["logout_button"], use_container_width=True):
        st.session_state.auth_user = None
        st.rerun()

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
        if _quota_allows(CURRENT_USER, CURRENT_QUOTA):
            today_str = date.today().strftime("%d/%m/%Y")
            nom = st.session_state.get("conseiller_nom", "").strip()
            cur_t = UI_TEXT[st.session_state.agent.lang]
            nom_txt = nom if nom else cur_t["advisor_not_provided"]
            request_msg = cur_t["whatsapp_request"].format(date=today_str, nom=nom_txt)

            st.session_state.messages.append({"role": "user", "content": request_msg})
            reply = st.session_state.agent.chat(request_msg, auto_detect_lang=False)
            auth.increment_usage(CURRENT_USER)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.rerun()

    # ── Panneau d'administration (uniquement pour role == admin) ──────
    if CURRENT_ROLE == "admin":
        st.divider()
        with st.expander(T["admin_title"]):
            st.markdown(T["admin_create_heading"])
            with st.form("create_user_form"):
                nu_username = st.text_input(T["field_username"], key="nu_username")
                nu_password = st.text_input(T["field_password"], type="password", key="nu_password")
                nu_role = st.selectbox(T["admin_role_label"], ["conseiller", "admin"], key="nu_role")
                nu_quota = st.number_input(
                    T["admin_quota_label"], min_value=0, value=15, key="nu_quota"
                )
                nu_submitted = st.form_submit_button(T["admin_create_button"])
            if nu_submitted:
                if not nu_username or not nu_password:
                    st.error(T["bootstrap_missing"])
                else:
                    try:
                        auth.create_user(nu_username, nu_password, nu_role, nu_quota)
                        st.success(T["admin_create_success"].format(username=nu_username))
                        st.rerun()
                    except Exception as e:
                        st.error(T["admin_create_error"].format(err=e))

            st.markdown(T["admin_existing_heading"])
            for u in auth.list_users():
                with st.container():
                    status = T["admin_status_active"] if u["active"] else T["admin_status_inactive"]
                    st.write(T["admin_account_line"].format(
                        username=u["username"], role=u["role"],
                        quota=u["monthly_quota"] or "∞", status=status,
                    ))
                    col1, col2 = st.columns(2)
                    with col1:
                        new_q = st.number_input(
                            T["admin_quota_label"], min_value=0,
                            value=u["monthly_quota"] or 0,
                            key=f"quota_{u['username']}",
                            label_visibility="collapsed",
                        )
                        if new_q != (u["monthly_quota"] or 0):
                            auth.update_quota(u["username"], new_q)
                            st.rerun()
                    with col2:
                        label = T["admin_deactivate"] if u["active"] else T["admin_reactivate"]
                        if st.button(label, key=f"toggle_{u['username']}"):
                            auth.set_active(u["username"], not u["active"])
                            st.rerun()

# ── Bandeau principal ───────────────────────────────────────────────
render_hero("Agro-Expert Pepper", T["main_caption"])

# ── Historique de conversation ────────────────────────────────────
for msg in st.session_state.messages:
    avatar = "🌿" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ── Zone de saisie ─────────────────────────────────────────────────
user_input = st.chat_input(T["chat_placeholder"])

if user_input:
    if not _quota_allows(CURRENT_USER, CURRENT_QUOTA):
        st.stop()

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

    auth.increment_usage(CURRENT_USER)
    st.session_state.messages.append({"role": "assistant", "content": reply})
