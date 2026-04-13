export type Workspace = {
  id: string
  name: string
  owner_id: string
  created_at: string
  role?: 'owner' | 'member'
}

export type ScrapeJob = {
  id: string
  workspace_id: string
  status: 'queued' | 'running' | 'complete' | 'error' | 'cancelled'
  niche_keywords: string[]
  zip_codes: string[]
  radius_miles: number
  min_rating: number | null
  min_reviews: number | null
  exclude_chains: boolean
  two_pass_mode: boolean
  worker_count: number
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  records_found: number
  api_calls_made: number
  estimated_cost_usd: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export type Company = {
  id: string
  name: string
  address?: string | null
  city?: string | null
  state?: string | null
  zip?: string | null
  phone?: string | null
  website?: string | null
  google_maps_url?: string | null
  rating?: number | null
  review_count?: number | null
  primary_category?: string | null
  categories?: string[] | null
  business_status?: string | null
  apollo_enriched_at?: string | null
  companyenrich_enriched_at?: string | null
  lead_score?: number | null
  tags?: string[] | null
  notes?: string | null
  is_archived: boolean
  created_at: string
  contact_count?: number
}

export type Contact = {
  id: string
  first_name?: string | null
  last_name?: string | null
  full_name?: string | null
  title?: string | null
  email?: string | null
  email_status?: string | null
  email_confidence?: number | null
  email_source?: string | null
  phone?: string | null
  linkedin_url?: string | null
  is_primary: boolean
  validated_at?: string | null
}

export type GoogleApiKey = {
  id: string
  name: string
  daily_quota: number
  calls_today: number
  status: 'active' | 'paused' | 'rate-limited' | 'error'
  last_used_at: string | null
  last_error: string | null
  created_at: string
}

export type WorkspaceSettings = {
  workspace_id: string
  validation_provider?: string
  default_title_filters?: string[]
  default_contact_cap?: number
  auto_validate_after_enrich?: boolean
  validation_staleness_days?: number
  slack_webhook_url?: string | null
  // Boolean flags indicating whether a secret is set (never the raw value).
  apollo_api_key_set?: boolean
  companyenrich_api_key_set?: boolean
  email_bison_api_key_set?: boolean
  neverbounce_api_key_set?: boolean
  zerobounce_api_key_set?: boolean
  millionverifier_api_key_set?: boolean
  reoon_api_key_set?: boolean
  anthropic_api_key_set?: boolean
  mxtoolbox_api_key_set?: boolean
}

export type ZipRow = {
  zip: string
  city: string | null
  state_abbr: string | null
  lat: number | null
  lng: number | null
  population: number | null
}
