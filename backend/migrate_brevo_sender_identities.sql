-- Safe, additive migration. Existing SMTP settings and records are untouched.
CREATE TABLE IF NOT EXISTS email_sender_identities (
    id CHAR(36) NOT NULL,
    sender_email VARCHAR(255) NOT NULL,
    sender_name VARCHAR(255) NOT NULL,
    reply_to_email VARCHAR(255) NULL,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verification_method VARCHAR(32) NULL,
    verified_at DATETIME NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    disabled_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_email_sender_identities_email (sender_email),
    KEY idx_email_sender_active (is_active, is_verified, disabled_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
