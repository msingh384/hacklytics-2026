-- DirectorsCut MVP schema migration
-- Run this in Supabase SQL editor.

begin;

-- Baseline source tables (create if this is a fresh DB).
create table if not exists public.user_reviews (
  id bigserial primary key,
  movie_id text not null,
  movie_title text,
  movie_review text not null,
  rating numeric,
  review_id text,
  created_at timestamptz not null default now()
);

create table if not exists public.critic_reviews (
  id bigserial primary key,
  imdb_id text,
  title text,
  review_content text not null,
  rating numeric,
  critic_name text,
  created_at timestamptz not null default now()
);

create table if not exists public.movies (
  movie_id text primary key,
  title text not null,
  year text,
  genre text,
  poster text,
  imdb_rating numeric,
  rotten_tomatoes text,
  audience_score text,
  plot text,
  expanded_plot text,
  omdb_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.plot_summary (
  movie_id text primary key references public.movies(movie_id) on delete cascade,
  plot_text text not null,
  source_page text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.plot_beats (
  beat_id bigserial primary key,
  movie_id text not null references public.movies(movie_id) on delete cascade,
  beat_order integer not null,
  label text not null,
  beat_text text not null,
  created_at timestamptz not null default now(),
  unique (movie_id, beat_order)
);

create table if not exists public.complaint_clusters (
  cluster_id text primary key,
  movie_id text not null references public.movies(movie_id) on delete cascade,
  label text not null,
  summary text,
  review_count integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.cluster_examples (
  example_id text primary key,
  movie_id text not null references public.movies(movie_id) on delete cascade,
  cluster_id text not null references public.complaint_clusters(cluster_id) on delete cascade,
  review_text text not null,
  source text not null check (source in ('user', 'critic')),
  review_reference text,
  created_at timestamptz not null default now()
);

create table if not exists public.what_if_suggestions (
  suggestion_id text primary key,
  movie_id text not null references public.movies(movie_id) on delete cascade,
  text text not null,
  linked_cluster_ids text[] not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists public.generations (
  generation_id text primary key,
  movie_id text not null references public.movies(movie_id) on delete cascade,
  movie_title text,
  session_id text not null,
  story_session_id text not null,
  ending_text text not null,
  story_payload jsonb not null default '{}'::jsonb,
  score_payload jsonb not null default '{}'::jsonb,
  score_total integer not null default 0,
  votes integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.votes (
  vote_id text primary key,
  generation_id text not null references public.generations(generation_id) on delete cascade,
  session_id text not null,
  value integer not null check (value in (-1, 1)),
  created_at timestamptz not null default now(),
  unique (generation_id, session_id)
);

create index if not exists idx_movies_title on public.movies (title);
create index if not exists idx_movies_genre on public.movies (genre);
create index if not exists idx_plot_beats_movie on public.plot_beats (movie_id);
create index if not exists idx_clusters_movie on public.complaint_clusters (movie_id);
create index if not exists idx_examples_movie on public.cluster_examples (movie_id);
create index if not exists idx_whatif_movie on public.what_if_suggestions (movie_id);
create index if not exists idx_generations_movie on public.generations (movie_id);
create index if not exists idx_generations_votes on public.generations (votes desc);
create index if not exists idx_votes_generation on public.votes (generation_id);

-- Helps dedupe scraper writes if user_reviews already has these columns.
alter table public.user_reviews add column if not exists review_id text;
create index if not exists idx_user_reviews_movie_review_id on public.user_reviews (movie_id, review_id) where review_id is not null;

-- Optional lookup acceleration for pre-existing critic table.
create index if not exists idx_critic_reviews_imdb_id on public.critic_reviews (imdb_id);
create index if not exists idx_critic_reviews_title on public.critic_reviews (lower(title));

commit;
