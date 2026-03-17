from datetime import timedelta, datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient as HttpxAsyncClient


from app.api import deps
from app.core import security
from app.core.config import settings
from app.schemas.token import Token
from app.schemas.user import User as UserSchema
from app.schemas.project import ProjectCreate
from app.crud import crud_user, crud_project, crud_audit


router = APIRouter()

@router.get("/login/{provider}")

async def login_with_oauth(
    provider: str,
) -> Any:
    """
    Initiate SSO login
    """
    if provider == "gmail":
        if not settings.GOOGLE_CLIENT_ID or settings.GOOGLE_CLIENT_ID == "your_google_client_id":
            raise HTTPException(status_code=500, detail="Google OAuth not configured. Please set GOOGLE_CLIENT_ID in backend/.env")

        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={settings.GOOGLE_CLIENT_ID}"
            f"&redirect_uri={settings.BACKEND_URL}{settings.API_V1_STR}/auth/callback/{provider}"
            f"&response_type=code"
            f"&scope=openid email profile https://mail.google.com/"
            f"&access_type=offline"
            f"&prompt=consent"
        )
        return RedirectResponse(auth_url)

    
    elif provider == "outlook":
        if not settings.MICROSOFT_CLIENT_ID or settings.MICROSOFT_CLIENT_ID == "your_microsoft_client_id":
            raise HTTPException(status_code=500, detail="Microsoft OAuth not configured. Please set MICROSOFT_CLIENT_ID in backend/.env")

        auth_url = (
            f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
            f"?client_id={settings.MICROSOFT_CLIENT_ID}"
            f"&redirect_uri={settings.BACKEND_URL}{settings.API_V1_STR}/auth/callback/{provider}"
            f"&response_type=code"
            f"&scope=openid email profile offline_access https://outlook.office.com/IMAP.AccessAsUser.All"
            f"&response_mode=query"
        )
        return RedirectResponse(auth_url)

    
    raise HTTPException(status_code=400, detail="Unsupported provider")

@router.get("/callback/{provider}")
async def callback_oauth(
    provider: str,
    code: str,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    OAuth2 callback for SSO
    """
    redirect_uri = f"{settings.BACKEND_URL}{settings.API_V1_STR}/auth/callback/{provider}"

    
    if provider == "gmail":
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

    elif provider == "outlook":
        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        data = {
            "code": code,
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "scope": "openid email profile offline_access https://outlook.office.com/IMAP.AccessAsUser.All",
        }


    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    # Exchange code for tokens
    async with HttpxAsyncClient() as client:
        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to fetch tokens: {response.text}")
        
        tokens = response.json()
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)
        
        # Get user info
        email = ""
        full_name = ""
        oauth_id = ""
        
        if provider == "gmail":
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if userinfo_response.status_code == 200:
                ui = userinfo_response.json()
                email = ui.get("email")
                full_name = ui.get("name")
                oauth_id = ui.get("sub")
        elif provider == "outlook":
            # We use the id_token from Microsoft (OIDC) which is safer and avoids Graph API scope conflicts
            id_token = tokens.get("id_token")
            if id_token:
                from jose import jwt
                # We don't verify the signature here for simplicity, as we just got it over HTTPS from MS
                payload = jwt.get_unverified_claims(id_token)
                email = payload.get("email") or payload.get("preferred_username")
                full_name = payload.get("name")
                oauth_id = payload.get("sub")
            else:
                print("ERROR: No id_token returned from Microsoft")


        if not email:
            print(f"ERROR: No email found for provider {provider.value}. Check if scopes are sufficient.")
            raise HTTPException(status_code=400, detail="Failed to retrieve user email")


        # Create or update user
        user = await crud_user.create_or_update_oauth(
            db,
            email=email,
            full_name=full_name or email,
            provider=provider,
            oauth_id=oauth_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        )
        
        # Audit log for SSO login
        await crud_audit.log_action(
            db, 
            "auth.login", 
            user.id, 
            "user", 
            user.id, 
            details={"provider": provider}
        )


        # --- AUTO SETUP: Default Projects & Email Settings ---
        from sqlalchemy import select, update as sa_update
        from app.models.project import Project as ProjectModel
        
        # 1. Claim any orphan projects (owner_id is None)
        orphan_query = sa_update(ProjectModel).where(ProjectModel.owner_id == None).values(owner_id=user.id)
        await db.execute(orphan_query)
        await db.commit()

        # 2. Ensure "General" project exists for this user

        async def ensure_project(name: str):
            p_query = select(ProjectModel).where(ProjectModel.owner_id == user.id, ProjectModel.name == name)
            p_result = await db.execute(p_query)
            p = p_result.scalars().first()
            if not p:
                print(f"INFO: Creating {name} project for user {user.email}")
                p_in = ProjectCreate(name=name, description=f"Your {name.lower()} workspace")
                p = await crud_project.create(db, obj_in=p_in, owner_id=user.id)
            return p

        general_project = await ensure_project("General")
        # --- END AUTO SETUP ---




        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        nimbus_token = security.create_access_token(
            user.email, expires_delta=access_token_expires
        )
        
        # In a real app, we would redirect back to the frontend with the token in a cookie or fragment
        # For this setup, we'll redirect to a frontend-friendly URL
        frontend_url = f"http://localhost:3100/login?token={nimbus_token}"
        return RedirectResponse(frontend_url)


