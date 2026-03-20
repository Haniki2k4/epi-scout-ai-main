export interface Article {
  id?: number;
  title: string;
  link: string;
  summary: string;
  source: string;
  published_date: string;
  keywords_matched: string;
  is_whitelisted: boolean;
  event_id?: number | null;
  event_match_score?: number | null;
  dedupe_reason?: string | null;
}

export interface WhitelistDomain {
  id?: number;
  domain: string;
  is_active: boolean;
}

export interface ScanResult {
  saved_trusted_count: number;
  unknown_articles: Article[];
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
