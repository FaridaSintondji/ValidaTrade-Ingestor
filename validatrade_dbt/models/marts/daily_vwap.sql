-- ============================================================
-- daily_vwap.sql
-- Mart : prix moyen pondere par les volumes (VWAP) par jour et symbole.
--
-- VWAP = sum(price * amount) / sum(amount)
-- Une ligne par couple (symbol, trade_date).
-- ============================================================

with staged_trades as (

    select * from {{ ref('stg_trades') }}

),

daily_aggregates as (

    select
        symbol,
        trade_date,
        count(*)                            as nb_trades,
        sum(amount)                         as total_volume,
        sum(price * amount)                 as total_value,
        sum(price * amount) / sum(amount)   as vwap
    from staged_trades
    group by symbol, trade_date

)

select * from daily_aggregates