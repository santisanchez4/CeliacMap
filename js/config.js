/* =====================================================================
   CeliacMap — js/config.js
   Public frontend configuration. The Supabase ANON key is safe to expose:
   Row Level Security restricts it to reading APPROVED places only.
   The service_role key must NEVER appear here — it lives in .env / CI only.
   ===================================================================== */
window.CELIACMAP_CONFIG = {
  SUPABASE_URL: "https://pgblbyvetclllaqvknvc.supabase.co",
  SUPABASE_ANON_KEY:
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBnYmxieXZldGNsbGxhcXZrbnZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1MDk1MDgsImV4cCI6MjA5NjA4NTUwOH0.kv4Eh_b0InQXy74CfFi4iyPS157xzQ1fMXyaf6DMj1Y"
};
