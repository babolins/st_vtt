from fastapi import APIRouter

from . import auth, characters, chat, content, records, shared

router = APIRouter(prefix="/api")
router.include_router(auth.router)
router.include_router(content.router)
router.include_router(characters.router)
router.include_router(shared.router)
router.include_router(records.router)
router.include_router(chat.router)
