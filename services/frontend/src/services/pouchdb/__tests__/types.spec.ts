/**
 * Unit tests for PouchDB types and helper functions.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createId, extractId } from '../types';

describe('PouchDB Types', () => {
  describe('createId', () => {
    beforeEach(() => {
      // Reset mock to return predictable UUIDs
      vi.mocked(crypto.randomUUID).mockReturnValue('12345678-1234-1234-1234-123456789abc');
    });

    it('generates valid format with type prefix', () => {
      const id = createId('wishlist');

      expect(id).toBe('wishlist:12345678-1234-1234-1234-123456789abc');
    });

    it('generates valid format for item type', () => {
      const id = createId('item');

      expect(id).toBe('item:12345678-1234-1234-1234-123456789abc');
    });

    it('generates valid format for user type', () => {
      const id = createId('user');

      expect(id).toBe('user:12345678-1234-1234-1234-123456789abc');
    });

    it('generates valid format for mark type', () => {
      const id = createId('mark');

      expect(id).toBe('mark:12345678-1234-1234-1234-123456789abc');
    });

    it('generates valid format for bookmark type', () => {
      const id = createId('bookmark');

      expect(id).toBe('bookmark:12345678-1234-1234-1234-123456789abc');
    });

    it('generates unique IDs on successive calls', () => {
      vi.mocked(crypto.randomUUID)
        .mockReturnValueOnce('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
        .mockReturnValueOnce('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb');

      const id1 = createId('wishlist');
      const id2 = createId('wishlist');

      expect(id1).not.toBe(id2);
      expect(id1).toBe('wishlist:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa');
      expect(id2).toBe('wishlist:bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb');
    });
  });

  describe('extractId', () => {
    it('removes prefix from standard document ID', () => {
      const uuid = extractId('wishlist:12345678-1234-1234-1234-123456789abc');

      expect(uuid).toBe('12345678-1234-1234-1234-123456789abc');
    });

    it('removes prefix from item ID', () => {
      const uuid = extractId('item:abcdef12-1234-5678-9abc-def012345678');

      expect(uuid).toBe('abcdef12-1234-5678-9abc-def012345678');
    });

    it('removes prefix from user ID', () => {
      const uuid = extractId('user:11111111-2222-3333-4444-555555555555');

      expect(uuid).toBe('11111111-2222-3333-4444-555555555555');
    });

    it('handles plain UUID without prefix', () => {
      const uuid = extractId('12345678-1234-1234-1234-123456789abc');

      expect(uuid).toBe('12345678-1234-1234-1234-123456789abc');
    });

    it('handles empty string', () => {
      const result = extractId('');

      expect(result).toBe('');
    });

    it('handles ID with multiple colons by returning second segment only', () => {
      // Edge case: The function uses split(':')[1] so only returns second segment
      const uuid = extractId('share:abc:def:123');

      // Implementation returns parts[1] which is just 'abc'
      expect(uuid).toBe('abc');
    });

    it('handles ID with only prefix and no UUID', () => {
      const result = extractId('wishlist:');

      expect(result).toBe('');
    });
  });
});
