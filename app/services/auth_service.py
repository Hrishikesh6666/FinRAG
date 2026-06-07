from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import timedelta

from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings


class AuthService:
    def register(self, db: Session, payload: RegisterRequest) -> User:
        # Uniqueness checks
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        if db.query(User).filter(User.username == payload.username).first():
            raise HTTPException(status_code=400, detail="Username already taken")

        user = User(
            email=payload.email,
            username=payload.username,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def login(self, db: Session, payload: LoginRequest) -> TokenResponse:
        user = db.query(User).filter(User.email == payload.email).first()
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")

        expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        token = create_access_token(data={"sub": str(user.id)}, expires_delta=expire)

        return TokenResponse(
            access_token=token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )


auth_service = AuthService()
