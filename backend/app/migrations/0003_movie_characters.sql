-- Add movie_characters table for character analysis from plot beats step.
create table if not exists public.movie_characters (
  character_id text primary key,
  movie_id text not null references public.movies(movie_id) on delete cascade,
  name text not null,
  role text not null,
  analysis text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_movie_characters_movie on public.movie_characters (movie_id);
