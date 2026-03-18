-- EpiScoutDB Schema - MySQL Version
-- Chuyển đổi từ SQL Server sang MySQL

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table: article_identity
-- (Tạo trước vì article_details và disease_cases tham chiếu đến bảng này)
-- ----------------------------
CREATE TABLE `article_identity` (
  `id`             INT            NOT NULL AUTO_INCREMENT,
  `title`          NVARCHAR(500)  NULL,
  `link`           VARCHAR(500)   NULL,
  `published_date` DATETIME       NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_article_identity_link` (`link`),
  KEY `ix_article_identity_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table: article_details
-- ----------------------------
CREATE TABLE `article_details` (
  `id`               INT            NOT NULL AUTO_INCREMENT,
  `article_id`       INT            NULL,
  `summary`          LONGTEXT       NULL,
  `source`           NVARCHAR(255)  NULL,
  `keywords_matched` NVARCHAR(500)  NULL,
  `tags`             NVARCHAR(500)  NULL,
  `is_whitelisted`   TINYINT(1)     NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_article_details_article_id` (`article_id`),
  KEY `ix_article_details_id` (`id`),
  CONSTRAINT `fk_article_details_article_id`
    FOREIGN KEY (`article_id`) REFERENCES `article_identity` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table: articles
-- ----------------------------
CREATE TABLE `articles` (
  `id`               INT              NOT NULL AUTO_INCREMENT,
  `title`            VARCHAR(500)     NOT NULL,
  `link`             VARCHAR(2048)    NOT NULL,
  `summary`          LONGTEXT         NULL,
  `source`           VARCHAR(255)     NULL,
  `published_date`   DATETIME         NULL,
  `keywords_matched` VARCHAR(500)     NULL,
  `is_whitelisted`   TINYINT(1)       NULL,
  `created_at`       DATETIME         NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_articles_link` (`link`(500)),
  KEY `ix_articles_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table: disease_cases
-- ----------------------------
CREATE TABLE `disease_cases` (
  `id`           INT            NOT NULL AUTO_INCREMENT,
  `article_id`   INT            NULL,
  `disease_name` NVARCHAR(255)  NULL,
  `case_count`   INT            NULL,
  `location`     NVARCHAR(255)  NULL,
  `report_date`  DATETIME       NULL,
  PRIMARY KEY (`id`),
  KEY `ix_disease_cases_id` (`id`),
  KEY `ix_disease_cases_disease_name` (`disease_name`),
  CONSTRAINT `fk_disease_cases_article_id`
    FOREIGN KEY (`article_id`) REFERENCES `article_identity` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table: keywords
-- ----------------------------
CREATE TABLE `keywords` (
  `id`         INT            NOT NULL AUTO_INCREMENT,
  `text`       NVARCHAR(255)  NULL,
  `created_at` DATETIME       NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_keywords_text` (`text`),
  KEY `ix_keywords_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------
-- Table: whitelist_domains
-- ----------------------------
CREATE TABLE `whitelist_domains` (
  `id`        INT           NOT NULL AUTO_INCREMENT,
  `domain`    VARCHAR(255)  NULL,
  `is_active` TINYINT(1)    NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_whitelist_domains_domain` (`domain`),
  KEY `ix_whitelist_domains_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;