-- db/partitions.sql
-- Create partitions for a date range (example: a month)
DO $$
DECLARE
  d DATE := DATE '2026-01-01';
  end_d DATE := DATE '2026-02-01';
  part_name TEXT;
BEGIN
  WHILE d < end_d LOOP
    part_name := format('messages_%s', to_char(d, 'YYYY_MM_DD'));

    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS %I PARTITION OF messages FOR VALUES FROM (%L) TO (%L);',
      part_name,
      d::timestamptz,
      (d + 1)::timestamptz
    );

    -- Indexes per partition
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (org_id, ts DESC);',
      part_name || '_org_ts_idx', part_name);

    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (org_id, user_id, ts DESC);',
      part_name || '_org_user_ts_idx', part_name);

    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (org_id, source_type, ts DESC);',
      part_name || '_org_source_ts_idx', part_name);

    d := d + 1;
  END LOOP;
END $$;

