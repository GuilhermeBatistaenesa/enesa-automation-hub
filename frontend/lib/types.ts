export type RobotVersion = {
  id: string;
  robot_id: string;
  version: string;
  channel: "stable" | "beta" | "hotfix";
  artifact_type: "ZIP" | "EXE";
  artifact_path: string | null;
  artifact_sha256: string | null;
  changelog: string | null;
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
  parameters_json: Record<string, unknown> | null;
  status: "PENDING" | "RUNNING" | "SUCCESS" | "FAILED";
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  triggered_by: string | null;
  error_message: string | null;
  host_name: string | null;
  process_id: number | null;
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
