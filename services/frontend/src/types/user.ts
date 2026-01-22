export interface SocialLinks {
  instagram?: string;
  telegram?: string;
  vk?: string;
  twitter?: string;
  facebook?: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  avatar_base64: string;
  bio?: string;
  public_url_slug?: string;
  social_links?: SocialLinks;
  locale: string;
  created_at: string;
  updated_at: string;
}

export interface UserPublicProfile {
  id: string;
  name: string;
  avatar_base64: string;
  bio?: string;
  social_links?: SocialLinks;
}

export interface ConnectedAccount {
  provider: string;
  email?: string;
  connected_at: string;
}
