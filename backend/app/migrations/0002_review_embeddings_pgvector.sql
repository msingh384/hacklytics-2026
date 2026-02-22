-- Enable pgvector and create review_embeddings table for Supabase vector store.
-- Run in Supabase SQL editor. Enable "vector" extension in Dashboard first if needed.

begin;

create extension if not exists vector;

create table if not exists public.review_embeddings (
  id bigserial primary key,
  movie_id text not null,
  chunk_id text not null unique,
  text text not null,
  source text not null default 'user',
  embedding vector(384) not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_review_embeddings_movie on public.review_embeddings (movie_id);
create index if not exists idx_review_embeddings_hnsw on public.review_embeddings
  using hnsw (embedding vector_cosine_ops);

-- RPC for similarity search (cosine distance, normalized embeddings)
create or replace function public.match_review_embeddings(
  query_embedding vector(384),
  p_movie_id text,
  match_count int default 10
)
returns table (
  chunk_id text,
  text text,
  source text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    re.chunk_id,
    re.text,
    re.source,
    1 - (re.embedding <=> query_embedding) as similarity
  from public.review_embeddings re
  where re.movie_id = p_movie_id
  order by re.embedding <=> query_embedding
  limit match_count;
end;
$$;

commit;
