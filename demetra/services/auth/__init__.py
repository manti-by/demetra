from demetra.library.exceptions import AuthError
from demetra.services.auth.allowlist import is_email_allowed, is_github_login_allowed
from demetra.services.auth.jwt import create_jwt_token, verify_jwt_token
from demetra.services.auth.oauth import exchange_code_for_token, get_github_auth_url, get_github_user
from demetra.services.auth.passwords import hash_password, verify_password
from demetra.services.auth.sessions import (
    authenticate_user,
    get_current_user,
    get_current_user_dep,
    get_or_create_user,
    has_permission,
    login_with_password,
    logout,
    reset_password,
    reset_password_cli,
    signup_with_password,
)
from demetra.services.auth.waitlist import (
    approve_waitlist_entry,
    find_pending_waitlist_entry,
    join_waitlist,
    mark_waitlist_joined,
    mark_waitlist_joined_by_value,
    remove_waitlist_entry,
    waitlist_cli,
)
from demetra.services.auth.waitlist import (
    list_entries as list_waitlist_entries,
)
from demetra.services.persistence.database import (
    create_user,
    delete_jwt_token,
    get_jwt_token,
    get_transaction,
    get_user_by_email,
    get_user_by_github_id,
    get_user_by_id,
    get_user_jwt_tokens,
    init_db,
    save_jwt_token,
    update_user_password,
)
from demetra.settings import GITHUB, JWT


__all__ = [
    "GITHUB",
    "JWT",
    "AuthError",
    "approve_waitlist_entry",
    "authenticate_user",
    "create_jwt_token",
    "create_user",
    "delete_jwt_token",
    "exchange_code_for_token",
    "find_pending_waitlist_entry",
    "get_current_user",
    "get_current_user_dep",
    "get_github_auth_url",
    "get_github_user",
    "get_jwt_token",
    "get_or_create_user",
    "get_transaction",
    "get_user_by_email",
    "get_user_by_github_id",
    "get_user_by_id",
    "get_user_jwt_tokens",
    "has_permission",
    "hash_password",
    "init_db",
    "is_email_allowed",
    "is_github_login_allowed",
    "join_waitlist",
    "list_waitlist_entries",
    "login_with_password",
    "logout",
    "mark_waitlist_joined",
    "mark_waitlist_joined_by_value",
    "remove_waitlist_entry",
    "reset_password",
    "reset_password_cli",
    "save_jwt_token",
    "signup_with_password",
    "update_user_password",
    "verify_jwt_token",
    "verify_password",
    "waitlist_cli",
]
