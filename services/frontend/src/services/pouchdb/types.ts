/**
 * TypeScript types for CouchDB documents.
 * All documents follow the single-database pattern with type prefixes and access arrays.
 */

// Base document interface - all CouchDB documents have these fields
export interface BaseDoc {
  _id: string;
  _rev?: string;
  _deleted?: boolean;
  type: 'user' | 'wishlist' | 'item' | 'mark' | 'share' | 'bookmark';
  access: string[]; // User IDs who can access this document
  created_at: string;
  updated_at: string;
}

// User document
export interface UserDoc extends BaseDoc {
  type: 'user';
  email: string;
  name: string;
  avatar_base64?: string | null;
  bio?: string | null;
  public_url_slug?: string | null;
  locale: string;
  password_hash?: string; // Only on server, never synced to client
}

// Wishlist document
export interface WishlistDoc extends BaseDoc {
  type: 'wishlist';
  owner_id: string;
  name: string;
  description?: string | null;
  icon: string;
  is_public: boolean;
}

// Item document
export interface ItemDoc extends BaseDoc {
  type: 'item';
  wishlist_id: string;
  owner_id: string;
  title: string;
  description?: string | null;
  price?: number | null;
  currency?: string | null;
  quantity: number;
  source_url?: string | null;
  image_url?: string | null;
  image_base64?: string | null;
  status: 'pending' | 'resolved' | 'error';
  resolve_confidence?: number;
  resolve_error?: string;
  resolved_at?: string;
}

// Mark document (when someone marks an item as "I'll get this")
export interface MarkDoc extends BaseDoc {
  type: 'mark';
  item_id: string;
  wishlist_id: string;
  owner_id: string; // Wishlist owner (for access filtering - marks are hidden from owner)
  marked_by: string; // User who marked it
  quantity: number;
}

// Share document
export interface ShareDoc extends BaseDoc {
  type: 'share';
  wishlist_id: string;
  owner_id: string;
  token: string;
  link_type: 'view' | 'mark';
  expires_at?: string | null;
  access_count: number;
  revoked: boolean;
  granted_users: string[];
}

// Bookmark document (user's saved shared wishlists)
export interface BookmarkDoc {
  _id: string;
  _rev?: string;
  _deleted?: boolean;
  type: 'bookmark';
  user_id: string;
  share_id: string;
  wishlist_id?: string;  // Direct reference for easy lookup
  // Cached owner/wishlist info for offline-first access
  owner_name?: string;
  owner_avatar_base64?: string | null;
  wishlist_name?: string;
  wishlist_icon?: string;
  access: string[];
  created_at: string;
  updated_at?: string;
  last_accessed_at: string;
}

// Union type for all documents
export type CouchDBDoc = UserDoc | WishlistDoc | ItemDoc | MarkDoc | ShareDoc | BookmarkDoc;

// Helper to extract ID without type prefix
export function extractId(docId: string): string {
  const parts = docId.split(':');
  return parts.length > 1 ? parts[1] : docId;
}

// Helper to create ID with type prefix
export function createId(type: string): string {
  return `${type}:${crypto.randomUUID()}`;
}

// PouchDB query selector types
export interface PouchDBSelector {
  [key: string]: unknown;
  type?: string;
  _deleted?: { $ne: boolean } | boolean;
  access?: { $elemMatch: { $eq: string } };
}

// PouchDB find options
export interface PouchDBFindOptions {
  selector: PouchDBSelector;
  sort?: Array<{ [key: string]: 'asc' | 'desc' }>;
  limit?: number;
  skip?: number;
  fields?: string[];
}

// Sync status
export type SyncStatus = 'idle' | 'syncing' | 'paused' | 'error' | 'offline';

// Change event from PouchDB
export interface PouchDBChange<T = CouchDBDoc> {
  id: string;
  seq: number | string;
  changes: Array<{ rev: string }>;
  doc?: T;
  deleted?: boolean;
}
