export type Category = "breaking" | "business" | "sports" | "movies" | "crime" | "education";

export type Article = {
  id: number;
  title: string;
  summary?: string | null;
  body?: string | null;
  image?: string | null;
  category?: string | null;
  source?: string | null;
  link?: string | null;
  published?: string | null;
  is_original?: boolean;
};

export type ActiveArticle = {
  article: Article;
  section: Category;
  index: number;
};

export type Theme = "light" | "dark";
