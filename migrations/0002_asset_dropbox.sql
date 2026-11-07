-- Phase 08: every Higgsfield output is copied to the operator's Dropbox (see packages/contracts/INTERNAL-API.md).
ALTER TABLE assets ADD COLUMN dropbox_path TEXT;
ALTER TABLE assets ADD COLUMN dropbox_status TEXT;
