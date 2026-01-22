export interface Wishlist {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface WishlistCreate {
  name: string;
  description?: string | null;
  is_public?: boolean;
}

export interface WishlistUpdate {
  name?: string;
  description?: string | null;
  is_public?: boolean;
}

export interface WishlistListResponse {
  wishlists: Wishlist[];
  total: number;
  limit: number;
  offset: number;
}
