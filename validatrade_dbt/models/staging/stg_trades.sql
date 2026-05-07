-- ============================================================
-- stg_trades.sql
-- Staging model pour les trades crypto.
--
-- Transformations legeres uniquement :
--   - Lecture depuis la source brute
--   - Renommage de timestamp en traded_at (plus explicite)
--   - Derivation de trade_date pour le partitionnement aval
--   - Ajout d'une colonne d'audit _staged_at
--
-- Pas de jointure, pas d'agregation, pas de business logic ici.
-- ============================================================

with raw_trades as (
    select * from {{source('validatrade_raw', 'trades')}}
),

cleaned as (
    select
        symbol,
        price,
        amount,
        total_value,
        platform,
        timestamp as traded_at,
        date(timestamp) as trade_date,
        current_timestamp() as _staged_at
    from raw_trades 
)

select * from cleaned