CREATE TABLE students (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    email NVARCHAR(254) NOT NULL
);

CREATE TABLE instructors (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    email NVARCHAR(254) NOT NULL,
    certificate_number NVARCHAR(50) NOT NULL
);

-- aircraft_id points to the maintenance service's database, so it is a plain
-- ID with no foreign key: the service checks it over HTTP instead.
CREATE TABLE lessons (
    id INT IDENTITY(1,1) PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(id),
    instructor_id INT NOT NULL REFERENCES instructors(id),
    aircraft_id INT NOT NULL,
    start_time DATETIME2 NOT NULL,
    end_time DATETIME2 NOT NULL,
    status NVARCHAR(20) NOT NULL DEFAULT 'scheduled'
);

-- One row that /health updates, to prove the service can write to its database.
CREATE TABLE health_check (
    id INT PRIMARY KEY,
    checked_at DATETIME2 NULL
);

INSERT INTO health_check (id) VALUES (1);
