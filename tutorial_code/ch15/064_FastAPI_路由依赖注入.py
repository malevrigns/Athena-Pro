from fastapi import Depends
from athena.config import Settings, get_settings

@router.get("/health")
def health(settings: Settings = Depends(get_settings)):
    return {"service": settings.service_name}