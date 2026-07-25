from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from analysis.router import router as analysis_router
from auth.router import router as auth_router
from config import settings
from schemas import CleanTextRequest, CleanTextResponse
from video.router import router as video_router

app = FastAPI(title="VerifyVault API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Used only for the short-lived Google OAuth handshake (state/nonce/PKCE
# verifier) - unrelated to the app's own JWT access/refresh tokens.
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

app.include_router(auth_router)
app.include_router(analysis_router)
app.include_router(video_router)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/clean", response_model=CleanTextResponse)
def clean_text(payload: CleanTextRequest):
    without_hashes = payload.text.replace("#", "").strip()
    without_both = payload.text.replace("#", "").replace("*", "").strip()
    return CleanTextResponse(
        without_hashes=without_hashes,
        without_hashes_and_asterisks=without_both
    )
