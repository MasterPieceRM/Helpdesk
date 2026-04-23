from fastapi import FastAPI, Depends, HTTPException
from typing import List
from . import models, db, schemas, crud, deps, cache, messaging, auth, keycloak_admin
from .auth import CurrentUser, get_current_user, require_roles

app = FastAPI(title="HelpDesk Ticket API")

# create tables on startup (simple for dev)


@app.on_event("startup")
def on_startup():
    # Wait for database to be available
    db.wait_for_db()

    with db.engine.begin() as conn:
        conn.exec_driver_sql("SELECT pg_advisory_lock(123456789)")
        try:
            models.Base.metadata.create_all(bind=conn)
        finally:
            conn.exec_driver_sql("SELECT pg_advisory_unlock(123456789)")


@app.get("/health")
def health_check():
    return {"status": "ok"}


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


@app.post("/notifications", response_model=schemas.NotificationOut)
def create_notification(
    notification: schemas.NotificationCreate,
    db_session=Depends(deps.get_db),
):
    """
    Create a notification for a ticket.
    Called by the worker service (internal API).
    """
    # Verify ticket exists
    ticket = crud.get_ticket(db_session, notification.ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    created = crud.create_notification(db_session, notification)
    print(
        f"[NOTIFICATION] Created notification for ticket #{notification.ticket_id}: {notification.event_type}")
    return created


@app.get("/tickets/{ticket_id}/notifications", response_model=List[schemas.NotificationOut])
def get_ticket_notifications(
    ticket_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db_session=Depends(deps.get_db),
):
    """
    Get all notifications for a specific ticket.
    """
    # Verify ticket exists
    ticket = crud.get_ticket(db_session, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Check permissions based on role
    roles = current_user.roles
    if "admin" not in roles:
        if "support" in roles:
            # Support can see notifications for tickets assigned to them
            if ticket.assigned_to != current_user.username:
                raise HTTPException(
                    status_code=403, detail="Not authorized to view this ticket's notifications")
        elif "client" in roles:
            # Clients can only see notifications for their own tickets
            if ticket.created_by != current_user.username:
                raise HTTPException(
                    status_code=403, detail="Not authorized to view this ticket's notifications")
        else:
            raise HTTPException(status_code=403, detail="Not authorized")

    notifications = crud.get_notifications_by_ticket(db_session, ticket_id)
    return notifications


@app.get("/tickets", response_model=List[schemas.TicketOut])
def list_tickets(
    current_user: CurrentUser = Depends(get_current_user),
    db_session=Depends(deps.get_db),
):
    roles = current_user.roles

    # Admin: sees everything, keep Redis cache for the global list
    if "admin" in roles:
        cached = cache.get_ticket_list_from_cache()
        if cached is not None:
            print("[CACHE] Serving tickets from Redis (admin)")
            return [schemas.TicketOut(**t) for t in cached]

        tickets = crud.get_tickets(db_session)
        print("[CACHE] Serving tickets from DB and storing in Redis (admin)")
        to_cache = [
            schemas.TicketOut.from_orm(t).model_dump(mode="json")
            for t in tickets
        ]
        cache.set_ticket_list_cache(to_cache)
        return tickets

    # Support: only tickets assigned to self (no shared cache, since list is user-specific)
    if "support" in roles:
        print(
            f"[AUTH] Support user {current_user.username} listing own assigned tickets")
        tickets = crud.get_tickets_by_assignee(
            db_session, current_user.username)
        return tickets

    # Client: only own tickets (created_by)
    if "client" in roles:
        print(
            f"[AUTH] Client user {current_user.username} listing own tickets")
        tickets = crud.get_tickets_by_creator(
            db_session, current_user.username)
        return tickets

    # Anything else: forbidden
    raise HTTPException(status_code=403, detail="Unknown or unauthorized role")


@app.post("/tickets", response_model=schemas.TicketOut)
def create_ticket(
    ticket: schemas.TicketCreate,
    current_user: CurrentUser = Depends(
        require_roles(["client", "support", "admin"])),
    db_session=Depends(deps.get_db),
):
    # Force created_by = current_user.username (ignore whatever comes from UI)
    ticket_data = ticket.model_dump()
    ticket_data["created_by"] = current_user.username

    created = crud.create_ticket(
        db_session, schemas.TicketCreate(**ticket_data))

    cache.invalidate_ticket_list_cache()
    print("[CACHE] Invalidated ticket list cache (create)")

    try:
        messaging.publish_ticket_event(
            "ticket_created",
            {
                "id": created.id,
                "title": created.title,
                "status": created.status,
                "created_by": created.created_by,
                "assigned_to": created.assigned_to,
            },
        )
        print(f"[MSG] Published 'ticket_created' for ticket #{created.id}")
    except Exception as e:
        print(f"[MSG] Error publishing ticket_created: {e}")

    return created


@app.get("/tickets/{ticket_id}", response_model=schemas.TicketOut)
def get_ticket(
    ticket_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db_session=Depends(deps.get_db),
):
    db_ticket = crud.get_ticket(db_session, ticket_id)
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    roles = current_user.roles

    # Admin can see any ticket
    if "admin" in roles:
        return db_ticket

    # Support: see only tickets assigned to self
    if "support" in roles:
        if db_ticket.assigned_to == current_user.username:
            return db_ticket
        raise HTTPException(
            status_code=403, detail="Not allowed to view this ticket")

    # Client: see only own tickets
    if "client" in roles:
        if db_ticket.created_by == current_user.username:
            return db_ticket
        raise HTTPException(
            status_code=403, detail="Not allowed to view this ticket")

    raise HTTPException(status_code=403, detail="Unknown or unauthorized role")


@app.patch("/tickets/{ticket_id}", response_model=schemas.TicketOut)
def update_ticket(
    ticket_id: int,
    ticket_update: schemas.TicketUpdate,
    current_user: CurrentUser = Depends(require_roles(["support", "admin"])),
    db_session=Depends(deps.get_db),
):
    # Get current state
    existing = crud.get_ticket(db_session, ticket_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Support: can only modify tickets assigned to themselves
    if "support" in current_user.roles and "admin" not in current_user.roles:
        if existing.assigned_to != current_user.username:
            raise HTTPException(
                status_code=403,
                detail="Support agents can only modify tickets assigned to themselves",
            )

    previous_status = existing.status
    previous_assigned_to = existing.assigned_to

    # Perform update
    updated = crud.update_ticket(db_session, ticket_id, ticket_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Ticket not found")

    cache.invalidate_ticket_list_cache()
    print("[CACHE] Invalidated ticket list cache (update)")

    payload = {
        "id": updated.id,
        "title": updated.title,
        "status": updated.status,
        "created_by": updated.created_by,
        "assigned_to": updated.assigned_to,
    }

    # Status changed
    if previous_status != updated.status:
        try:
            messaging.publish_ticket_event("ticket_status_changed", payload)
            print(
                f"[MSG] Published 'ticket_status_changed' for ticket #{updated.id} "
                f"({previous_status} -> {updated.status})"
            )
        except Exception as e:
            print(f"[MSG] Error publishing ticket_status_changed: {e}")

        if updated.status == "closed":
            try:
                messaging.publish_ticket_event("ticket_closed", payload)
                print(
                    f"[MSG] Published 'ticket_closed' for ticket #{updated.id}")
            except Exception as e:
                print(f"[MSG] Error publishing ticket_closed: {e}")

    # Assignment changed
    if previous_assigned_to != updated.assigned_to:
        try:
            messaging.publish_ticket_event("ticket_assigned", payload)
            print(
                f"[MSG] Published 'ticket_assigned' for ticket #{updated.id} "
                f"({previous_assigned_to} -> {updated.assigned_to})"
            )
        except Exception as e:
            print(f"[MSG] Error publishing ticket_assigned: {e}")

    return updated


@app.delete("/tickets/{ticket_id}")
def delete_ticket(
    ticket_id: int,
    current_user: CurrentUser = Depends(require_roles(["admin"])),
    db_session=Depends(deps.get_db),
):
    ticket = crud.delete_ticket(db_session, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    cache.invalidate_ticket_list_cache()
    print("[CACHE] Invalidated ticket list cache (delete)")

    payload = {
        "id": ticket.id,
        "title": ticket.title,
        "status": ticket.status,
        "created_by": ticket.created_by,
        "assigned_to": ticket.assigned_to,
    }

    try:
        messaging.publish_ticket_event("ticket_deleted", payload)
        print(f"[MSG] Published 'ticket_deleted' for ticket #{ticket.id}")
    except Exception as e:
        print(f"[MSG] Error publishing ticket_deleted: {e}")

    return {"detail": f"Ticket {ticket_id} deleted"}


@app.get("/me")
def read_me(current_user: CurrentUser = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "roles": current_user.roles,
    }
