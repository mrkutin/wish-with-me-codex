/**
 * Share-related type definitions
 */

export type ShareLinkType = 'view' | 'mark';

export interface ShareLink {
  id: string;
  wishlist_id: string;
  token: string;
  link_type: ShareLinkType;
  expires_at: string | null;
  access_count: number;
  created_at: string;
  share_url: string;
}

export interface ShareLinkCreate {
  link_type?: ShareLinkType;
  expires_in_days?: number;
}

export interface ShareLinkListResponse {
  items: ShareLink[];
}

export interface OwnerPublicProfile {
  id: string;
  name: string;
  avatar_base64: string;
}

export interface SharedItem {
  id: string;
  title: string;
  description: string | null;
  price_amount: string | null;
  price_currency: string | null;
  image_base64: string | null;
  source_url: string | null;
  quantity: number;
  marked_quantity: number;
  available_quantity: number;
  my_mark_quantity: number;
}

export interface SharedWishlistInfo {
  id: string;
  title: string;
  description: string | null;
  icon: string;
  owner: OwnerPublicProfile;
  item_count: number;
}

export interface SharedWishlistResponse {
  wishlist: SharedWishlistInfo;
  items: SharedItem[];
  permissions: string[];
}

export interface SharedWishlistPreview {
  wishlist: {
    title: string;
    owner_name: string;
    item_count: number;
  };
  requires_auth: boolean;
  auth_redirect: string;
}

export interface MarkResponse {
  item_id: string;
  my_mark_quantity: number;
  total_marked_quantity: number;
  available_quantity: number;
}

export interface SharedWishlistBookmark {
  id: string;
  wishlist_id: string;
  share_token: string;
  last_accessed_at: string;
  wishlist: SharedWishlistInfo;
}

export interface SharedWishlistBookmarkListResponse {
  items: SharedWishlistBookmark[];
}
