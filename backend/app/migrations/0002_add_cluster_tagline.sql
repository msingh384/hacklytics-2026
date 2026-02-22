-- Add tagline column to complaint_clusters for 1-2 word descriptions (generated once, stored in DB)
alter table public.complaint_clusters add column if not exists tagline text;
