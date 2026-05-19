// ═══════════════════════════════════════════════════════════════════════════
// PeerLearn — MongoDB Initialization Script
// Runs once when the MongoDB container is first created.
// Creates the application database user and bootstraps collections.
// ═══════════════════════════════════════════════════════════════════════════

// Authenticate as root first (script runs in admin context)
db = db.getSiblingDB("peer_learning");

// Create a dedicated application user (least-privilege)
db.createUser({
  user: "peerlearn",
  pwd: process.env.MONGO_APP_PASSWORD || "mongoapppwd",
  roles: [
    { role: "readWrite", db: "peer_learning" },
    { role: "dbAdmin",   db: "peer_learning" }
  ]
});

// ── Bootstrap collections with schema validation ─────────────────────────────

// discussions collection
db.createCollection("discussions", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["channel_id", "author_id", "title", "created_at"],
      properties: {
        channel_id:  { bsonType: "int",    description: "MySQL Channel PK" },
        author_id:   { bsonType: "int",    description: "MySQL User PK" },
        title:       { bsonType: "string", maxLength: 300 },
        body:        { bsonType: "string" },
        is_deleted:  { bsonType: "bool" }
      }
    }
  },
  validationAction: "warn"   // warn not error, so seed_data works smoothly
});

// messages collection
db.createCollection("messages", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["discussion_id", "author_id", "body", "created_at"],
      properties: {
        discussion_id:       { bsonType: "string" },
        author_id:           { bsonType: "int" },
        body:                { bsonType: "string" },
        is_deleted:          { bsonType: "bool" },
        deleted_by_moderator:{ bsonType: "bool" }
      }
    }
  },
  validationAction: "warn"
});

// search_logs collection (no strict schema — analytics data)
db.createCollection("search_logs");

// ── Indexes ──────────────────────────────────────────────────────────────────
db.discussions.createIndex({ channel_id: 1 });
db.discussions.createIndex({ author_id: 1 });
db.discussions.createIndex({ title: "text", body: "text" }, { name: "discussions_fulltext" });
db.discussions.createIndex({ created_at: -1 });

db.messages.createIndex({ discussion_id: 1 });
db.messages.createIndex({ author_id: 1 });
db.messages.createIndex({ body: "text" }, { name: "messages_fulltext" });

db.search_logs.createIndex({ created_at: -1 });
db.search_logs.createIndex({ query: "text" });

print("✅ PeerLearn MongoDB initialization complete.");
