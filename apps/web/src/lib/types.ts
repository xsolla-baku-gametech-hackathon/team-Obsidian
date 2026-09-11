import type { Analysis } from '../features/recommendations/GameReport';

export type UserRole = 'game_developer' | 'content_creator';
export type PlanName = 'starter' | 'pro' | 'studio';
export type Page = 'dashboard' | 'analyze' | 'reports' | 'ownership' | 'marketplace' | 'keys' | 'account';

export type Account = {
  id: number;
  email: string;
  display_name: string | null;
  premium_role: UserRole | null;
  subscription_plan: PlanName | null;
  subscription_status: 'inactive' | 'active' | 'pending_youtube_verification';
  youtube_channel_id: string | null;
};

export type AuthSession = { access_token: string; user: Account };

export type ReportSummary = {
  id: number;
  steam_url: string;
  app_id: number;
  game_name: string;
  target_source: string;
  suggested_price_minor: number | null;
  price_currency: string | null;
  release_status: string;
  competitor_count: number;
  created_at: string;
};

export type ReportCollection = { reports: ReportSummary[] };
export type SavedReport = ReportSummary & { payload: Analysis };

export type OwnershipApplication = {
  id: number;
  report_id: number;
  app_id: number;
  game_name: string;
  steam_url: string;
  studio_name: string;
  applicant_name: string;
  applicant_title: string;
  business_email: string;
  company_website_url: string | null;
  official_contact_url: string | null;
  steamworks_proof_url: string | null;
  proof_url: string | null;
  proof_notes: string;
  status: 'pending' | 'approved' | 'rejected';
  reviewed_notes: string | null;
  created_at: string;
  updated_at: string;
};

export type PublishedGame = {
  id: number;
  owner_user_id: number;
  ownership_application_id: number;
  app_id: number;
  game_name: string;
  steam_url: string;
  pitch: string;
  contact_email: string | null;
  created_at: string;
  updated_at: string;
};

export type KeyRequest = {
  id: number;
  game_id: number;
  creator_user_id: number;
  owner_user_id: number;
  message: string;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled';
  created_at: string;
  updated_at: string;
};
