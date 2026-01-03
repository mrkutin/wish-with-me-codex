from copy import deepcopy

from app.utils import normalize_mongo


def build_wishlist_view(wishlist: dict, owner_user: dict, viewer_user: dict) -> dict:
    owner_id = str(owner_user.get("_id"))
    viewer_id = str(viewer_user.get("_id"))
    is_owner = owner_id == viewer_id
    is_admin = "admin" in viewer_user.get("roles", [])

    wl = normalize_mongo(deepcopy(wishlist))
    wl["owner_user_id"] = owner_id
    wl["owner_full_name"] = owner_user.get("full_name")

    if is_owner or is_admin:
        return wl

    wl.pop("access", None)
    share = wl.get("share")
    if isinstance(share, dict):
        share = {key: value for key, value in share.items() if key != "share_token"}
        wl["share"] = share
    return wl
