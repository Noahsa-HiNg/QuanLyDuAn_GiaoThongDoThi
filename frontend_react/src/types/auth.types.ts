import type { User } from './api.types';

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}
