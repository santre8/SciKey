USE scikey;


CREATE TABLE IF NOT EXISTS documents (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  doc_id BIGINT NOT NULL,
  halId_s VARCHAR(50),
  title VARCHAR(255),
  abstract MEDIUMTEXT,
  discipline VARCHAR(100),
  domain_codes TEXT,
  url_primary TEXT,
  PRIMARY KEY (id),
  UNIQUE KEY uk_documents_doc_id (doc_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

 CREATE TABLE IF NOT EXISTS organisms (
  hal_structure_id BIGINT NOT NULL,
  structIdName_fs VARCHAR(255),
  PRIMARY KEY (hal_structure_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS authors (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  doc_id BIGINT,
  author_index INT,    
  authFirstName_s VARCHAR(255),
  authLastName_s VARCHAR(255),
  authQuality_s VARCHAR(255),
  PRIMARY KEY (id),
  KEY idx_authors_doc_id (doc_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS journals (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  doc_id BIGINT,
  journalIssn_s VARCHAR(50),
  journalTitle_s VARCHAR(255),
  PRIMARY KEY (id),
  KEY idx_journals_doc_id (doc_id),
  KEY idx_journals_issn (journalIssn_s)
 ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS keywords (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  doc_id BIGINT,
  keyword_s VARCHAR(255),
  PRIMARY KEY (id),
  KEY idx_keywords_doc_id (doc_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS identifiers (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  doc_id BIGINT NOT NULL,
  doiId_s VARCHAR(255),
  halId_s VARCHAR(255),
  isbn VARCHAR(255),
  PRIMARY KEY (id),
  KEY idx_identifiers_doc_id (doc_id),
  KEY idx_identifiers_doi (doiId_s),
  KEY idx_identifiers_halid (halId_s),
  KEY idx_identifiers_isbn (isbn)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_organisms (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  doc_id BIGINT NOT NULL,             
  hal_structure_id BIGINT NOT NULL,   
  PRIMARY KEY (id),
  KEY idx_doc_org_doc (doc_id),
  KEY idx_doc_org_struct (hal_structure_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS author_organisms (
  doc_id BIGINT NOT NULL,
  author_index INT NOT NULL,
  hal_structure_id BIGINT NOT NULL,
  PRIMARY KEY (doc_id, author_index, hal_structure_id),
  KEY idx_ao_struct (hal_structure_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;