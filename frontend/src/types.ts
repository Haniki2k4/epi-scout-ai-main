export interface DiseaseCase {
  disease_name: string;
  case_count: number;
  location?: string | null;
}

export interface Article {
  id?: number;
  title: string;
  link: string;
  summary: string;
  source: string;
  published_date: string;
  keywords_matched: string;
  is_whitelisted: boolean;
  tags?: string | null;
  event_id?: number | null;
  event_match_score?: number | null;
  dedupe_reason?: string | null;
  cases?: DiseaseCase[];
}

export interface RssSource {
  id?: number;
  url: string;
  label?: string | null;
  category?: string | null;
  is_active: boolean;
  created_at?: string;
}

export interface ScanResult {
  saved_trusted_count: number;
  execution_time?: number;
}

export interface Keyword {
  id?: number;
  text: string;
}

export interface NewsEvent {
  id: number;
  canonical_title: string;
  disease_name: string;
  location?: string | null;
  event_date: string;
  case_count: number;
  severity?: string | null;
  status?: string | null;
  fingerprint: string;
  article_count: number;
  source_count: number;
  sources_preview: string[];
}

export interface NewsEventDetail extends Omit<NewsEvent, "article_count"> {
  article_count: number;
  articles: Article[];
}

export interface ZScoreSpike {
  date: string;
  cases: number;
  rolling_mean: number;
  rolling_std: number;
  z_score: number;
  is_spike: boolean;
}

export interface ProphetForecast {
  date: string;
  actual: number | null;
  forecast: number;
  forecast_lower: number;
  forecast_upper: number;
  is_future: boolean;
}
