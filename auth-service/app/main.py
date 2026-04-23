from fastapi import FastAPI, Depends, HTTPException
from . import schemas, keycloak_admin
from .auth import CurrentUser, get_current_user, require_roles

app = FastAPI(title="HelpDesk Auth Service")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/me")
def read_me(current_user: CurrentUser = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "roles": current_user.roles,
    }


@app.post("/register")
def register_user(user: schemas.UserCreate):
    """
    Register a new user in Keycloak.
    This endpoint is public (no authentication required).
    """
    success, message = keycloak_admin.create_user(
        username=user.username,
        email=user.email,
        password=user.password,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"message": message}


@app.post("/admin/users/support")
def create_support_user(
    user: schemas.SupportUserCreate,
    current_user: CurrentUser = Depends(require_roles(["admin"])),
):
    """
    Create a new support user in Keycloak.
    This endpoint requires admin role.
    """
    success, message = keycloak_admin.create_user(
        username=user.username,
        email=user.email,
        password=user.password,
        first_name=user.first_name,
        last_name=user.last_name,
        role="support",
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"message": f"Support user '{user.username}' created successfully"}
