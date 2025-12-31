from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/")
def root():
    return {
        "service": "PyHoldem Pro API",
        "health": "/health",
        "docs": "/docs"
    }
