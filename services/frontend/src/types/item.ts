export type ItemStatus = 'pending' | 'in_progress' | 'resolved' | 'error';

export interface Item {
  id: string;
  wishlist_id: string;
  title: string;
  description: string | null;
  price: number | null;
  currency: string | null;
  quantity: number;
  source_url: string | null;
  image_url: string | null;
  image_base64: string | null;
  status: ItemStatus;
  resolver_metadata: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface ItemCreate {
  title: string;
  description?: string | null;
  price?: number | null;
  currency?: string | null;
  quantity?: number;
  source_url?: string | null;
  image_url?: string | null;
  image_base64?: string | null;
  /** If true, skip automatic resolution even if source_url is provided */
  skip_resolution?: boolean;
}

export interface ItemUpdate {
  title?: string;
  description?: string | null;
  price?: number | null;
  currency?: string | null;
  quantity?: number;
  source_url?: string | null;
  image_url?: string | null;
  image_base64?: string | null;
}

export interface ItemListResponse {
  items: Item[];
  total: number;
  limit: number;
  offset: number;
}
