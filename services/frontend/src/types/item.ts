export type ItemStatus = 'pending' | 'resolving' | 'resolved' | 'failed';

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
