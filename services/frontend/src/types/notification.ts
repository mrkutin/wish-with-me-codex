/**
 * Notification-related type definitions
 */

export type NotificationType =
  | 'wishlist_shared'
  | 'item_marked'
  | 'item_unmarked'
  | 'item_resolved'
  | 'item_resolution_failed';

export interface Notification {
  id: string;
  type: NotificationType;
  payload: Record<string, string | null>;
  read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  items: Notification[];
  unread_count: number;
  total: number;
}
