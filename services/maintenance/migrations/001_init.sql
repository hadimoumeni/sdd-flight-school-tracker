CREATE TABLE aircraft (
    id INT IDENTITY(1,1) PRIMARY KEY,
    tail_number NVARCHAR(20) NOT NULL UNIQUE,
    model NVARCHAR(100) NOT NULL,
    total_hours FLOAT NOT NULL DEFAULT 0,
    hours_at_last_inspection FLOAT NOT NULL DEFAULT 0
);

CREATE TABLE squawks (
    id INT IDENTITY(1,1) PRIMARY KEY,
    aircraft_id INT NOT NULL REFERENCES aircraft(id),
    description NVARCHAR(500) NOT NULL,
    severity NVARCHAR(10) NOT NULL CHECK (severity IN ('minor', 'safety')),
    reported_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    resolved_at DATETIME2 NULL
);

-- One row that /health updates, to prove the service can write to its database.
CREATE TABLE health_check (
    id INT PRIMARY KEY,
    checked_at DATETIME2 NULL
);

INSERT INTO health_check (id) VALUES (1);
