-- Enesa Automation Hub - Initial Schema (SQL Server)
-- Execute in target database: enesa_automation_hub

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;

IF OBJECT_ID('dbo.users', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.users (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        username NVARCHAR(128) NOT NULL UNIQUE,
        full_name NVARCHAR(255) NULL,
        email NVARCHAR(255) NULL UNIQUE,
        hashed_password NVARCHAR(255) NOT NULL,
        is_active BIT NOT NULL DEFAULT 1,
        is_superuser BIT NOT NULL DEFAULT 0,
        auth_source NVARCHAR(50) NOT NULL DEFAULT 'local',
        azure_object_id NVARCHAR(255) NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        updated_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET()
    );
END;
GO

IF OBJECT_ID('dbo.permissions', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.permissions (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        user_id UNIQUEIDENTIFIER NOT NULL,
        resource_type NVARCHAR(50) NOT NULL,
        resource_id UNIQUEIDENTIFIER NULL,
        action NVARCHAR(80) NOT NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        CONSTRAINT FK_permissions_users FOREIGN KEY (user_id) REFERENCES dbo.users(id) ON DELETE CASCADE
    );
    CREATE INDEX IX_permissions_user_id ON dbo.permissions(user_id);
    CREATE INDEX IX_permissions_action ON dbo.permissions(action);
    CREATE INDEX IX_permissions_resource_type ON dbo.permissions(resource_type);
END;
GO

IF OBJECT_ID('dbo.robots', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.robots (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        name NVARCHAR(200) NOT NULL UNIQUE,
        description NVARCHAR(MAX) NULL,
        created_by UNIQUEIDENTIFIER NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        updated_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        CONSTRAINT FK_robots_users FOREIGN KEY (created_by) REFERENCES dbo.users(id)
    );
END;
GO

IF OBJECT_ID('dbo.robot_versions', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.robot_versions (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        robot_id UNIQUEIDENTIFIER NOT NULL,
        version NVARCHAR(50) NOT NULL,
        entrypoint_type NVARCHAR(20) NOT NULL,
        entrypoint_path NVARCHAR(1024) NOT NULL,
        arguments NVARCHAR(MAX) NOT NULL,
        env_vars NVARCHAR(MAX) NOT NULL,
        working_directory NVARCHAR(1024) NULL,
        checksum NVARCHAR(255) NULL,
        created_by UNIQUEIDENTIFIER NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        is_active BIT NOT NULL DEFAULT 1,
        CONSTRAINT FK_robot_versions_robots FOREIGN KEY (robot_id) REFERENCES dbo.robots(id) ON DELETE CASCADE,
        CONSTRAINT FK_robot_versions_users FOREIGN KEY (created_by) REFERENCES dbo.users(id)
    );
    CREATE INDEX IX_robot_versions_robot_id ON dbo.robot_versions(robot_id);
END;
GO

IF OBJECT_ID('dbo.runs', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.runs (
        run_id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        robot_id UNIQUEIDENTIFIER NOT NULL,
        robot_version_id UNIQUEIDENTIFIER NOT NULL,
        status NVARCHAR(20) NOT NULL,
        queued_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        started_at DATETIMEOFFSET NULL,
        finished_at DATETIMEOFFSET NULL,
        duration_seconds FLOAT NULL,
        triggered_by UNIQUEIDENTIFIER NULL,
        error_message NVARCHAR(MAX) NULL,
        host_name NVARCHAR(255) NULL,
        process_id INT NULL,
        CONSTRAINT FK_runs_robots FOREIGN KEY (robot_id) REFERENCES dbo.robots(id),
        CONSTRAINT FK_runs_robot_versions FOREIGN KEY (robot_version_id) REFERENCES dbo.robot_versions(id),
        CONSTRAINT FK_runs_users FOREIGN KEY (triggered_by) REFERENCES dbo.users(id)
    );
    CREATE INDEX IX_runs_robot_id ON dbo.runs(robot_id);
    CREATE INDEX IX_runs_status ON dbo.runs(status);
    CREATE INDEX IX_runs_triggered_by ON dbo.runs(triggered_by);
END;
GO

IF OBJECT_ID('dbo.run_logs', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.run_logs (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        run_id UNIQUEIDENTIFIER NOT NULL,
        [timestamp] DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        [level] NVARCHAR(20) NOT NULL,
        [message] NVARCHAR(MAX) NOT NULL,
        CONSTRAINT FK_run_logs_runs FOREIGN KEY (run_id) REFERENCES dbo.runs(run_id) ON DELETE CASCADE
    );
    CREATE INDEX IX_run_logs_run_id ON dbo.run_logs(run_id);
    CREATE INDEX IX_run_logs_timestamp ON dbo.run_logs([timestamp]);
END;
GO

IF OBJECT_ID('dbo.artifacts', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.artifacts (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        run_id UNIQUEIDENTIFIER NOT NULL,
        artifact_name NVARCHAR(255) NOT NULL,
        file_path NVARCHAR(2048) NOT NULL,
        file_size_bytes INT NOT NULL,
        content_type NVARCHAR(255) NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        CONSTRAINT FK_artifacts_runs FOREIGN KEY (run_id) REFERENCES dbo.runs(run_id) ON DELETE CASCADE
    );
    CREATE INDEX IX_artifacts_run_id ON dbo.artifacts(run_id);
END;
GO

