-- Enesa Automation Hub - Robot Versions Registry
-- Adds publish/rollback registry metadata and normalizes audit_events format.

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;

IF COL_LENGTH('dbo.robot_versions', 'channel') IS NULL
BEGIN
    ALTER TABLE dbo.robot_versions ADD channel NVARCHAR(20) NOT NULL CONSTRAINT DF_robot_versions_channel DEFAULT 'stable';
END;
GO

IF COL_LENGTH('dbo.robot_versions', 'artifact_type') IS NULL
BEGIN
    ALTER TABLE dbo.robot_versions ADD artifact_type NVARCHAR(20) NOT NULL CONSTRAINT DF_robot_versions_artifact_type DEFAULT 'ZIP';
END;
GO

IF COL_LENGTH('dbo.robot_versions', 'artifact_path') IS NULL
BEGIN
    ALTER TABLE dbo.robot_versions ADD artifact_path NVARCHAR(2048) NULL;
END;
GO

IF COL_LENGTH('dbo.robot_versions', 'artifact_sha256') IS NULL
BEGIN
    ALTER TABLE dbo.robot_versions ADD artifact_sha256 NVARCHAR(128) NULL;
END;
GO

IF COL_LENGTH('dbo.robot_versions', 'changelog') IS NULL
BEGIN
    ALTER TABLE dbo.robot_versions ADD changelog NVARCHAR(MAX) NULL;
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UQ_robot_versions_robot_id_version'
      AND object_id = OBJECT_ID('dbo.robot_versions')
)
BEGIN
    CREATE UNIQUE INDEX UQ_robot_versions_robot_id_version ON dbo.robot_versions(robot_id, version);
END;
GO

IF OBJECT_ID('dbo.robot_release_tags', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.robot_release_tags (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        robot_id UNIQUEIDENTIFIER NOT NULL,
        tag NVARCHAR(30) NOT NULL,
        version_id UNIQUEIDENTIFIER NOT NULL,
        CONSTRAINT FK_robot_release_tags_robot FOREIGN KEY (robot_id) REFERENCES dbo.robots(id) ON DELETE CASCADE,
        CONSTRAINT FK_robot_release_tags_version FOREIGN KEY (version_id) REFERENCES dbo.robot_versions(id) ON DELETE CASCADE,
        CONSTRAINT UQ_robot_release_tags_robot_tag UNIQUE (robot_id, tag)
    );
    CREATE INDEX IX_robot_release_tags_robot_id ON dbo.robot_release_tags(robot_id);
    CREATE INDEX IX_robot_release_tags_tag ON dbo.robot_release_tags(tag);
END;
GO

IF OBJECT_ID('dbo.audit_events', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.audit_events (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        actor_user_id UNIQUEIDENTIFIER NULL,
        action NVARCHAR(120) NOT NULL,
        target_type NVARCHAR(80) NULL,
        target_id NVARCHAR(255) NULL,
        metadata_json NVARCHAR(MAX) NOT NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        ip NVARCHAR(64) NULL
    );
    CREATE INDEX IX_audit_events_actor_user_id ON dbo.audit_events(actor_user_id);
    CREATE INDEX IX_audit_events_action ON dbo.audit_events(action);
    CREATE INDEX IX_audit_events_target_type ON dbo.audit_events(target_type);
    CREATE INDEX IX_audit_events_target_id ON dbo.audit_events(target_id);
    CREATE INDEX IX_audit_events_created_at ON dbo.audit_events(created_at);
END;
GO

IF OBJECT_ID('dbo.audit_events', 'U') IS NOT NULL
BEGIN
    IF COL_LENGTH('dbo.audit_events', 'target_type') IS NULL
    BEGIN
        ALTER TABLE dbo.audit_events ADD target_type NVARCHAR(80) NULL;
    END;
    IF COL_LENGTH('dbo.audit_events', 'target_id') IS NULL
    BEGIN
        ALTER TABLE dbo.audit_events ADD target_id NVARCHAR(255) NULL;
    END;
    IF COL_LENGTH('dbo.audit_events', 'created_at') IS NULL
    BEGIN
        ALTER TABLE dbo.audit_events ADD created_at DATETIMEOFFSET NULL;
    END;
    IF COL_LENGTH('dbo.audit_events', 'ip') IS NULL
    BEGIN
        ALTER TABLE dbo.audit_events ADD ip NVARCHAR(64) NULL;
    END;
END;
GO

IF COL_LENGTH('dbo.audit_events', 'created_at') IS NOT NULL
BEGIN
    IF COL_LENGTH('dbo.audit_events', 'timestamp') IS NOT NULL
    BEGIN
        UPDATE dbo.audit_events
        SET created_at = COALESCE(created_at, [timestamp], SYSDATETIMEOFFSET())
        WHERE created_at IS NULL;
    END;
    IF COL_LENGTH('dbo.audit_events', 'timestamp') IS NULL
    BEGIN
        UPDATE dbo.audit_events
        SET created_at = COALESCE(created_at, SYSDATETIMEOFFSET())
        WHERE created_at IS NULL;
    END;
END;
GO

IF COL_LENGTH('dbo.audit_events', 'created_at') IS NOT NULL
BEGIN
    ALTER TABLE dbo.audit_events
    ALTER COLUMN created_at DATETIMEOFFSET NOT NULL;
END;
GO

IF COL_LENGTH('dbo.audit_events', 'ip') IS NOT NULL
BEGIN
    IF COL_LENGTH('dbo.audit_events', 'actor_ip') IS NOT NULL
    BEGIN
        UPDATE dbo.audit_events
        SET ip = COALESCE(ip, actor_ip)
        WHERE ip IS NULL;
    END;
END;
GO
