-- Enesa Automation Hub - Operational Control (Run cancel + Worker management)

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;

IF COL_LENGTH('dbo.runs', 'cancel_requested') IS NULL
BEGIN
    ALTER TABLE dbo.runs
    ADD cancel_requested BIT NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'canceled_at') IS NULL
BEGIN
    ALTER TABLE dbo.runs
    ADD canceled_at DATETIMEOFFSET NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'canceled_by') IS NULL
BEGIN
    ALTER TABLE dbo.runs
    ADD canceled_by UNIQUEIDENTIFIER NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'cancel_requested') IS NOT NULL
BEGIN
    UPDATE dbo.runs
    SET cancel_requested = COALESCE(cancel_requested, 0)
    WHERE cancel_requested IS NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'cancel_requested') IS NOT NULL
BEGIN
    ALTER TABLE dbo.runs
    ALTER COLUMN cancel_requested BIT NOT NULL;
END;
GO

IF OBJECT_ID('DF_runs_cancel_requested', 'D') IS NULL
BEGIN
    ALTER TABLE dbo.runs
    ADD CONSTRAINT DF_runs_cancel_requested DEFAULT 0 FOR cancel_requested;
END;
GO

IF COL_LENGTH('dbo.runs', 'canceled_by') IS NOT NULL
AND NOT EXISTS (
    SELECT 1
    FROM sys.foreign_keys
    WHERE name = 'FK_runs_canceled_by_users'
      AND parent_object_id = OBJECT_ID('dbo.runs')
)
BEGIN
    ALTER TABLE dbo.runs
    ADD CONSTRAINT FK_runs_canceled_by_users
        FOREIGN KEY (canceled_by) REFERENCES dbo.users(id);
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_runs_cancel_requested'
      AND object_id = OBJECT_ID('dbo.runs')
)
BEGIN
    CREATE INDEX IX_runs_cancel_requested ON dbo.runs(cancel_requested);
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_runs_canceled_by'
      AND object_id = OBJECT_ID('dbo.runs')
)
BEGIN
    CREATE INDEX IX_runs_canceled_by ON dbo.runs(canceled_by);
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_runs_canceled_at'
      AND object_id = OBJECT_ID('dbo.runs')
)
BEGIN
    CREATE INDEX IX_runs_canceled_at ON dbo.runs(canceled_at);
END;
GO

IF OBJECT_ID('dbo.workers', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.workers (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        hostname NVARCHAR(255) NOT NULL,
        status NVARCHAR(20) NOT NULL,
        last_heartbeat DATETIMEOFFSET NOT NULL,
        version NVARCHAR(50) NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET()
    );
    CREATE INDEX IX_workers_status ON dbo.workers(status);
    CREATE INDEX IX_workers_last_heartbeat ON dbo.workers(last_heartbeat);
END;
GO
