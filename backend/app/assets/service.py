from ..assets.models import Asset, Factory
from ..config import get_settings
from ..repositories import one_or_404


def get_asset(db, asset_id, identity):
    try:
        return one_or_404(db, Asset, asset_id, identity.factory_id)
    except ValueError:
        raise ValueError("asset_not_found")


def ensure_factory(db, identity):
    factory = db.get(Factory, identity.factory_id)
    if factory is None:
        factory = Factory(
            id=identity.factory_id,
            name=identity.factory_id,
            deployment_tier=get_settings().deployment_tier,
        )
        db.add(factory)
        db.flush()
    return factory