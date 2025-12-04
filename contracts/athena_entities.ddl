-- Athena external table for entities extracted by ETL (JSON Lines)

CREATE EXTERNAL TABLE IF NOT EXISTS analytics_entities (
  note_id       string,
  run_id        string,
  entity_type   string,
  text          string,
  norm_text     string,
  begin         int,
  end           int,
  score         double,
  section       string
)
PARTITIONED BY (run string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://REPLACE_ME/enriched/entities/';

