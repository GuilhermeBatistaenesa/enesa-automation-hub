-- Enesa Automation Hub - Corporate Scheduler + SLA/Alerts

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;

IF OBJECT_ID('dbo.schedules', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.schedules (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        robot_id UNIQUEIDENTIFIER NOT NULL,
        enabled BIT NOT NULL DEFAULT 1,
        cron_expr NVARCHAR(120) NOT NULL,
        timezone NVARCHAR(80) NOT NULL DEFAULT 'America/Sao_Paulo',
        window_start NVARCHAR(5) NULL,
        window_end NVARCHAR(5) NULL,
        max_concurrency INT NOT NULL DEFAULT 1,
        timeout_seconds INT NOT NULL DEFAULT 3600,
        retry_count INT NOT NULL DEFAULT 0,
        retry_backoff_seconds INT NOT NULL DEFAULT 60,
        created_by UNIQUEIDENTIFIER NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        CONSTRAINT FK_schedules_robots FOREIGN KEY (robot_id) REFERENCES dbo.robots(id) ON DELETE CASCADE,
        CONSTRAINT FK_schedules_users FOREIGN KEY (created_by) REFERENCES dbo.users(id),
        CONSTRAINT UQ_schedules_robot_id UNIQUE (robot_id)
    );
    CREATE INDEX IX_schedules_enabled ON dbo.schedules(enabled);
END;
GO

IF COL_LENGTH('dbo.runs', 'trigger_type') IS NULL
BEGIN
    ALTER TABLE dbo.runs
    ADD trigger_type NVARCHAR(20) NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'attempt') IS NULL
BEGIN
    ALTER TABLE dbo.runs
    ADD attempt INT NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'schedule_id') IS NULL
BEGIN
    ALTER TABLE dbo.runs
    ADD schedule_id UNIQUEIDENTIFIER NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'trigger_type') IS NOT NULL
BEGIN
    UPDATE dbo.runs
    SET trigger_type = COALESCE(trigger_type, 'MANUAL');
END;
GO

IF COL_LENGTH('dbo.runs', 'attempt') IS NOT NULL
BEGIN
    UPDATE dbo.runs
    SET attempt = COALESCE(attempt, 1);
END;
GO

IF COL_LENGTH('dbo.runs', 'trigger_type') IS NOT NULL
BEGIN
    ALTER TABLE dbo.runs ALTER COLUMN trigger_type NVARCHAR(20) NOT NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'attempt') IS NOT NULL
BEGIN
    ALTER TABLE dbo.runs ALTER COLUMN attempt INT NOT NULL;
END;
GO

IF OBJECT_ID('DF_runs_trigger_type', 'D') IS NULL
BEGIN
    ALTER TABLE dbo.runs ADD CONSTRAINT DF_runs_trigger_type DEFAULT 'MANUAL' FOR trigger_type;
END;
GO

IF OBJECT_ID('DF_runs_attempt', 'D') IS NULL
BEGIN
    ALTER TABLE dbo.runs ADD CONSTRAINT DF_runs_attempt DEFAULT 1 FOR attempt;
END;
GO

IF COL_LENGTH('dbo.runs', 'schedule_id') IS NOT NULL
AND NOT EXISTS (
    SELECT 1
    FROM sys.foreign_keys
    WHERE name = 'FK_runs_schedules'
      AND parent_object_id = OBJECT_ID('dbo.runs')
)
BEGIN
    ALTER TABLE dbo.runs
    ADD CONSTRAINT FK_runs_schedules FOREIGN KEY (schedule_id) REFERENCES dbo.schedules(id);
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_runs_trigger_type'
      AND object_id = OBJECT_ID('dbo.runs')
)
BEGIN
    CREATE INDEX IX_runs_trigger_type ON dbo.runs(trigger_type);
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_runs_schedule_id'
      AND object_id = OBJECT_ID('dbo.runs')
)
BEGIN
    CREATE INDEX IX_runs_schedule_id ON dbo.runs(schedule_id);
END;
GO

IF OBJECT_ID('dbo.sla_rules', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.sla_rules (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        robot_id UNIQUEIDENTIFIER NOT NULL,
        expected_run_every_minutes INT NULL,
        expected_daily_time NVARCHAR(5) NULL,
        late_after_minutes INT NOT NULL DEFAULT 15,
        alert_on_failure BIT NOT NULL DEFAULT 1,
        alert_on_late BIT NOT NULL DEFAULT 1,
        notify_channels_json NVARCHAR(MAX) NOT NULL DEFAULT '{}',
        created_by UNIQUEIDENTIFIER NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        updated_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        CONSTRAINT FK_sla_rules_robots FOREIGN KEY (robot_id) REFERENCES dbo.robots(id) ON DELETE CASCADE,
        CONSTRAINT FK_sla_rules_users FOREIGN KEY (created_by) REFERENCES dbo.users(id),
        CONSTRAINT UQ_sla_rules_robot_id UNIQUE (robot_id)
    );
END;
GO

IF OBJECT_ID('dbo.alert_events', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.alert_events (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        robot_id UNIQUEIDENTIFIER NOT NULL,
        run_id UNIQUEIDENTIFIER NULL,
        type NVARCHAR(40) NOT NULL,
        severity NVARCHAR(20) NOT NULL,
        message NVARCHAR(MAX) NOT NULL,
        metadata_json NVARCHAR(MAX) NOT NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        resolved_at DATETIMEOFFSET NULL,
        CONSTRAINT FK_alert_events_robots FOREIGN KEY (robot_id) REFERENCES dbo.robots(id) ON DELETE CASCADE,
        CONSTRAINT FK_alert_events_runs FOREIGN KEY (run_id) REFERENCES dbo.runs(run_id)
    );
    CREATE INDEX IX_alert_events_robot_id ON dbo.alert_events(robot_id);
    CREATE INDEX IX_alert_events_type ON dbo.alert_events(type);
    CREATE INDEX IX_alert_events_created_at ON dbo.alert_events(created_at);
    CREATE INDEX IX_alert_events_resolved_at ON dbo.alert_events(resolved_at);
END;
GO
