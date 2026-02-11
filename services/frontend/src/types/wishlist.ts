export interface Wishlist {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  is_public: boolean;
  icon: string;
  icon_color: string;
  created_at: string;
  updated_at: string;
}

export interface WishlistCreate {
  name: string;
  description?: string | null;
  is_public?: boolean;
  icon?: string;
  icon_color?: string;
}

export interface WishlistUpdate {
  name?: string;
  description?: string | null;
  is_public?: boolean;
  icon?: string;
  icon_color?: string;
}

export interface WishlistListResponse {
  wishlists: Wishlist[];
  total: number;
  limit: number;
  offset: number;
}
