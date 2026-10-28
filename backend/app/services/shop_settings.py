from sqlalchemy.orm import Session

from app.models import ShopSettings


def get_settings(db: Session) -> ShopSettings:
    settings = db.get(ShopSettings, 1)
    if settings is None:
        settings = ShopSettings(id=1)
        db.add(settings)
        db.flush()
    return settings
