-- Pegar en Supabase → SQL Editor → Run
create table canales (
  id text primary key,          -- ID de Telegram (-100...)
  nombre text not null,
  fotos boolean not null default false,  -- publica los picks solo en foto
  ultimo_id bigint              -- último mensaje visto; null = empezar desde el siguiente
);
create table picks (
  id bigint generated always as identity primary key,
  canal text not null,
  nombre text not null,
  pick text not null,
  cuota numeric,
  stake numeric,                -- null = no se sabe (resúmenes)
  fecha timestamptz not null default now(),
  res text,                     -- null (pendiente), ganada, perdida, nula, sin resultado
  unidades numeric              -- ganancia que dice el tipster; si es null se calcula con stake y cuota
);
create table kv (k text primary key, v text);
-- Sin políticas: solo la clave secreta (el script) puede leer o escribir.
alter table canales enable row level security;
alter table picks enable row level security;
alter table kv enable row level security;
