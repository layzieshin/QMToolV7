-- Persistent marker proving this is the J04-M0 destructive test cluster.
-- Guarded live fixtures refuse to run without this exact marker.

CREATE TABLE IF NOT EXISTS public.qmtool_j04_test_cluster_marker (
    marker_key text PRIMARY KEY,
    marker_value text NOT NULL
);

INSERT INTO public.qmtool_j04_test_cluster_marker (marker_key, marker_value)
VALUES ('cluster_id', 'j04_m0_destructive_pg16')
ON CONFLICT (marker_key) DO UPDATE
SET marker_value = EXCLUDED.marker_value;
