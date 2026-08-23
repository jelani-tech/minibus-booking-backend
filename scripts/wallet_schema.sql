-- ============================================================================
-- Wallet client — création des tables en production (Supabase)
--
-- Porte-monnaie fermé : dépôt mobile money, paiement de réservation depuis le
-- solde, recrédit à l'annulation. Aucun retrait.
--
--   public.wallets        solde courant, un par client
--   public.wallet_entries registre append-only des mouvements
--   public.wallet_topups  cycle de vie des tentatives de rechargement
--
-- Montants : bigint, en FRANCS ENTIERS. Le XOF n'a pas de subdivision — pas de
-- stockage en centimes. Le ×100 attendu par JEKO et Paystack reste dans le code,
-- à la frontière provider.
--
-- Le script est IDEMPOTENT : il peut être rejoué sans effet de bord.
-- Il produit exactement le même schéma que les révisions Alembic
-- f1a2b3c4d5e6 → a7b8c9d0e1f2 → b3c4d5e6f7a8.
--
-- Exécution :
--   Supabase Studio > SQL Editor > coller ce fichier > Run
--   ou : psql "$DATABASE_URL" -f scripts/wallet_schema.sql
--
-- À exécuter AVANT de passer WALLET_ENABLED=true (§ 12, étape 1 : les tables
-- existent, aucune route n'est exposée, rien ne change pour le client).
-- ============================================================================

begin;

-- gen_random_uuid() : natif sur Supabase, créé ici pour les autres bases.
create extension if not exists pgcrypto;


-- ─────────────────────────────────────────────────────────────────────────────
-- 1. public.wallets — le solde courant
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.wallets (
    id            uuid primary key default gen_random_uuid(),
    -- Un seul wallet par client : cette unicité est la garantie anti-doublon
    -- lors de la création paresseuse (insert … on conflict do nothing).
    customer_id   uuid not null unique references public.customers(id) on delete restrict,
    currency      char(3) not null default 'XOF',
    -- Solde matérialisé, recalculable à tout instant par somme des écritures.
    -- Le check est le dernier rempart contre un solde négatif.
    balance       bigint  not null default 0 check (balance >= 0),
    -- 'frozen' bloque débits et rechargements (fraude, litige) sans effacer
    -- l'historique ; les remboursements restent acceptés.
    status        text    not null default 'active' check (status in ('active','frozen')),
    created_at    timestamptz not null default timezone('utc', now()),
    updated_at    timestamptz not null default timezone('utc', now())
);


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. public.wallet_entries — le registre
--
-- Table APPEND-ONLY : jamais d'update, jamais de delete. Une correction se fait
-- par une écriture inverse de type 'adjustment'.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.wallet_entries (
    id                  uuid primary key default gen_random_uuid(),
    wallet_id           uuid not null references public.wallets(id) on delete restrict,
    -- Le montant est toujours positif : le signe est porté par direction.
    direction           text not null check (direction in ('credit','debit')),
    entry_type          text not null check (entry_type in (
                            'topup','booking_payment','booking_refund',
                            'topup_reversal','adjustment','promo_credit')),
    amount              bigint not null check (amount > 0),
    -- Solde du wallet après application de ce mouvement. Redondant par
    -- construction, et c'est délibéré : il rend le relevé lisible sans agrégat
    -- et permet à l'audit de localiser l'écriture à partir de laquelle un solde
    -- a divergé.
    balance_after       bigint not null,
    reference_type      text check (reference_type in ('topup','booking','payment','manual')),
    reference_id        uuid,
    -- Clé déterministe : topup:{id}, booking_payment:{booking_id},
    -- booking_refund:{payment_id}… La même opération rejouée (webhook redélivré,
    -- callback en course) ne crée jamais deux écritures.
    idempotency_key     text not null unique,
    description         text,
    metadata            jsonb,
    created_at          timestamptz not null default timezone('utc', now())
);

create index if not exists ix_wallet_entries_wallet_created
    on public.wallet_entries (wallet_id, created_at desc);
create index if not exists ix_wallet_entries_reference
    on public.wallet_entries (reference_type, reference_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. public.wallet_topups — les tentatives de rechargement
--
-- Calquée sur public.payments : mêmes colonnes provider, mêmes statuts.
-- wallet_topups est au wallet ce que public.payments est au booking.
-- Cardinalité : N tentatives → 0 ou 1 écriture au registre.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.wallet_topups (
    id                    uuid primary key default gen_random_uuid(),
    wallet_id             uuid not null references public.wallets(id) on delete restrict,
    -- Dénormalisé : filtrage sans jointure et autorisation.
    customer_id           uuid not null references public.customers(id) on delete restrict,
    amount                bigint not null check (amount > 0),
    currency              char(3) not null default 'XOF',
    provider              text not null,                       -- jeko | paystack
    provider_method       text,                                -- wave|orange|mtn|moov|djamo
    -- Référence émise par NOUS, préfixée TU- : c'est ce préfixe qui aiguille un
    -- événement provider vers le crédit du wallet plutôt que vers le règlement
    -- d'une réservation (cf. RF- pour les virements sortants).
    provider_reference    text not null unique,
    provider_payment_url  text,
    status                text not null default 'pending'
                            check (status in ('pending','success','failed','expired')),
    -- Contient provider_payment_id, indispensable à la vérification JEKO au
    -- retour de checkout (leur API ne cherche pas par référence).
    raw_provider_response jsonb,
    credited_at           timestamptz,
    created_at            timestamptz not null default timezone('utc', now()),
    updated_at            timestamptz not null default timezone('utc', now())
);

create index if not exists ix_wallet_topups_customer_created
    on public.wallet_topups (customer_id, created_at desc);
create index if not exists ix_wallet_topups_status
    on public.wallet_topups (status) where status = 'pending';


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Garde-fou : balance_after doit correspondre au solde ± le montant
--
-- Filet de sécurité au cas où un chemin de code futur oublierait de passer par
-- SupabaseWalletRepository.post_entry(). BEFORE INSERT : le trigger s'exécute
-- donc avant la mise à jour de wallets.balance et lit bien le solde d'avant.
-- ─────────────────────────────────────────────────────────────────────────────
create or replace function public.wallet_entry_balance_guard()
returns trigger
language plpgsql
set search_path = public
as $$
declare
    current_balance bigint;
    expected_balance bigint;
begin
    select balance into current_balance
    from public.wallets
    where id = new.wallet_id
    for update;

    if current_balance is null then
        raise exception 'wallet % not found', new.wallet_id;
    end if;

    if new.direction = 'credit' then
        expected_balance := current_balance + new.amount;
    else
        expected_balance := current_balance - new.amount;
    end if;

    if new.balance_after is distinct from expected_balance then
        raise exception
            'wallet_entries.balance_after % does not match expected % '
            '(wallet %, balance %, % of %)',
            new.balance_after, expected_balance, new.wallet_id,
            current_balance, new.direction, new.amount;
    end if;

    if expected_balance < 0 then
        raise exception 'wallet % would go negative (% - %)',
            new.wallet_id, current_balance, new.amount;
    end if;

    return new;
end;
$$;

drop trigger if exists wallet_entry_balance_guard on public.wallet_entries;
create trigger wallet_entry_balance_guard
    before insert on public.wallet_entries
    for each row execute function public.wallet_entry_balance_guard();


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. updated_at automatique, si la base a déjà la fonction set_updated_at()
--    (c'est le cas du schéma existant : partners, vehicles, trips, bookings…).
--    Le code applicatif pose updated_at explicitement à chaque update : ces
--    triggers ne sont qu'une ceinture de plus.
-- ─────────────────────────────────────────────────────────────────────────────
do $$
begin
    if exists (
        select 1 from pg_proc p
        join pg_namespace n on n.oid = p.pronamespace
        where p.proname = 'set_updated_at' and n.nspname = 'public'
    ) then
        drop trigger if exists trg_wallets_updated_at on public.wallets;
        create trigger trg_wallets_updated_at
            before update on public.wallets
            for each row execute function public.set_updated_at();

        drop trigger if exists trg_wallet_topups_updated_at on public.wallet_topups;
        create trigger trg_wallet_topups_updated_at
            before update on public.wallet_topups
            for each row execute function public.set_updated_at();
    else
        raise notice 'set_updated_at() absente : triggers updated_at non créés '
                     '(sans conséquence, le code pose updated_at lui-même)';
    end if;
end
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. RLS — même posture que public.payments : activée, sans policy.
--    Seuls les rôles qui contournent la RLS (service_role, postgres) accèdent
--    aux tables ; l'API passe par le backend, jamais par PostgREST en direct.
-- ─────────────────────────────────────────────────────────────────────────────
alter table public.wallets       enable row level security;
alter table public.wallet_entries enable row level security;
alter table public.wallet_topups  enable row level security;


-- ─────────────────────────────────────────────────────────────────────────────
-- 7. Backfill — un wallet actif par client existant
--
-- Pour que GET /api/wallet réponde sans écriture au premier appel. Rejouable.
-- La création paresseuse côté applicatif reste indispensable : les clients
-- créés après ce script n'y sont pas.
-- ─────────────────────────────────────────────────────────────────────────────
insert into public.wallets (customer_id)
select c.id from public.customers c
on conflict (customer_id) do nothing;


-- ─────────────────────────────────────────────────────────────────────────────
-- 8. Alembic — aligner la version pour que le démarrage de l'app n'ait rien
--    à faire.
--
-- L'app exécute upgrade() au démarrage quand AUTO_UPGRADE_DB=true. Les trois
-- révisions wallet sont écrites en « create … if not exists » : les laisser
-- tourner après ce script est sans danger (elles seraient des no-op). Ce bloc
-- fait simplement sauter l'étape, et UNIQUEMENT si la base est bien à la
-- révision qui précède.
-- ─────────────────────────────────────────────────────────────────────────────
update public.alembic_version
set version_num = 'b3c4d5e6f7a8'
where version_num = 'e39e99f5e548';

commit;


-- ─────────────────────────────────────────────────────────────────────────────
-- Vérification (à lancer après le commit)
-- ─────────────────────────────────────────────────────────────────────────────
-- select table_name from information_schema.tables
--  where table_schema = 'public' and table_name like 'wallet%';
--
-- select (select count(*) from public.customers) as customers,
--        (select count(*) from public.wallets)   as wallets;
--
-- select version_num from public.alembic_version;
--
-- Réconciliation solde / registre (doit ne rien renvoyer) :
-- select w.id, w.balance,
--        coalesce(sum(case when e.direction = 'credit' then e.amount
--                          else -e.amount end), 0) as computed
--   from public.wallets w
--   left join public.wallet_entries e on e.wallet_id = w.id
--  group by w.id, w.balance
-- having w.balance <> coalesce(sum(case when e.direction = 'credit' then e.amount
--                                       else -e.amount end), 0);
