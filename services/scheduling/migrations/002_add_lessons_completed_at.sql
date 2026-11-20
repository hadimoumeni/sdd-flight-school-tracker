-- Record when a lesson was completed.
-- lessons already holds data, so the column is added as NULL (existing rows stay
-- valid) and lessons that are already completed are backfilled with their end time,
-- the closest value we have. Nothing is dropped or recreated.
ALTER TABLE lessons ADD completed_at DATETIME2 NULL;
GO

UPDATE lessons
SET completed_at = end_time
WHERE status = 'completed' AND completed_at IS NULL;
