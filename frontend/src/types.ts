export interface Article {
  id?: number;
  title: string;
  link: string;
  summary: string;
  source: string;
  published_date: string;
  keywords_matched: string;
  is_whitelisted: boolean;
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
