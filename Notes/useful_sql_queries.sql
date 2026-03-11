-- Useful SQL Queries for Zombie Game Analysis in pgAdmin

-- ============================================
-- GAME OVERVIEW
-- ============================================

-- View all games
SELECT 
    game_id,
    grid_size,
    round_num,
    status,
    created_at,
    ended_at,
    EXTRACT(EPOCH FROM (ended_at - created_at)) as duration_seconds
FROM game_sessions
ORDER BY created_at DESC;

-- ============================================
-- AGENT STATISTICS
-- ============================================

-- Agent distribution by game
SELECT 
    game_id,
    agent_type,
    role_name,
    COUNT(*) as count
FROM agents
GROUP BY game_id, agent_type, role_name
ORDER BY game_id, agent_type;

-- Survival rate by agent type for a specific game
SELECT 
    agent_type,
    COUNT(*) as total,
    SUM(CASE WHEN is_alive THEN 1 ELSE 0 END) as survived,
    ROUND(100.0 * SUM(CASE WHEN is_alive THEN 1 ELSE 0 END) / COUNT(*), 2) as survival_rate
FROM agents
WHERE game_id = 1  -- Change game_id as needed
GROUP BY agent_type;

-- Role effectiveness analysis
SELECT 
    role_name,
    COUNT(*) as agents,
    AVG(health)::INTEGER as avg_health,
    SUM(CASE WHEN is_alive THEN 1 ELSE 0 END) as alive,
    ROUND(100.0 * SUM(CASE WHEN is_alive THEN 1 ELSE 0 END) / COUNT(*), 2) as survival_rate
FROM agents
WHERE game_id = 1 AND role_name IS NOT NULL
GROUP BY role_name;

-- Agent positions at end of game (useful for visualization)
SELECT 
    agent_id,
    name,
    agent_type,
    role_name,
    x,
    y,
    health,
    is_alive
FROM agents
WHERE game_id = 1
ORDER BY agent_type, name;

-- ============================================
-- COMBAT STATISTICS
-- ============================================

-- Combat overview by game
SELECT 
    game_id,
    COUNT(*) as total_attacks,
    SUM(damage) as total_damage,
    AVG(damage)::INTEGER as avg_damage,
    MAX(damage) as max_damage,
    MIN(damage) as min_damage,
    SUM(CASE WHEN was_critical THEN 1 ELSE 0 END) as critical_hits,
    ROUND(100.0 * SUM(CASE WHEN was_critical THEN 1 ELSE 0 END) / COUNT(*), 2) as crit_rate
FROM combat_log
GROUP BY game_id
ORDER BY game_id;

-- Top attackers in a specific game
SELECT 
    a.name,
    a.agent_type,
    a.role_name,
    COUNT(*) as attacks,
    SUM(cl.damage) as total_damage,
    AVG(cl.damage)::INTEGER as avg_damage,
    MAX(cl.damage) as max_damage,
    SUM(CASE WHEN cl.was_critical THEN 1 ELSE 0 END) as crits
FROM combat_log cl
JOIN agents a ON cl.attacker_id = a.agent_id
WHERE cl.game_id = 1
GROUP BY a.agent_id, a.name, a.agent_type, a.role_name
ORDER BY total_damage DESC
LIMIT 10;

-- Most attacked agents
SELECT 
    a.name,
    a.agent_type,
    a.role_name,
    COUNT(*) as times_attacked,
    SUM(cl.damage) as total_damage_taken,
    AVG(cl.damage)::INTEGER as avg_damage_taken
FROM combat_log cl
JOIN agents a ON cl.target_id = a.agent_id
WHERE cl.game_id = 1
GROUP BY a.agent_id, a.name, a.agent_type, a.role_name
ORDER BY total_damage_taken DESC
LIMIT 10;

-- Round-by-round combat progression
SELECT 
    round_num,
    COUNT(*) as attacks_this_round,
    SUM(damage) as damage_this_round,
    AVG(damage)::INTEGER as avg_damage,
    SUM(CASE WHEN was_critical THEN 1 ELSE 0 END) as crits_this_round
FROM combat_log
WHERE game_id = 1
GROUP BY round_num
ORDER BY round_num;

-- Combat history with attacker and target names
SELECT 
    cl.round_num,
    a1.name as attacker,
    a1.agent_type as attacker_type,
    a2.name as target,
    a2.agent_type as target_type,
    cl.damage,
    cl.was_critical,
    cl.timestamp
FROM combat_log cl
JOIN agents a1 ON cl.attacker_id = a1.agent_id
JOIN agents a2 ON cl.target_id = a2.agent_id
WHERE cl.game_id = 1
ORDER BY cl.timestamp DESC
LIMIT 50;

-- ============================================
-- ITEM STATISTICS
-- ============================================

-- Item pickup analysis
SELECT 
    i.item_type,
    COUNT(*) as spawned,
    SUM(CASE WHEN i.picked_up THEN 1 ELSE 0 END) as picked_up,
    ARRAY_AGG(a.name) FILTER (WHERE i.picked_up) as picked_by
FROM items i
LEFT JOIN agents a ON i.picked_by_agent_id = a.agent_id
WHERE i.game_id = 1
GROUP BY i.item_type;

-- Items still available in game
SELECT 
    item_id,
    item_type,
    x,
    y
FROM items
WHERE game_id = 1 AND picked_up = FALSE;

-- ============================================
-- PERFORMANCE QUERIES
-- ============================================

-- Database size monitoring
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY size_bytes DESC;

-- Table row counts
SELECT 
    'game_sessions' as table_name, COUNT(*) as rows FROM game_sessions
UNION ALL
SELECT 'agents', COUNT(*) FROM agents
UNION ALL
SELECT 'items', COUNT(*) FROM items
UNION ALL
SELECT 'combat_log', COUNT(*) FROM combat_log;

-- Index usage statistics
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as number_of_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- ============================================
-- MAINTENANCE QUERIES
-- ============================================

-- Clean up old test games (older than 7 days)
DELETE FROM game_sessions 
WHERE created_at < NOW() - INTERVAL '7 days'
AND status != 'active';

-- Clean up specific game
DELETE FROM game_sessions WHERE game_id = 1;

-- Reset auto-increment counters (use with caution!)
-- ALTER SEQUENCE game_sessions_game_id_seq RESTART WITH 1;
-- ALTER SEQUENCE agents_agent_id_seq RESTART WITH 1;
-- ALTER SEQUENCE items_item_id_seq RESTART WITH 1;
-- ALTER SEQUENCE combat_log_log_id_seq RESTART WITH 1;

-- Vacuum tables to reclaim space
VACUUM ANALYZE game_sessions;
VACUUM ANALYZE agents;
VACUUM ANALYZE items;
VACUUM ANALYZE combat_log;

-- ============================================
-- ADVANCED ANALYTICS
-- ============================================

-- Win rate by first item pickup
WITH first_pickups AS (
    SELECT 
        i.game_id,
        i.item_type,
        a.agent_type,
        MIN(cl.timestamp) as first_pickup_time
    FROM items i
    JOIN agents a ON i.picked_by_agent_id = a.agent_id
    JOIN combat_log cl ON cl.game_id = i.game_id
    WHERE i.picked_up = TRUE
    GROUP BY i.game_id, i.item_type, a.agent_type
),
game_winners AS (
    SELECT 
        game_id,
        CASE 
            WHEN SUM(CASE WHEN agent_type = 'Human' AND is_alive THEN 1 ELSE 0 END) > 
                 SUM(CASE WHEN agent_type = 'Zombie' AND is_alive THEN 1 ELSE 0 END) 
            THEN 'Human'
            ELSE 'Zombie'
        END as winner
    FROM agents
    GROUP BY game_id
)
SELECT 
    fp.item_type,
    gw.winner,
    COUNT(*) as games
FROM first_pickups fp
JOIN game_winners gw ON fp.game_id = gw.game_id
GROUP BY fp.item_type, gw.winner
ORDER BY fp.item_type, gw.winner;

-- Average game duration by grid size
SELECT 
    grid_size,
    COUNT(*) as games,
    AVG(round_num) as avg_rounds,
    AVG(EXTRACT(EPOCH FROM (ended_at - created_at))) as avg_duration_seconds
FROM game_sessions
WHERE ended_at IS NOT NULL
GROUP BY grid_size
ORDER BY grid_size;

-- Agent kill/death ratios
WITH kill_counts AS (
    SELECT 
        attacker_id,
        COUNT(DISTINCT target_id) as kills
    FROM combat_log cl
    JOIN agents a ON cl.target_id = a.agent_id
    WHERE a.is_alive = FALSE AND cl.game_id = 1
    GROUP BY attacker_id
)
SELECT 
    a.name,
    a.agent_type,
    a.role_name,
    COALESCE(kc.kills, 0) as kills,
    CASE WHEN a.is_alive THEN 0 ELSE 1 END as deaths,
    CASE 
        WHEN a.is_alive THEN COALESCE(kc.kills, 0)
        ELSE ROUND(COALESCE(kc.kills, 0)::NUMERIC / 1, 2)
    END as kd_ratio
FROM agents a
LEFT JOIN kill_counts kc ON a.agent_id = kc.attacker_id
WHERE a.game_id = 1
ORDER BY kd_ratio DESC, kills DESC;
