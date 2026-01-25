"""Share service for managing share links."""

import base64
import io
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import qrcode
from qrcode.image.styledpil import StyledPilImage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.share import ShareLink, ShareLinkType
from app.models.wishlist import Wishlist
from app.schemas.share import ShareLinkCreate, ShareLinkResponse

logger = logging.getLogger(__name__)


class ShareService:
    """Service for managing share links."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _get_share_url(self, token: str) -> str:
        """Get the full share URL for a token."""
        # Use frontend URL for share links (not API)
        base_url = settings.frontend_callback_url.rsplit("/", 2)[0]  # https://wishwith.me
        return f"{base_url}/s/{token}"

    def _generate_qr_code(self, url: str) -> str:
        """Generate QR code as base64 data URI."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        b64 = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{b64}"

    async def get_wishlist(self, wishlist_id: UUID) -> Wishlist | None:
        """Get a wishlist by ID."""
        result = await self.db.execute(
            select(Wishlist)
            .where(Wishlist.id == wishlist_id, Wishlist.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_share_links(self, wishlist_id: UUID) -> list[ShareLinkResponse]:
        """List all active share links for a wishlist."""
        result = await self.db.execute(
            select(ShareLink)
            .where(
                ShareLink.wishlist_id == wishlist_id,
                ShareLink.revoked == False,  # noqa: E712
            )
            .order_by(ShareLink.created_at.desc())
        )
        links = result.scalars().all()

        return [
            ShareLinkResponse(
                id=link.id,
                wishlist_id=link.wishlist_id,
                token=link.token,
                link_type=link.link_type,
                expires_at=link.expires_at,
                access_count=link.access_count,
                created_at=link.created_at,
                share_url=self._get_share_url(link.token),
            )
            for link in links
        ]

    async def create_share_link(
        self,
        wishlist_id: UUID,
        data: ShareLinkCreate,
    ) -> ShareLinkResponse:
        """Create a new share link for a wishlist."""
        token = ShareLink.generate_token()

        expires_at = None
        if data.expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)

        share_link = ShareLink(
            wishlist_id=wishlist_id,
            token=token,
            link_type=data.link_type,
            expires_at=expires_at,
        )

        self.db.add(share_link)
        await self.db.flush()
        await self.db.refresh(share_link)

        share_url = self._get_share_url(token)
        qr_code = self._generate_qr_code(share_url)

        return ShareLinkResponse(
            id=share_link.id,
            wishlist_id=share_link.wishlist_id,
            token=share_link.token,
            link_type=share_link.link_type,
            expires_at=share_link.expires_at,
            access_count=share_link.access_count,
            created_at=share_link.created_at,
            share_url=share_url,
            qr_code_base64=qr_code,
        )

    async def get_share_link(self, share_id: UUID) -> ShareLink | None:
        """Get a share link by ID."""
        result = await self.db.execute(
            select(ShareLink).where(ShareLink.id == share_id)
        )
        return result.scalar_one_or_none()

    async def get_share_link_by_token(self, token: str) -> ShareLink | None:
        """Get a share link by token."""
        result = await self.db.execute(
            select(ShareLink)
            .options(
                selectinload(ShareLink.wishlist).selectinload(Wishlist.user),
                selectinload(ShareLink.wishlist).selectinload(Wishlist.items),
            )
            .where(
                ShareLink.token == token,
                ShareLink.revoked == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def revoke_share_link(self, share_link: ShareLink) -> None:
        """Revoke a share link."""
        share_link.revoked = True
        await self.db.flush()

    async def increment_access_count(self, share_link: ShareLink) -> None:
        """Increment the access count for a share link."""
        share_link.access_count += 1
        await self.db.flush()

    def is_link_valid(self, share_link: ShareLink) -> bool:
        """Check if a share link is valid."""
        if share_link.revoked:
            return False
        if share_link.expires_at is not None:
            return share_link.expires_at > datetime.now(timezone.utc)
        return True
