/**
 * Test data factories for creating mock documents.
 *
 * These factories create realistic test data that matches the application's
 * data models. Each factory accepts optional overrides for customization.
 */

import type { User, SocialLinks } from '@/types/user';
import type { Wishlist } from '@/types/wishlist';
import type { Item, ItemStatus } from '@/types/item';
import type {
  UserDoc,
  WishlistDoc,
  ItemDoc,
  MarkDoc,
  BookmarkDoc,
  ShareDoc,
} from '@/services/pouchdb/types';

// ============================================
// ID Generation Helpers
// ============================================

let idCounter = 0;

/**
 * Generate a unique test ID.
 */
function generateId(): string {
  return `test-${++idCounter}-${Date.now().toString(36)}`;
}

/**
 * Reset the ID counter (useful between test suites).
 */
export function resetIdCounter(): void {
  idCounter = 0;
}

/**
 * Create a document ID with type prefix.
 */
function createDocId(type: string, id?: string): string {
  return `${type}:${id || generateId()}`;
}

// ============================================
// Timestamp Helpers
// ============================================

/**
 * Get current ISO timestamp.
 */
function now(): string {
  return new Date().toISOString();
}

/**
 * Get ISO timestamp for a date in the past.
 */
function daysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString();
}

/**
 * Get ISO timestamp for a date in the future.
 */
function daysFromNow(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString();
}

// ============================================
// User Factories
// ============================================

export interface CreateMockUserOptions {
  id?: string;
  email?: string;
  name?: string;
  avatar_base64?: string;
  bio?: string;
  public_url_slug?: string;
  social_links?: SocialLinks;
  locale?: string;
  birthday?: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * Create a mock User object (API response format).
 */
export function createMockUser(options: CreateMockUserOptions = {}): User {
  const id = options.id || createDocId('user');
  return {
    id,
    email: options.email || `user-${idCounter}@example.com`,
    name: options.name || `Test User ${idCounter}`,
    avatar_base64: options.avatar_base64 || '',
    bio: options.bio,
    public_url_slug: options.public_url_slug,
    social_links: options.social_links,
    locale: options.locale || 'en',
    birthday: options.birthday,
    created_at: options.created_at || now(),
    updated_at: options.updated_at || now(),
  };
}

export interface CreateMockUserDocOptions extends CreateMockUserOptions {
  _rev?: string;
  _deleted?: boolean;
  access?: string[];
  password_hash?: string;
}

/**
 * Create a mock UserDoc (PouchDB/CouchDB format).
 */
export function createMockUserDoc(options: CreateMockUserDocOptions = {}): UserDoc {
  const id = options.id || createDocId('user');
  const user = createMockUser({ ...options, id });

  return {
    _id: id,
    _rev: options._rev,
    _deleted: options._deleted,
    type: 'user',
    email: user.email,
    name: user.name,
    avatar_base64: user.avatar_base64 || null,
    bio: user.bio || null,
    public_url_slug: user.public_url_slug || null,
    locale: user.locale,
    access: options.access || [id],
    created_at: user.created_at,
    updated_at: user.updated_at,
  };
}

// ============================================
// Wishlist Factories
// ============================================

export interface CreateMockWishlistOptions {
  id?: string;
  user_id?: string;
  name?: string;
  description?: string | null;
  is_public?: boolean;
  icon?: string;
  icon_color?: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * Create a mock Wishlist object (API response format).
 */
export function createMockWishlist(options: CreateMockWishlistOptions = {}): Wishlist {
  const id = options.id || createDocId('wishlist');
  return {
    id,
    user_id: options.user_id || createDocId('user'),
    name: options.name || `Test Wishlist ${idCounter}`,
    description: options.description === undefined ? `Description for wishlist ${idCounter}` : options.description,
    is_public: options.is_public ?? false,
    icon: options.icon || 'favorite',
    icon_color: options.icon_color || 'primary',
    created_at: options.created_at || now(),
    updated_at: options.updated_at || now(),
  };
}

export interface CreateMockWishlistDocOptions extends CreateMockWishlistOptions {
  _rev?: string;
  _deleted?: boolean;
  owner_id?: string;
  access?: string[];
}

/**
 * Create a mock WishlistDoc (PouchDB/CouchDB format).
 */
export function createMockWishlistDoc(options: CreateMockWishlistDocOptions = {}): WishlistDoc {
  const id = options.id || createDocId('wishlist');
  const ownerId = options.owner_id || options.user_id || createDocId('user');
  const wishlist = createMockWishlist({ ...options, id, user_id: ownerId });

  return {
    _id: id,
    _rev: options._rev,
    _deleted: options._deleted,
    type: 'wishlist',
    owner_id: ownerId,
    name: wishlist.name,
    description: wishlist.description,
    icon: wishlist.icon,
    icon_color: wishlist.icon_color,
    is_public: wishlist.is_public,
    access: options.access || [ownerId],
    created_at: wishlist.created_at,
    updated_at: wishlist.updated_at,
  };
}

// ============================================
// Item Factories
// ============================================

export interface CreateMockItemOptions {
  id?: string;
  wishlist_id?: string;
  title?: string;
  description?: string | null;
  price?: number | null;
  currency?: string | null;
  quantity?: number;
  source_url?: string | null;
  image_url?: string | null;
  image_base64?: string | null;
  status?: ItemStatus;
  resolver_metadata?: Record<string, unknown> | null;
  created_at?: string;
  updated_at?: string;
}

/**
 * Create a mock Item object (API response format).
 */
export function createMockItem(options: CreateMockItemOptions = {}): Item {
  const id = options.id || createDocId('item');
  return {
    id,
    wishlist_id: options.wishlist_id || createDocId('wishlist'),
    title: options.title || `Test Item ${idCounter}`,
    description: options.description === undefined ? `Description for item ${idCounter}` : options.description,
    price: options.price === undefined ? Math.floor(Math.random() * 10000) + 100 : options.price,
    currency: options.currency === undefined ? 'RUB' : options.currency,
    quantity: options.quantity ?? 1,
    source_url: options.source_url === undefined ? `https://example.com/product/${idCounter}` : options.source_url,
    image_url: options.image_url === undefined ? `https://example.com/images/${idCounter}.jpg` : options.image_url,
    image_base64: options.image_base64 === undefined ? null : options.image_base64,
    status: options.status || 'resolved',
    resolver_metadata: options.resolver_metadata ?? null,
    created_at: options.created_at || now(),
    updated_at: options.updated_at || now(),
  };
}

export interface CreateMockItemDocOptions extends CreateMockItemOptions {
  _rev?: string;
  _deleted?: boolean;
  owner_id?: string;
  access?: string[];
  resolve_confidence?: number;
  resolve_error?: string;
  resolved_at?: string;
}

/**
 * Create a mock ItemDoc (PouchDB/CouchDB format).
 */
export function createMockItemDoc(options: CreateMockItemDocOptions = {}): ItemDoc {
  const id = options.id || createDocId('item');
  const ownerId = options.owner_id || createDocId('user');
  const wishlistId = options.wishlist_id || createDocId('wishlist');
  const item = createMockItem({ ...options, id, wishlist_id: wishlistId });

  return {
    _id: id,
    _rev: options._rev,
    _deleted: options._deleted,
    type: 'item',
    wishlist_id: wishlistId,
    owner_id: ownerId,
    title: item.title,
    description: item.description,
    price: item.price,
    currency: item.currency,
    quantity: item.quantity,
    source_url: item.source_url,
    image_url: item.image_url,
    image_base64: item.image_base64,
    status: item.status as 'pending' | 'resolved' | 'error',
    resolve_confidence: options.resolve_confidence,
    resolve_error: options.resolve_error,
    resolved_at: options.resolved_at,
    access: options.access || [ownerId],
    created_at: item.created_at,
    updated_at: item.updated_at,
  };
}

// ============================================
// Mark Factories
// ============================================

export interface CreateMockMarkOptions {
  id?: string;
  item_id?: string;
  wishlist_id?: string;
  owner_id?: string;
  marked_by?: string;
  quantity?: number;
  created_at?: string;
  updated_at?: string;
}

export interface CreateMockMarkDocOptions extends CreateMockMarkOptions {
  _rev?: string;
  _deleted?: boolean;
  access?: string[];
}

/**
 * Create a mock MarkDoc (PouchDB/CouchDB format).
 *
 * Marks represent when a user marks an item as "I'll get this".
 * The owner_id is excluded from access to keep it a surprise.
 */
export function createMockMark(options: CreateMockMarkDocOptions = {}): MarkDoc {
  const id = options.id || createDocId('mark');
  const markedBy = options.marked_by || createDocId('user');
  const ownerId = options.owner_id || createDocId('user');

  return {
    _id: id,
    _rev: options._rev,
    _deleted: options._deleted,
    type: 'mark',
    item_id: options.item_id || createDocId('item'),
    wishlist_id: options.wishlist_id || createDocId('wishlist'),
    owner_id: ownerId,
    marked_by: markedBy,
    quantity: options.quantity ?? 1,
    // Access excludes owner_id to keep marks hidden from wishlist owner
    access: options.access || [markedBy],
    created_at: options.created_at || now(),
    updated_at: options.updated_at || now(),
  };
}

// Alias for consistency
export { createMockMark as createMockMarkDoc };

// ============================================
// Bookmark Factories
// ============================================

export interface CreateMockBookmarkOptions {
  id?: string;
  user_id?: string;
  share_id?: string;
  wishlist_id?: string;
  owner_name?: string;
  owner_avatar_base64?: string | null;
  wishlist_name?: string;
  wishlist_icon?: string;
  wishlist_icon_color?: string;
  created_at?: string;
  updated_at?: string;
  last_accessed_at?: string;
}

export interface CreateMockBookmarkDocOptions extends CreateMockBookmarkOptions {
  _rev?: string;
  _deleted?: boolean;
  access?: string[];
}

/**
 * Create a mock BookmarkDoc (PouchDB/CouchDB format).
 *
 * Bookmarks are saved references to shared wishlists.
 */
export function createMockBookmark(options: CreateMockBookmarkDocOptions = {}): BookmarkDoc {
  const id = options.id || createDocId('bookmark');
  const userId = options.user_id || createDocId('user');

  return {
    _id: id,
    _rev: options._rev,
    _deleted: options._deleted,
    type: 'bookmark',
    user_id: userId,
    share_id: options.share_id || createDocId('share'),
    wishlist_id: options.wishlist_id || createDocId('wishlist'),
    owner_name: options.owner_name || `Owner ${idCounter}`,
    owner_avatar_base64: options.owner_avatar_base64 ?? null,
    wishlist_name: options.wishlist_name || `Shared Wishlist ${idCounter}`,
    wishlist_icon: options.wishlist_icon || 'favorite',
    wishlist_icon_color: options.wishlist_icon_color || 'primary',
    access: options.access || [userId],
    created_at: options.created_at || now(),
    updated_at: options.updated_at,
    last_accessed_at: options.last_accessed_at || now(),
  };
}

// Alias for consistency
export { createMockBookmark as createMockBookmarkDoc };

// ============================================
// Share Factories
// ============================================

export interface CreateMockShareOptions {
  id?: string;
  wishlist_id?: string;
  owner_id?: string;
  token?: string;
  link_type?: 'view' | 'mark';
  expires_at?: string | null;
  access_count?: number;
  revoked?: boolean;
  granted_users?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface CreateMockShareDocOptions extends CreateMockShareOptions {
  _rev?: string;
  _deleted?: boolean;
  access?: string[];
}

/**
 * Create a mock ShareDoc (PouchDB/CouchDB format).
 *
 * Shares represent shareable links to wishlists.
 */
export function createMockShare(options: CreateMockShareDocOptions = {}): ShareDoc {
  const id = options.id || createDocId('share');
  const ownerId = options.owner_id || createDocId('user');

  return {
    _id: id,
    _rev: options._rev,
    _deleted: options._deleted,
    type: 'share',
    wishlist_id: options.wishlist_id || createDocId('wishlist'),
    owner_id: ownerId,
    token: options.token || `share-token-${generateId()}`,
    link_type: options.link_type || 'mark',
    expires_at: options.expires_at ?? null,
    access_count: options.access_count ?? 0,
    revoked: options.revoked ?? false,
    granted_users: options.granted_users || [],
    access: options.access || [ownerId],
    created_at: options.created_at || now(),
    updated_at: options.updated_at || now(),
  };
}

// Alias for consistency
export { createMockShare as createMockShareDoc };

// ============================================
// Batch Factories
// ============================================

/**
 * Create multiple mock users.
 */
export function createMockUsers(count: number, options: CreateMockUserOptions = {}): User[] {
  return Array.from({ length: count }, (_, i) =>
    createMockUser({
      ...options,
      name: options.name ? `${options.name} ${i + 1}` : undefined,
      email: options.email ? `${i + 1}-${options.email}` : undefined,
    })
  );
}

/**
 * Create multiple mock wishlists.
 */
export function createMockWishlists(count: number, options: CreateMockWishlistOptions = {}): Wishlist[] {
  return Array.from({ length: count }, (_, i) =>
    createMockWishlist({
      ...options,
      name: options.name ? `${options.name} ${i + 1}` : undefined,
    })
  );
}

/**
 * Create multiple mock items.
 */
export function createMockItems(count: number, options: CreateMockItemOptions = {}): Item[] {
  return Array.from({ length: count }, (_, i) =>
    createMockItem({
      ...options,
      title: options.title ? `${options.title} ${i + 1}` : undefined,
    })
  );
}

/**
 * Create multiple mock item docs.
 */
export function createMockItemDocs(count: number, options: CreateMockItemDocOptions = {}): ItemDoc[] {
  return Array.from({ length: count }, (_, i) =>
    createMockItemDoc({
      ...options,
      title: options.title ? `${options.title} ${i + 1}` : undefined,
    })
  );
}

/**
 * Create a complete wishlist with items.
 */
export function createMockWishlistWithItems(
  itemCount: number,
  wishlistOptions: CreateMockWishlistDocOptions = {},
  itemOptions: CreateMockItemDocOptions = {}
): { wishlist: WishlistDoc; items: ItemDoc[] } {
  const ownerId = wishlistOptions.owner_id || createDocId('user');
  const wishlist = createMockWishlistDoc({ ...wishlistOptions, owner_id: ownerId });

  const items = Array.from({ length: itemCount }, () =>
    createMockItemDoc({
      ...itemOptions,
      wishlist_id: wishlist._id,
      owner_id: ownerId,
      access: [ownerId],
    })
  );

  return { wishlist, items };
}

// ============================================
// Scenario Factories
// ============================================

/**
 * Create a scenario with a user who has wishlists and items.
 */
export function createUserWithWishlistsScenario(
  wishlistCount = 2,
  itemsPerWishlist = 3
): {
  user: UserDoc;
  wishlists: WishlistDoc[];
  items: ItemDoc[];
} {
  const user = createMockUserDoc();
  const wishlists: WishlistDoc[] = [];
  const items: ItemDoc[] = [];

  for (let i = 0; i < wishlistCount; i++) {
    const { wishlist, items: wishlistItems } = createMockWishlistWithItems(
      itemsPerWishlist,
      { owner_id: user._id, access: [user._id] },
      { owner_id: user._id, access: [user._id] }
    );
    wishlists.push(wishlist);
    items.push(...wishlistItems);
  }

  return { user, wishlists, items };
}

/**
 * Create a scenario with shared wishlist and marks.
 */
export function createSharedWishlistScenario(): {
  owner: UserDoc;
  viewer: UserDoc;
  wishlist: WishlistDoc;
  items: ItemDoc[];
  share: ShareDoc;
  marks: MarkDoc[];
  bookmark: BookmarkDoc;
} {
  const owner = createMockUserDoc({ name: 'Wishlist Owner' });
  const viewer = createMockUserDoc({ name: 'Wishlist Viewer' });

  const { wishlist, items } = createMockWishlistWithItems(
    3,
    {
      owner_id: owner._id,
      access: [owner._id, viewer._id],
    },
    {
      owner_id: owner._id,
      access: [owner._id, viewer._id],
    }
  );

  const share = createMockShare({
    wishlist_id: wishlist._id,
    owner_id: owner._id,
    granted_users: [viewer._id],
    access: [owner._id],
  });

  // Viewer marks one item
  const marks = [
    createMockMark({
      item_id: items[0]._id,
      wishlist_id: wishlist._id,
      owner_id: owner._id,
      marked_by: viewer._id,
      access: [viewer._id], // Hidden from owner
    }),
  ];

  const bookmark = createMockBookmark({
    user_id: viewer._id,
    share_id: share._id,
    wishlist_id: wishlist._id,
    owner_name: owner.name,
    wishlist_name: wishlist.name,
    wishlist_icon: wishlist.icon,
    wishlist_icon_color: wishlist.icon_color,
    access: [viewer._id],
  });

  return { owner, viewer, wishlist, items, share, marks, bookmark };
}

// ============================================
// Export utilities
// ============================================

export { daysAgo, daysFromNow, now, createDocId, generateId };
