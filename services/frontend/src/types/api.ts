import type { User } from './user';

export interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  locale?: string;
}

export interface ErrorDetail {
  field?: string;
  reason?: string;
}

export interface APIError {
  error: {
    code: string;
    message: string;
    details?: ErrorDetail | Record<string, unknown>;
    trace_id?: string;
  };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
