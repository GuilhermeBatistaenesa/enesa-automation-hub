-- Enesa Automation Hub - GitHub Deploy + Robot Env/Secrets Manager

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;

IF COL_LENGTH('dbo.robot_versions', 'commit_sha') IS NULL
BEGIN
    ALTER TABLE dbo.robot_versions
    ADD commit_sha NVARCHAR(80) NULL;
END;
GO

IF COL_LENGTH('dbo.robot_versions', 'branch') IS NULL
BEGIN
    ALTER TABLE dbo.robot_versions
    ADD branch NVARCHAR(255) NULL;
END;
GO

IF COL_LENGTH('dbo.robot_versions', 'build_url') IS NULL
BEGIN
    ALTER TABLE dbo.robot_versions
    ADD build_url NVARCHAR(2048) NULL;
END;
GO

IF COL_LENGTH('dbo.robot_versions', 'created_source') IS NULL
BEGIN
    ALTER TABLE dbo.robot_versions
    ADD created_source NVARCHAR(50) NULL;
END;
GO

IF COL_LENGTH('dbo.robot_versions', 'required_env_keys_json') IS NULL
BEGIN
    ALTER TABLE dbo.robot_versions
    ADD required_env_keys_json NVARCHAR(MAX) NULL;
END;
GO

IF COL_LENGTH('dbo.robot_versions', 'created_source') IS NOT NULL
BEGIN
    UPDATE dbo.robot_versions
    SET created_source = COALESCE(created_source, 'user')
    WHERE created_source IS NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'env_name') IS NULL
BEGIN
    ALTER TABLE dbo.runs
    ADD env_name NVARCHAR(20) NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'env_name') IS NOT NULL
BEGIN
    UPDATE dbo.runs
    SET env_name = COALESCE(env_name, 'PROD')
    WHERE env_name IS NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'env_name') IS NOT NULL
BEGIN
    ALTER TABLE dbo.runs
    ALTER COLUMN env_name NVARCHAR(20) NOT NULL;
END;
GO

IF OBJECT_ID('DF_runs_env_name', 'D') IS NULL
BEGIN
    ALTER TABLE dbo.runs
    ADD CONSTRAINT DF_runs_env_name DEFAULT 'PROD' FOR env_name;
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_runs_env_name'
      AND object_id = OBJECT_ID('dbo.runs')
)
BEGIN
    CREATE INDEX IX_runs_env_name ON dbo.runs(env_name);
END;
GO

IF OBJECT_ID('dbo.robot_env_vars', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.robot_env_vars (
        robot_id UNIQUEIDENTIFIER NOT NULL,
        env_name NVARCHAR(20) NOT NULL,
        [key] NVARCHAR(150) NOT NULL,
        value_encrypted NVARCHAR(MAX) NOT NULL,
        is_secret BIT NOT NULL DEFAULT 0,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        created_by UNIQUEIDENTIFIER NULL,
        updated_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        updated_by UNIQUEIDENTIFIER NULL,
        CONSTRAINT PK_robot_env_vars PRIMARY KEY (robot_id, env_name, [key]),
        CONSTRAINT FK_robot_env_vars_robot FOREIGN KEY (robot_id) REFERENCES dbo.robots(id) ON DELETE CASCADE,
        CONSTRAINT FK_robot_env_vars_created_by FOREIGN KEY (created_by) REFERENCES dbo.users(id),
        CONSTRAINT FK_robot_env_vars_updated_by FOREIGN KEY (updated_by) REFERENCES dbo.users(id)
    );
    CREATE INDEX IX_robot_env_vars_env_name ON dbo.robot_env_vars(env_name);
    CREATE INDEX IX_robot_env_vars_key ON dbo.robot_env_vars([key]);
END;
GO
