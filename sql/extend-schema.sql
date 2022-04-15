-- Add column for laboratory and analyst to table
-- This is a bit hacky pending better implementation of many-to-many relationship for researchers/samples/projects
ALTER TABLE sample ADD COLUMN laboratory text ;
ALTER TABLE sample ADD COLUMN researcher_id integer REFERENCES researcher(id) ;