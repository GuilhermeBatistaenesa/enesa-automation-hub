-- Enesa Automation Hub - Self-Service Portal
-- Adds domains/services catalog and service-driven run metadata.

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;

IF OBJECT_ID('dbo.domains', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.domains (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        name NVARCHAR(200) NOT NULL,
        slug NVARCHAR(120) NOT NULL,
        description NVARCHAR(MAX) NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        CONSTRAINT UQ_domains_name UNIQUE (name),
        CONSTRAINT UQ_domains_slug UNIQUE (slug)
    );
    CREATE INDEX IX_domains_slug ON dbo.domains(slug);
END;
GO

IF OBJECT_ID('dbo.services', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.services (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        domain_id UNIQUEIDENTIFIER NOT NULL,
        robot_id UNIQUEIDENTIFIER NOT NULL,
        title NVARCHAR(200) NOT NULL,
        description NVARCHAR(MAX) NULL,
        icon NVARCHAR(120) NULL,
        enabled BIT NOT NULL DEFAULT 1,
        default_version_id UNIQUEIDENTIFIER NULL,
        form_schema_json NVARCHAR(MAX) NOT NULL DEFAULT '{}',
        run_template_json NVARCHAR(MAX) NOT NULL DEFAULT '{}',
        created_by UNIQUEIDENTIFIER NULL,
        created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        updated_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
        CONSTRAINT FK_services_domains FOREIGN KEY (domain_id) REFERENCES dbo.domains(id) ON DELETE CASCADE,
        CONSTRAINT FK_services_robots FOREIGN KEY (robot_id) REFERENCES dbo.robots(id),
        CONSTRAINT FK_services_default_version FOREIGN KEY (default_version_id) REFERENCES dbo.robot_versions(id),
        CONSTRAINT FK_services_users FOREIGN KEY (created_by) REFERENCES dbo.users(id),
        CONSTRAINT UQ_services_domain_id_title UNIQUE (domain_id, title)
    );
    CREATE INDEX IX_services_domain_id ON dbo.services(domain_id);
    CREATE INDEX IX_services_robot_id ON dbo.services(robot_id);
    CREATE INDEX IX_services_enabled ON dbo.services(enabled);
END;
GO

IF COL_LENGTH('dbo.runs', 'service_id') IS NULL
BEGIN
    ALTER TABLE dbo.runs
    ADD service_id UNIQUEIDENTIFIER NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'parameters_json') IS NULL
BEGIN
    ALTER TABLE dbo.runs
    ADD parameters_json NVARCHAR(MAX) NULL;
END;
GO

IF COL_LENGTH('dbo.runs', 'service_id') IS NOT NULL
AND NOT EXISTS (
    SELECT 1
    FROM sys.foreign_keys
    WHERE name = 'FK_runs_services'
      AND parent_object_id = OBJECT_ID('dbo.runs')
)
BEGIN
    ALTER TABLE dbo.runs
    ADD CONSTRAINT FK_runs_services
        FOREIGN KEY (service_id) REFERENCES dbo.services(id);
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_runs_service_id'
      AND object_id = OBJECT_ID('dbo.runs')
)
BEGIN
    CREATE INDEX IX_runs_service_id ON dbo.runs(service_id);
END;
GO
