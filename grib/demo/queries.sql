SELECT date_trunc('hour', created_at) AS time, COUNT(*) AS orders
FROM orders
WHERE created_at >= $from AND created_at < $to
GROUP BY 1 ORDER BY 1;

SELECT strftime('%Y-%m-%d %H:00:00', created_at) AS time, COUNT(*) AS orders
FROM orders
WHERE created_at >= $from AND created_at < $to
GROUP BY 1 ORDER BY 1;

SELECT region, SUM(amount) AS revenue
FROM orders
WHERE created_at >= $from AND created_at < $to
GROUP BY region ORDER BY revenue DESC;

SELECT name, size FROM queue_state;

SELECT users FROM online_users WHERE id = 1;
