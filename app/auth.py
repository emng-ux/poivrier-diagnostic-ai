# -*- coding: utf-8 -*-
"""
auth.py — Authentification simple + gestion des comptes/quotas pour
Agro-Expert Pepper. Les comptes et l'usage mensuel sont stockes dans Supabase
(tables app_users / app_usage — voir supabase_auth_schema.sql).

Aucune inscription libre : les comptes sont crees uniquement par un admin
(ou via l'ecran de creation du tout premier compte admin si la table est vide).
"""

import os
import hashlib
import secrets
from datetime import date
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

_client = None


def _sb():
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _client


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000
    ).hex()


def _new_salt() -> str:
    return secrets.token_hex(16)


def has_any_user() -> bool:
    """True s'il existe deja au moins un compte (sert a savoir si on doit
    afficher l'ecran de creation du premier compte admin)."""
    resp = _sb().table("app_users").select("username").limit(1).execute()
    return bool(resp.data)


def create_user(username: str, password: str, role: str = "conseiller",
                 monthly_quota: int = 15) -> None:
    salt = _new_salt()
    pw_hash = _hash_password(password, salt)
    _sb().table("app_users").insert({
        "username": username,
        "password_hash": pw_hash,
        "password_salt": salt,
        "role": role,
        "monthly_quota": monthly_quota,
        "active": True,
    }).execute()


def verify_login(username: str, password: str):
    """Retourne le compte (dict) si les identifiants sont valides et le
    compte actif, sinon None."""
    resp = _sb().table("app_users").select("*").eq("username", username).execute()
    if not resp.data:
        return None
    user = resp.data[0]
    if not user.get("active", True):
        return None
    if _hash_password(password, user["password_salt"]) != user["password_hash"]:
        return None
    return user


def list_users() -> list:
    resp = _sb().table("app_users").select(
        "username, role, monthly_quota, active, created_at"
    ).order("created_at").execute()
    return resp.data or []


def update_quota(username: str, monthly_quota: int) -> None:
    _sb().table("app_users").update(
        {"monthly_quota": monthly_quota}
    ).eq("username", username).execute()


def set_active(username: str, active: bool) -> None:
    _sb().table("app_users").update(
        {"active": active}
    ).eq("username", username).execute()


def _current_month() -> str:
    return date.today().strftime("%Y-%m")


def get_usage(username: str) -> int:
    ym = _current_month()
    resp = _sb().table("app_usage").select("count").eq(
        "username", username
    ).eq("year_month", ym).execute()
    if resp.data:
        return resp.data[0]["count"]
    return 0


def check_quota(username: str, monthly_quota: int):
    """Retourne (autorise: bool, deja_utilise: int, quota: int).
    Un quota <= 0 signifie illimite."""
    used = get_usage(username)
    if monthly_quota is not None and monthly_quota > 0 and used >= monthly_quota:
        return False, used, monthly_quota
    return True, used, monthly_quota


def increment_usage(username: str) -> None:
    ym = _current_month()
    used = get_usage(username)
    _sb().table("app_usage").upsert({
        "username": username,
        "year_month": ym,
        "count": used + 1,
    }).execute()
