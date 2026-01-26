/**
 * RxDB collection schemas for offline-first sync.
 */

import type { RxJsonSchema } from 'rxdb';

export interface WishlistDoc {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  is_public: boolean;
  created_at: string;
  updated_at: string;
  _deleted: boolean;
}

export interface ItemDoc {
  id: string;
  wishlist_id: string;
  title: string;
  description: string | null;
  price: string | null;
  currency: string | null;
  quantity: number;
  source_url: string | null;
  image_url: string | null;
  image_base64: string | null;
  status: 'pending' | 'resolving' | 'resolved' | 'failed';
  created_at: string;
  updated_at: string;
  _deleted: boolean;
}

export const wishlistSchema: RxJsonSchema<WishlistDoc> = {
  version: 0,
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
      maxLength: 36,
    },
    user_id: {
      type: 'string',
      maxLength: 36,
    },
    name: {
      type: 'string',
      maxLength: 100,
    },
    description: {
      type: ['string', 'null'],
      maxLength: 500,
    },
    is_public: {
      type: 'boolean',
    },
    created_at: {
      type: 'string',
      format: 'date-time',
    },
    updated_at: {
      type: 'string',
      format: 'date-time',
    },
    _deleted: {
      type: 'boolean',
    },
  },
  required: ['id', 'user_id', 'name', 'created_at', 'updated_at', '_deleted'],
  indexes: ['user_id', 'updated_at'],
};

export const itemSchema: RxJsonSchema<ItemDoc> = {
  version: 0,
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
      maxLength: 36,
    },
    wishlist_id: {
      type: 'string',
      maxLength: 36,
    },
    title: {
      type: 'string',
      maxLength: 200,
    },
    description: {
      type: ['string', 'null'],
      maxLength: 1000,
    },
    price: {
      type: ['string', 'null'],
      maxLength: 20,
    },
    currency: {
      type: ['string', 'null'],
      maxLength: 3,
    },
    quantity: {
      type: 'integer',
      minimum: 1,
    },
    source_url: {
      type: ['string', 'null'],
    },
    image_url: {
      type: ['string', 'null'],
    },
    image_base64: {
      type: ['string', 'null'],
    },
    status: {
      type: 'string',
      enum: ['pending', 'resolving', 'resolved', 'failed'],
    },
    created_at: {
      type: 'string',
      format: 'date-time',
    },
    updated_at: {
      type: 'string',
      format: 'date-time',
    },
    _deleted: {
      type: 'boolean',
    },
  },
  required: ['id', 'wishlist_id', 'title', 'status', 'created_at', 'updated_at', '_deleted'],
  indexes: ['wishlist_id', 'status', 'updated_at'],
};
