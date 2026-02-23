-- Enesa Automation Hub - Enterprise Hardening
-- Adds scoped permissions, robot tags and audit events.

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;

IF COL_LENGTH('dbo.permissions', 'scope_tag') IS NULL
BEGIN
    ALTER TABLE dbo.permissions
    ADD scope_tag NVARCHAR(100) NULL;
END;
GO

UPDATE dbo.permissions SET action = 'robot.publish' WHERE action = 'robots:create';
UPDATE dbo.permissions SET action = 'robot.read' WHERE action = 'robots:read';
UPDATE dbo.permissions SET action = 'robot.run' WHERE action = 'robots:execute';
UPDATE dbo.permissions SET action = 'run.read' WHERE action = 'runs:read';
UPDATE dbo.permissions SET action = 'run.read' WHERE action = 'runs:logs:read';
UPDATE dbo.permissions SET action = 'artifact.download' WHERE action = 'artifacts:read';
UPDATE dbo.permissions SET action = 'admin.manage' WHERE action = 'users:manage';
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_permissions_scope_tag'
    AND object_id = OBJECT_ID('dbo.permissions')
)
BEGIN
    CREATE INDEX IX_permissions_scope_tag ON dbo.permissions(scope_tag);
END;
GO

IF OBJECT_ID('dbo.robot_tags', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.robot_tags (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        robot_id UNIQUEIDENTIFIER NOT NULL,
        tag NVARCHAR(100) NOT NULL,
        CONSTRAINT FK_robot_tags_robots FOREIGN KEY (robot_id) REFERENCES dbo.robots(id) ON DELETE CASCADE,
        CONSTRAINT UQ_robot_tags_robot_id_tag UNIQUE (robot_id, tag)
    );
    CREATE INDEX IX_robot_tags_robot_id ON dbo.robot_tags(robot_id);
    CREATE INDEX IX_robot_tags_tag ON dbo.robot_tags(tag);
END;
GO

IF OBJECT_ID('dbo.audit_events', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.audit_events (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        actor_user_id UNIQUEIDENTIFIER NULL,
        actor_subject NVARCHAR(255) NOT NULL,
        actor_role NVARCHAR(50) NULL,
        actor_ip NVARCHAR(64) NULL,
        action NVARCHAR(120) NOT NULL,
        metadata_json NVARCHAR(MAX) NOT NULL,
        [timestamp] DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET()
    );
    CREATE INDEX IX_audit_events_actor_user_id ON dbo.audit_events(actor_user_id);
    CREATE INDEX IX_audit_events_action ON dbo.audit_events(action);
    CREATE INDEX IX_audit_events_timestamp ON dbo.audit_events([timestamp]);
END;
GO
