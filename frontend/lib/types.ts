export type RobotVersion = {
  id: string;
  robot_id: string;
  version: string;
  channel: "stable" | "beta" | "hotfix";
  artifact_type: "ZIP" | "EXE";
  artifact_path: string | null;
  artifact_sha256: string | null;
  changelog: string | null;
  commit_sha: string | null;
  branch: string | null;
  build_url: string | null;
  created_source: string;
  required_env_keys_json: string[];
  entrypoint_type: "PYTHON" | "EXE";
  entrypoint_path: string;
  arguments: string[];
  env_vars: Record<string, string>;
  working_directory: string | null;
  checksum: string | null;
  created_by: string | null;
  created_at: string;
  is_active: boolean;
};

export type Robot = {
  id: string;
  name: string;
  description: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
  versions: RobotVersion[];
};

export type RobotListResponse = {
  items: Robot[];
  total: number;
};

export type RunArtifact = {
  id: string;
  run_id: string;
  artifact_name: string;
  file_path: string;
  file_size_bytes: number;
  content_type: string | null;
  created_at: string;
};

export type RunVersionSummary = {
  id: string;
  version: string;
  channel: "stable" | "beta" | "hotfix";
  artifact_type: "ZIP" | "EXE";
  artifact_sha256: string | null;
};

export type RunServiceSummary = {
  id: string;
  title: string;
};

export type Run = {
  run_id: string;
  robot_id: string;
  robot_version_id: string;
  service_id: string | null;
  schedule_id: string | null;
  trigger_type: "MANUAL" | "SCHEDULED" | "RETRY";
  attempt: number;
  parameters_json: Record<string, unknown> | null;
  status: "PENDING" | "RUNNING" | "SUCCESS" | "FAILED" | "CANCELED";
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  triggered_by: string | null;
  error_message: string | null;
  host_name: string | null;
  process_id: number | null;
  env_name: "PROD" | "HML" | "TEST";
  cancel_requested: boolean;
  canceled_at: string | null;
  canceled_by: string | null;
  robot_version: RunVersionSummary | null;
  service: RunServiceSummary | null;
  artifacts: RunArtifact[];
};

export type RunListResponse = {
  items: Run[];
  total: number;
};

export type RunLog = {
  id: number;
  run_id: string;
  timestamp: string;
  level: string;
  message: string;
};

export type ExecuteRunRequest = {
  version_id?: string;
  robot_version_id?: string;
  runtime_arguments: string[];
  runtime_env: Record<string, string>;
  env_name?: "PROD" | "HML" | "TEST";
};

export type Domain = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  created_at: string;
};

export type Service = {
  id: string;
  domain_id: string;
  robot_id: string;
  title: string;
  description: string | null;
  icon: string | null;
  enabled: boolean;
  default_version_id: string | null;
  form_schema_json: Record<string, unknown>;
  run_template_json: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type ServiceRunRequest = {
  parameters: Record<string, unknown>;
};

export type Schedule = {
  id: string;
  robot_id: string;
  enabled: boolean;
  cron_expr: string;
  timezone: string;
  window_start: string | null;
  window_end: string | null;
  max_concurrency: number;
  timeout_seconds: number;
  retry_count: number;
  retry_backoff_seconds: number;
  created_by: string | null;
  created_at: string;
};

export type SlaRule = {
  id: string;
  robot_id: string;
  expected_run_every_minutes: number | null;
  expected_daily_time: string | null;
  late_after_minutes: number;
  alert_on_failure: boolean;
  alert_on_late: boolean;
  notify_channels_json: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type AlertEvent = {
  id: string;
  robot_id: string;
  run_id: string | null;
  type: "LATE" | "FAILURE_STREAK" | "WORKER_DOWN" | "QUEUE_BACKLOG";
  severity: "INFO" | "WARN" | "CRITICAL";
  message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  resolved_at: string | null;
};

export type Worker = {
  id: string;
  hostname: string;
  status: "RUNNING" | "PAUSED" | "STOPPED";
  last_heartbeat: string;
  version: string | null;
  created_at: string;
};

export type OpsStatus = {
  total_workers: number;
  workers_running: number;
  workers_paused: number;
  queue_depth: number;
  runs_running: number;
  runs_failed_last_hour: number;
  uptime_seconds: number;
};

export type RobotEnvVar = {
  robot_id: string;
  env_name: "PROD" | "HML" | "TEST";
  key: string;
  is_secret: boolean;
  is_set: boolean;
  value: string | null;
  created_at: string;
  updated_at: string;
};

export type RobotEnvVarUpsertItem = {
  key: string;
  value: string;
  is_secret: boolean;
};
