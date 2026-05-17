import os
import requests
import streamlit as st

# ---------------------------
# Config
# ---------------------------

AUTH_URL = os.getenv("AUTH_URL", "http://kong:8000/auth")
API_URL = os.getenv("API_URL", "http://kong:8000")

KEYCLOAK_BASE_URL = "http://keycloak:8080"
KEYCLOAK_REALM = "helpdesk"
KEYCLOAK_CLIENT_ID = "helpdesk-frontend"

TOKEN_URL = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"


# ---------------------------
# Helpers
# ---------------------------

def login_with_keycloak(username: str, password: str):
    """
    Use Keycloak Direct Access Grants (Resource Owner Password Credentials)
    to obtain an access token for the given user.
    """
    data = {
        "grant_type": "password",
        "client_id": KEYCLOAK_CLIENT_ID,
        "username": username,
        "password": password,
    }

    resp = requests.post(TOKEN_URL, data=data)
    if resp.status_code != 200:
        return None, f"Login failed: {resp.status_code} {resp.text}"

    tokens = resp.json()
    return tokens, None


def get_auth_headers():
    token = st.session_state.get("access_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


# ---------------------------
# App layout and login gate
# ---------------------------

st.set_page_config(page_title="Helpdesk Distributed", layout="wide")

# Login gate: if we have no token in session, show only login form
if "access_token" not in st.session_state:
    st.title("Helpdesk Login")

    login_tab, register_tab = st.tabs(["Login", "Create Account"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

        if submitted:
            tokens, error = login_with_keycloak(username, password)
            if error:
                st.error(error)
            else:
                st.session_state["access_token"] = tokens["access_token"]
                st.session_state["refresh_token"] = tokens.get("refresh_token")

                # Ask backend who we are
                me_resp = requests.get(
                    f"{AUTH_URL}/me", headers=get_auth_headers())
                if me_resp.status_code == 200:
                    me_data = me_resp.json()
                    st.session_state["username"] = me_data.get("username")
                    st.session_state["roles"] = me_data.get("roles", [])
                    st.success(f"Logged in as {st.session_state['username']}")
                    st.rerun()
                else:
                    st.error(f"Login succeeded but /me failed: {me_resp.text}")

    with register_tab:
        st.subheader("Create a new account")
        with st.form("register_form"):
            reg_username = st.text_input("Username", key="reg_username")
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input(
                "Password", type="password", key="reg_password")
            reg_password_confirm = st.text_input(
                "Confirm Password", type="password", key="reg_password_confirm")
            reg_first_name = st.text_input("First Name", key="reg_first_name")
            reg_last_name = st.text_input("Last Name", key="reg_last_name")
            reg_submitted = st.form_submit_button("Create Account")

        if reg_submitted:
            if not reg_username or not reg_email or not reg_password:
                st.error("Username, email, and password are required.")
            elif not reg_first_name or not reg_last_name:
                st.error("First name and last name are required.")
            elif reg_password != reg_password_confirm:
                st.error("Passwords do not match.")
            elif len(reg_password) < 6:
                st.error("Password must be at least 6 characters long.")
            else:
                try:
                    payload = {
                        "username": reg_username,
                        "email": reg_email,
                        "password": reg_password,
                        "first_name": reg_first_name,
                        "last_name": reg_last_name,
                    }
                    resp = requests.post(f"{AUTH_URL}/register", json=payload)
                    if resp.status_code == 200:
                        st.success(
                            "Account created successfully! You can now log in.")
                    else:
                        error_detail = resp.json().get("detail", resp.text)
                        st.error(f"Registration failed: {error_detail}")
                except Exception as e:
                    st.error(f"Error connecting to backend: {e}")

    # Stop here if not logged in
    st.stop()

# If we reached this point, user is authenticated and /me worked
username = st.session_state.get("username")
roles = st.session_state.get("roles", [])

is_admin = "admin" in roles
is_support = "support" in roles
is_client = "client" in roles

# Sidebar info + logout
st.sidebar.title("User info")
st.sidebar.write(f"**User:** {username}")
st.sidebar.write(f"**Roles:** {', '.join(roles) or '-'}")

if st.sidebar.button("Logout"):
    for key in ["access_token", "refresh_token", "username", "roles"]:
        st.session_state.pop(key, None)
    st.rerun()

st.title("Helpdesk Distributed System")


# ---------------------------
# Tabs: Create ticket / List tickets / Admin (if admin)
# ---------------------------

if is_admin:
    tab_create, tab_list, tab_admin = st.tabs(
        ["Create ticket", "Tickets", "Admin"])
else:
    tab_create, tab_list = st.tabs(["Create ticket", "Tickets"])


# ---------------------------
# Create ticket tab
# ---------------------------

with tab_create:
    st.header("Create a new ticket")

    st.write(f"Ticket will be created as user: **{username}**")

    title = st.text_input("Title")
    description = st.text_area("Description", height=150)

    if st.button("Create ticket"):
        if not title or not description:
            st.error("Title and description are required.")
        else:
            payload = {
                "title": title,
                "description": description,
                "created_by": username,
            }
            try:
                resp = requests.post(
                    f"{API_URL}/tickets",
                    json=payload,
                    headers=get_auth_headers(),
                )
            except Exception as e:
                st.error(f"Error calling backend: {e}")
            else:
                if resp.status_code == 200:
                    st.success("Ticket created successfully!")
                else:
                    st.error(f"Backend error: {resp.status_code} {resp.text}")


# ---------------------------
# List / manage tickets tab
# ---------------------------

with tab_list:
    st.header("Tickets")

    # Refresh button – just triggers a rerun, which will re-call /tickets
    if st.button("Refresh tickets"):
        st.rerun()

    try:
        resp = requests.get(f"{API_URL}/tickets", headers=get_auth_headers())
    except Exception as e:
        st.error(f"Error calling backend: {e}")
        st.stop()

    if resp.status_code == 401:
        st.error("Not authorized. Please log in again.")
        st.stop()
    elif resp.status_code != 200:
        st.error(f"Error loading tickets: {resp.status_code} {resp.text}")
        st.stop()

    tickets = resp.json()

    if not tickets:
        st.info("No tickets available.")
    else:
        for t in tickets:
            with st.expander(f"#{t['id']} - {t['title']}"):
                st.markdown(f"**Current status:** `{t['status']}`")
                st.write(t["description"])
                st.markdown(
                    f"**Created by:** `{t['created_by']}`  |  "
                    f"**Assigned to:** `{t.get('assigned_to') or '-'}`"
                )

                # Display notifications for this ticket
                st.markdown("---")
                st.markdown("**📋 Activity Log:**")
                try:
                    notif_resp = requests.get(
                        f"{API_URL}/tickets/{t['id']}/notifications",
                        headers=get_auth_headers(),
                    )
                    if notif_resp.status_code == 200:
                        notifications = notif_resp.json()
                        if notifications:
                            for n in notifications:
                                created_at = n.get("created_at", "")[
                                    :19].replace("T", " ")
                                event_icon = {
                                    "ticket_created": "🆕",
                                    "ticket_status_changed": "🔄",
                                    "ticket_assigned": "👤",
                                    "ticket_closed": "✅",
                                    "ticket_deleted": "🗑️",
                                }.get(n.get("event_type"), "📌")
                                st.markdown(
                                    f"{event_icon} `{created_at}` - {n.get('message')}")
                        else:
                            st.caption("No activity yet.")
                    elif notif_resp.status_code == 403:
                        st.caption("Not authorized to view activity.")
                    else:
                        st.caption("Could not load activity.")
                except Exception:
                    st.caption("Error loading activity.")
                st.markdown("---")

                # Only support/admin can change status and assignment
                if is_support or is_admin:
                    status_options = ["open", "in_progress", "closed"]
                    try:
                        current_index = status_options.index(t["status"])
                    except ValueError:
                        current_index = 0

                    new_status = st.selectbox(
                        "Change status",
                        status_options,
                        index=current_index,
                        key=f"status_{t['id']}",
                    )
                    assigned_to = st.text_input(
                        "Assign to (username)",
                        value=t.get("assigned_to") or "",
                        key=f"assignee_{t['id']}",
                    )
                else:
                    # Clients cannot edit fields
                    new_status = t["status"]
                    assigned_to = t.get("assigned_to")

                col1, col2 = st.columns(2)

                # Update button: support/admin only
                with col1:
                    if (is_support or is_admin) and st.button(
                        "Save update", key=f"update_{t['id']}"
                    ):
                        payload = {
                            "status": new_status,
                            "assigned_to": assigned_to or None,
                        }
                        try:
                            r = requests.patch(
                                f"{API_URL}/tickets/{t['id']}",
                                json=payload,
                                headers=get_auth_headers(),
                            )
                        except Exception as e:
                            st.error(f"Error calling backend: {e}")
                        else:
                            if r.status_code == 200:
                                st.success(
                                    "Ticket updated! Click 'Refresh tickets' to see new values.")
                            else:
                                st.error(
                                    f"Error updating ticket: {r.status_code} {r.text}")

                # Delete button: admin only
                with col2:
                    if is_admin and st.button(
                        "Delete ticket", key=f"delete_{t['id']}"
                    ):
                        try:
                            r = requests.delete(
                                f"{API_URL}/tickets/{t['id']}",
                                headers=get_auth_headers(),
                            )
                        except Exception as e:
                            st.error(f"Error calling backend: {e}")
                        else:
                            if r.status_code == 200:
                                st.success(
                                    "Ticket deleted! Click 'Refresh tickets' to update the list.")
                            else:
                                st.error(
                                    f"Error deleting ticket: {r.status_code} {r.text}")

# ---------------------------
# Admin tab (only visible to admins)
# ---------------------------

if is_admin:
    with tab_admin:
        st.header("Admin Panel")

        st.subheader("Create Support User")
        st.write("Create a new user with the **support** role.")

        with st.form("create_support_user_form"):
            support_username = st.text_input(
                "Username", key="support_username")
            support_email = st.text_input("Email", key="support_email")
            support_password = st.text_input(
                "Password", type="password", key="support_password")
            support_password_confirm = st.text_input(
                "Confirm Password", type="password", key="support_password_confirm")
            support_first_name = st.text_input(
                "First Name (optional)", key="support_first_name")
            support_last_name = st.text_input(
                "Last Name (optional)", key="support_last_name")
            support_submitted = st.form_submit_button("Create Support User")

        if support_submitted:
            if not support_username or not support_email or not support_password:
                st.error("Username, email, and password are required.")
            elif support_password != support_password_confirm:
                st.error("Passwords do not match.")
            elif len(support_password) < 6:
                st.error("Password must be at least 6 characters long.")
            else:
                try:
                    payload = {
                        "username": support_username,
                        "email": support_email,
                        "password": support_password,
                        "first_name": support_first_name or None,
                        "last_name": support_last_name or None,
                    }
                    resp = requests.post(
                        f"{AUTH_URL}/admin/users/support",
                        json=payload,
                        headers=get_auth_headers(),
                    )
                    if resp.status_code == 200:
                        st.success(
                            f"Support user '{support_username}' created successfully!")
                    else:
                        error_detail = resp.json().get("detail", resp.text)
                        st.error(
                            f"Failed to create support user: {error_detail}")
                except Exception as e:
                    st.error(f"Error connecting to backend: {e}")
