-- Comptes du site « Portefeuille » (Supabase). À coller une seule fois dans SQL Editor → Run.
-- Principe : pseudo + code à 4 chiffres. Les données sont chiffrées sur le téléphone (AES-256) avant l'envoi :
-- la base ne voit jamais un achat en clair. Personne ne peut lire ni modifier les tables directement :
-- tout passe par les fonctions ci-dessous, qui vérifient le code (haché bcrypt) ou un jeton de session (haché SHA-256),
-- et bloquent le compte après 5 codes faux (15 min, puis de plus en plus longtemps).

create extension if not exists pgcrypto with schema extensions;

create table if not exists public.comptes (
  pseudo_cle    text primary key check (char_length(pseudo_cle) between 1 and 24),
  pseudo        text not null,
  pin_hash      text not null,
  sel           text not null,
  donnees       text,
  version       bigint not null default 0,
  maj           timestamptz not null default now(),
  echecs        int not null default 0,
  bloque_jusqua timestamptz,
  cree          timestamptz not null default now()
);
create table if not exists public.sessions (
  jeton_hash text primary key,
  pseudo_cle text not null references public.comptes(pseudo_cle) on delete cascade,
  cree       timestamptz not null default now(),
  vu         timestamptz not null default now()
);
alter table public.comptes  enable row level security;
alter table public.sessions enable row level security;
revoke all on public.comptes, public.sessions from anon, authenticated;

create or replace function public._session(p_pseudo text, p_jeton text) returns text
language plpgsql security definer set search_path = public, extensions as $$
declare k text := lower(trim(p_pseudo));
begin
  if p_jeton is null or length(p_jeton) <> 64 then return null; end if;
  update sessions set vu = now() where jeton_hash = encode(digest(p_jeton, 'sha256'), 'hex') and pseudo_cle = k;
  if found then return k; end if;
  return null;
end $$;

create or replace function public._nouvelle_session(k text) returns text
language plpgsql security definer set search_path = public, extensions as $$
declare j text := encode(gen_random_bytes(32), 'hex');
begin
  insert into sessions(jeton_hash, pseudo_cle) values (encode(digest(j, 'sha256'), 'hex'), k);
  delete from sessions where pseudo_cle = k and jeton_hash not in (select jeton_hash from sessions where pseudo_cle = k order by vu desc limit 10);
  return j;
end $$;

create or replace function public.creer_compte(p_pseudo text, p_pin text) returns json
language plpgsql security definer set search_path = public, extensions as $$
declare k text := lower(trim(p_pseudo)); s text;
begin
  if k is null or char_length(k) < 1 or char_length(k) > 24 then return json_build_object('ok', false, 'erreur', 'pseudo'); end if;
  if p_pin !~ '^[0-9]{4}$' then return json_build_object('ok', false, 'erreur', 'code'); end if;
  if exists (select 1 from comptes where pseudo_cle = k) then return json_build_object('ok', false, 'erreur', 'existe'); end if;
  perform pg_sleep(0.4);
  s := encode(gen_random_bytes(16), 'base64');
  insert into comptes(pseudo_cle, pseudo, pin_hash, sel) values (k, trim(p_pseudo), crypt(p_pin, gen_salt('bf', 10)), s);
  return json_build_object('ok', true, 'jeton', _nouvelle_session(k), 'sel', s, 'version', 0);
end $$;

create or replace function public.connexion(p_pseudo text, p_pin text) returns json
language plpgsql security definer set search_path = public, extensions as $$
declare k text := lower(trim(p_pseudo)); c comptes%rowtype; e int;
begin
  perform pg_sleep(0.5);  -- ralentit les essais à la chaîne
  select * into c from comptes where pseudo_cle = k for update;
  if not found then return json_build_object('ok', false, 'erreur', 'inconnu'); end if;
  if c.bloque_jusqua is not null and c.bloque_jusqua > now() then
    return json_build_object('ok', false, 'erreur', 'bloque', 'attente', ceil(extract(epoch from c.bloque_jusqua - now())));
  end if;
  if p_pin ~ '^[0-9]{4}$' and crypt(p_pin, c.pin_hash) = c.pin_hash then
    update comptes set echecs = 0, bloque_jusqua = null where pseudo_cle = k;
    return json_build_object('ok', true, 'jeton', _nouvelle_session(k), 'sel', c.sel, 'donnees', c.donnees, 'version', c.version, 'maj', c.maj, 'pseudo', c.pseudo);
  end if;
  e := c.echecs + 1;
  update comptes set echecs = e,
    bloque_jusqua = case when e >= 5 then now() + least(interval '24 hours', interval '15 minutes' * power(2, e - 5)) else null end
  where pseudo_cle = k;
  return json_build_object('ok', false, 'erreur', case when e >= 5 then 'bloque' else 'code' end, 'restants', greatest(0, 5 - e),
                           'attente', case when e >= 5 then extract(epoch from least(interval '24 hours', interval '15 minutes' * power(2, e - 5))) else null end);
end $$;

create or replace function public.charger(p_pseudo text, p_jeton text) returns json
language plpgsql security definer set search_path = public, extensions as $$
declare k text := _session(p_pseudo, p_jeton); c comptes%rowtype;
begin
  if k is null then return json_build_object('ok', false, 'erreur', 'session'); end if;
  select * into c from comptes where pseudo_cle = k;
  return json_build_object('ok', true, 'donnees', c.donnees, 'version', c.version, 'maj', c.maj);
end $$;

create or replace function public.enregistrer(p_pseudo text, p_jeton text, p_donnees text, p_version bigint) returns json
language plpgsql security definer set search_path = public, extensions as $$
declare k text := _session(p_pseudo, p_jeton); v bigint;
begin
  if k is null then return json_build_object('ok', false, 'erreur', 'session'); end if;
  if p_donnees is null or length(p_donnees) > 3000000 then return json_build_object('ok', false, 'erreur', 'taille'); end if;
  select version into v from comptes where pseudo_cle = k for update;
  if p_version is not null and p_version < v then
    return json_build_object('ok', false, 'erreur', 'conflit', 'version', v);
  end if;
  update comptes set donnees = p_donnees, version = v + 1, maj = now() where pseudo_cle = k;
  return json_build_object('ok', true, 'version', v + 1);
end $$;

create or replace function public.changer_code(p_pseudo text, p_jeton text, p_ancien text, p_nouveau text, p_donnees text, p_sel text) returns json
language plpgsql security definer set search_path = public, extensions as $$
declare k text := _session(p_pseudo, p_jeton); c comptes%rowtype; s text := p_sel;
begin
  if k is null then return json_build_object('ok', false, 'erreur', 'session'); end if;
  if p_nouveau !~ '^[0-9]{4}$' or s is null or length(s) < 16 then return json_build_object('ok', false, 'erreur', 'code'); end if;
  perform pg_sleep(0.5);
  select * into c from comptes where pseudo_cle = k for update;
  if crypt(p_ancien, c.pin_hash) <> c.pin_hash then return json_build_object('ok', false, 'erreur', 'ancien'); end if;
  update comptes set pin_hash = crypt(p_nouveau, gen_salt('bf', 10)), sel = s, donnees = p_donnees, version = c.version + 1, maj = now() where pseudo_cle = k;
  delete from sessions where pseudo_cle = k;  -- tous les appareils doivent se reconnecter
  return json_build_object('ok', true, 'jeton', _nouvelle_session(k), 'sel', s, 'version', c.version + 1);
end $$;

create or replace function public.deconnexion(p_pseudo text, p_jeton text) returns json
language plpgsql security definer set search_path = public, extensions as $$
begin
  delete from sessions where jeton_hash = encode(digest(coalesce(p_jeton, ''), 'sha256'), 'hex') and pseudo_cle = lower(trim(p_pseudo));
  return json_build_object('ok', true);
end $$;

create or replace function public.supprimer_compte(p_pseudo text, p_jeton text, p_pin text) returns json
language plpgsql security definer set search_path = public, extensions as $$
declare k text := _session(p_pseudo, p_jeton); c comptes%rowtype;
begin
  if k is null then return json_build_object('ok', false, 'erreur', 'session'); end if;
  perform pg_sleep(0.5);
  select * into c from comptes where pseudo_cle = k;
  if crypt(p_pin, c.pin_hash) <> c.pin_hash then return json_build_object('ok', false, 'erreur', 'code'); end if;
  delete from comptes where pseudo_cle = k;
  return json_build_object('ok', true);
end $$;

revoke all on function public._session(text, text), public._nouvelle_session(text) from public, anon, authenticated;
grant execute on function public.creer_compte(text, text), public.connexion(text, text), public.charger(text, text),
  public.enregistrer(text, text, text, bigint), public.changer_code(text, text, text, text, text, text),
  public.deconnexion(text, text), public.supprimer_compte(text, text, text) to anon;
