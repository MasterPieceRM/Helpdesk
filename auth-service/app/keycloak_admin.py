"""
Keycloak Admin API integration for user registration.
"""
import os
import requests
from typing import Optional, Tuple

KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "helpdesk")
KEYCLOAK_ADMIN_USER = os.getenv("KEYCLOAK_ADMIN", "admin")
KEYCLOAK_ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")

# Default role to assign to new users
DEFAULT_USER_ROLE = os.getenv("DEFAULT_USER_ROLE", "client")


def get_admin_token() -> Tuple[Optional[str], Optional[str]]:
    """
    Get an admin access token from Keycloak master realm.
    Returns (token, error_message).
    """
    token_url = f"{KEYCLOAK_BASE_URL}/realms/master/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": KEYCLOAK_ADMIN_USER,
        "password": KEYCLOAK_ADMIN_PASSWORD,
    }

    try:
        resp = requests.post(token_url, data=data, timeout=10)
        if resp.status_code != 200:
            print(
                f"[KEYCLOAK] Failed to get admin token: {resp.status_code} {resp.text}")
            return None, f"Failed to get admin token: {resp.status_code}"
        return resp.json().get("access_token"), None
    except Exception as e:
        print(f"[KEYCLOAK] Error connecting to Keycloak: {str(e)}")
        return None, f"Error connecting to Keycloak: {str(e)}"


def check_realm_exists(admin_token: str) -> Tuple[bool, Optional[str]]:
    """
    Check if the target realm exists.
    """
    realm_url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_REALM}"
    headers = {"Authorization": f"Bearer {admin_token}"}

    try:
        resp = requests.get(realm_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return True, None
        elif resp.status_code == 404:
            return False, f"Realm '{KEYCLOAK_REALM}' does not exist. Please create it in Keycloak admin console."
        else:
            return False, f"Error checking realm: {resp.status_code}"
    except Exception as e:
        return False, f"Error checking realm: {str(e)}"


def get_role_id(admin_token: str, role_name: str) -> Optional[str]:
    """
    Get the role ID for a given realm role name.
    """
    roles_url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_REALM}/roles/{role_name}"
    headers = {"Authorization": f"Bearer {admin_token}"}

    try:
        resp = requests.get(roles_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("id")
        return None
    except Exception:
        return None


def assign_role_to_user(admin_token: str, user_id: str, role_name: str) -> Tuple[bool, Optional[str]]:
    """
    Assign a realm role to a user.
    """
    # First, get the role details
    role_url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_REALM}/roles/{role_name}"
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }

    try:
        role_resp = requests.get(role_url, headers=headers, timeout=10)
        if role_resp.status_code != 200:
            return False, f"Role '{role_name}' not found"

        role_data = role_resp.json()

        # Assign role to user
        assign_url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_REALM}/users/{user_id}/role-mappings/realm"
        assign_resp = requests.post(assign_url, headers=headers, json=[
                                    role_data], timeout=10)

        if assign_resp.status_code in (200, 204):
            return True, None
        return False, f"Failed to assign role: {assign_resp.status_code}"
    except Exception as e:
        return False, f"Error assigning role: {str(e)}"


def create_user(
    username: str,
    email: str,
    password: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    role: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Create a new user in Keycloak with the specified role (or default 'client' role).
    Returns (success, message).
    """
    # Get admin token
    admin_token, error = get_admin_token()
    if error:
        return False, error

    # Check if realm exists first
    realm_exists, realm_error = check_realm_exists(admin_token)
    if not realm_exists:
        return False, realm_error

    normalized_first_name = (first_name or username).strip()
    normalized_last_name = (last_name or "User").strip()

    # Create user payload
    user_payload = {
        "username": username,
        "email": email,
        "enabled": True,
        "emailVerified": True,
        "firstName": normalized_first_name,
        "lastName": normalized_last_name,
        "credentials": [
            {
                "type": "password",
                "value": password,
                "temporary": False,
            }
        ],
    }

    users_url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_REALM}/users"
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }

    try:
        print(
            f"[KEYCLOAK] Creating user '{username}' in realm '{KEYCLOAK_REALM}'")
        resp = requests.post(users_url, headers=headers,
                             json=user_payload, timeout=10)

        if resp.status_code == 201:
            # User created successfully, get user ID from Location header
            location = resp.headers.get("Location", "")
            user_id = location.split("/")[-1] if location else None
            print(
                f"[KEYCLOAK] User '{username}' created successfully with ID: {user_id}")

            if user_id:
                # Clear any required actions to ensure account is fully set up
                user_update_url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_REALM}/users/{user_id}"
                update_payload = {
                    "requiredActions": [],
                    "emailVerified": True,
                    "enabled": True
                }
                update_resp = requests.put(
                    user_update_url, headers=headers, json=update_payload, timeout=10)
                if update_resp.status_code not in (200, 204):
                    print(
                        f"[KEYCLOAK] Warning: Could not clear required actions: {update_resp.status_code}")
                else:
                    print(
                        f"[KEYCLOAK] Cleared required actions for user '{username}'")

                # Assign the specified role or default role
                role_to_assign = role or DEFAULT_USER_ROLE
                if role_to_assign:
                    role_success, role_error = assign_role_to_user(
                        admin_token, user_id, role_to_assign)
                    if not role_success:
                        print(
                            f"[KEYCLOAK] Warning: User created but role assignment failed: {role_error}")
                    else:
                        print(
                            f"[KEYCLOAK] Assigned role '{role_to_assign}' to user '{username}'")

            return True, "User created successfully"
        elif resp.status_code == 409:
            return False, "User with this username or email already exists"
        elif resp.status_code == 404:
            return False, f"Realm '{KEYCLOAK_REALM}' not found. Please create it in Keycloak admin console first."
        else:
            print(
                f"[KEYCLOAK] Failed to create user: {resp.status_code} {resp.text}")
            return False, f"Failed to create user: {resp.status_code}"
    except Exception as e:
        print(f"[KEYCLOAK] Error creating user: {str(e)}")
        return False, f"Error creating user: {str(e)}"
