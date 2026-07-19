export type Category = "breaking" | "business" | "sports" | "movies" | "crime";

export type Article = {
  id: number;
  title: string;
  summary?: string | null;
  ai_summary?: string | null;
  image?: string | null;
  category?: string | null;
  source?: string | null;
  link?: string | null;
  published?: string | null;
};

export type ActiveArticle = {
  article: Article;
  section: Category;
  index: number;
};

export type Theme = "light" | "dark";
