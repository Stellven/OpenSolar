//! Document schema for Solar Search
//!
//! Defines the structure of indexed documents across all data sources.

use tantivy::schema::{Schema, STORED, TEXT, STRING, FAST};
use tantivy::schema::{TextFieldIndexing, TextOptions, IndexRecordOption};

/// Document types in Solar
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DocType {
    /// Conversation messages from .jsonl
    Conversation,
    /// Semantic/episodic/procedural memories
    Memory,
    /// Source code files
    Code,
    /// Documentation and markdown
    Document,
    /// System registry entries (skills, agents, etc.)
    Registry,
    /// Statistics and logs
    Stats,
}

impl DocType {
    pub fn as_str(&self) -> &'static str {
        match self {
            DocType::Conversation => "conversation",
            DocType::Memory => "memory",
            DocType::Code => "code",
            DocType::Document => "document",
            DocType::Registry => "registry",
            DocType::Stats => "stats",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "conversation" => Some(DocType::Conversation),
            "memory" => Some(DocType::Memory),
            "code" => Some(DocType::Code),
            "document" => Some(DocType::Document),
            "registry" => Some(DocType::Registry),
            "stats" => Some(DocType::Stats),
            _ => None,
        }
    }
}

/// Build the Tantivy schema for Solar documents
pub fn build_schema() -> Schema {
    let mut schema_builder = Schema::builder();

    // Unique identifier
    schema_builder.add_text_field("id", STRING | STORED);

    // Document type (conversation, memory, code, etc.)
    schema_builder.add_text_field("doc_type", STRING | STORED | FAST);

    // Main content - full-text indexed with Chinese support
    let text_indexing = TextFieldIndexing::default()
        .set_tokenizer("jieba")
        .set_index_option(IndexRecordOption::WithFreqsAndPositions);
    let text_options = TextOptions::default()
        .set_indexing_options(text_indexing)
        .set_stored();
    schema_builder.add_text_field("content", text_options);

    // Title/subject (for conversations, memory titles, etc.)
    schema_builder.add_text_field("title", TEXT | STORED);

    // Source file path
    schema_builder.add_text_field("source", STRING | STORED);

    // Timestamp (Unix timestamp in seconds)
    schema_builder.add_u64_field("timestamp", STORED | FAST);

    // Role (for conversations: user/assistant/system)
    schema_builder.add_text_field("role", STRING | STORED);

    // Project context
    schema_builder.add_text_field("project", STRING | STORED);

    // Additional metadata as JSON string
    schema_builder.add_text_field("metadata", STORED);

    schema_builder.build()
}

/// Field accessors for the schema
pub struct SchemaFields {
    pub id: tantivy::schema::Field,
    pub doc_type: tantivy::schema::Field,
    pub content: tantivy::schema::Field,
    pub title: tantivy::schema::Field,
    pub source: tantivy::schema::Field,
    pub timestamp: tantivy::schema::Field,
    pub role: tantivy::schema::Field,
    pub project: tantivy::schema::Field,
    pub metadata: tantivy::schema::Field,
}

impl SchemaFields {
    pub fn new(schema: &Schema) -> Self {
        Self {
            id: schema.get_field("id").unwrap(),
            doc_type: schema.get_field("doc_type").unwrap(),
            content: schema.get_field("content").unwrap(),
            title: schema.get_field("title").unwrap(),
            source: schema.get_field("source").unwrap(),
            timestamp: schema.get_field("timestamp").unwrap(),
            role: schema.get_field("role").unwrap(),
            project: schema.get_field("project").unwrap(),
            metadata: schema.get_field("metadata").unwrap(),
        }
    }
}
