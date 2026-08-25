from sqlalchemy import delete, select

from ..assets.models import Asset, AssetSparePart, Factory, SparePart
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

def _part_out(part, asset_ids):
    return {"id": part.code, "name": part.name, "stock": part.stock, "unit": part.unit,
            "min_stock": part.min_stock, "eta": part.eta, "asset_ids": asset_ids}


def read_inventory(db, factory_id, asset_id=None):
    """The factory's stock. With `asset_id`, only the parts that fit that machine."""
    query = select(SparePart).where(SparePart.factory_id == factory_id).order_by(SparePart.name)
    if asset_id is not None:
        query = query.join(AssetSparePart, AssetSparePart.spare_part_id == SparePart.id).where(
            AssetSparePart.asset_id == asset_id
        )
    parts = list(db.scalars(query))
    links = {}
    for part_id, linked_asset in db.execute(
        select(AssetSparePart.spare_part_id, AssetSparePart.asset_id).where(
            AssetSparePart.spare_part_id.in_([p.id for p in parts] or [""])
        )
    ).all():
        links.setdefault(part_id, []).append(linked_asset)
    return [_part_out(part, links.get(part.id, [])) for part in parts]


def replace_inventory(db, factory_id, inventory):
    """Full replace, links included. Linking a machine from another factory is a 404, not a silent drop."""
    own_assets = set(db.scalars(select(Asset.id).where(Asset.factory_id == factory_id)))
    for part in inventory:
        for asset_id in part.asset_ids:
            if asset_id not in own_assets:
                raise ValueError("asset_not_found")
    existing = select(SparePart.id).where(SparePart.factory_id == factory_id)
    db.execute(delete(AssetSparePart).where(AssetSparePart.spare_part_id.in_(existing)))
    db.execute(delete(SparePart).where(SparePart.factory_id == factory_id))
    db.flush()
    for part in inventory:
        row = SparePart(factory_id=factory_id, code=part.id, name=part.name, stock=part.stock,
                        unit=part.unit, min_stock=part.min_stock, eta=part.eta)
        db.add(row)
        db.flush()
        for asset_id in dict.fromkeys(part.asset_ids):
            db.add(AssetSparePart(asset_id=asset_id, spare_part_id=row.id))
