from django.db import models


class AuthorOrganisms(models.Model):
    """
    Author-organization relationship table.
    Note: In the database, the actual primary key is composite (doc_id, author_index, hal_structure_id).
    Here, we use doc_id as the primary key only to ensure Django is happy,
    but we maintain the unique_together relationship with all three columns.
    """
    doc_id = models.BigIntegerField(primary_key=True)
    author_index = models.IntegerField()
    hal_structure_id = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = "author_organisms"
        unique_together = (("doc_id", "author_index", "hal_structure_id"),)


class Authors(models.Model):
    id = models.BigAutoField(primary_key=True)
    doc_id = models.BigIntegerField(blank=True, null=True)
    authfirstname_s = models.CharField(
        db_column="authFirstName_s", max_length=255, blank=True, null=True
    )
    authlastname_s = models.CharField(
        db_column="authLastName_s", max_length=255, blank=True, null=True
    )
    authquality_s = models.CharField(
        db_column="authQuality_s", max_length=255, blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = "authors"

    def __str__(self):
        return f"{self.authfirstname_s or ''} {self.authlastname_s or ''}".strip() or f"Author {self.id}"


class DocumentOrganisms(models.Model):
    id = models.BigAutoField(primary_key=True)
    doc_id = models.BigIntegerField()
    hal_structure_id = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = "document_organisms"

    def __str__(self):
        return f"doc {self.doc_id} – organism {self.hal_structure_id}"


class Documents(models.Model):
    """
    Documentos HAL “planos” en MySQL.
    doc_id es el que luego corresponde con Document.docid (Neo4j) convertido a str.
    """
    id = models.BigAutoField(primary_key=True)
    doc_id = models.BigIntegerField(unique=True)
    halid_s = models.CharField(
        db_column="halId_s", max_length=50, blank=True, null=True
    )
    title = models.CharField(max_length=255, blank=True, null=True)
    abstract = models.TextField(blank=True, null=True)
    discipline = models.CharField(max_length=100, blank=True, null=True)
    domain_codes = models.TextField(blank=True, null=True)
    url_primary = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "documents"

    def __str__(self):
        return self.title or f"Document {self.doc_id}"


class Identifiers(models.Model):
    id = models.BigAutoField(primary_key=True)
    doc_id = models.BigIntegerField()
    doiid_s = models.CharField(
        db_column="doiId_s", max_length=255, blank=True, null=True
    )
    halid_s = models.CharField(
        db_column="halId_s", max_length=255, blank=True, null=True
    )
    isbn = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "identifiers"

    def __str__(self):
        return self.doiid_s or self.halid_s or f"Identifiers {self.id}"


class Journals(models.Model):
    id = models.BigAutoField(primary_key=True)
    doc_id = models.BigIntegerField(blank=True, null=True)
    journalissn_s = models.CharField(
        db_column="journalIssn_s", max_length=50, blank=True, null=True
    )
    journaltitle_s = models.CharField(
        db_column="journalTitle_s", max_length=255, blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = "journals"

    def __str__(self):
        return self.journaltitle_s or f"Journal {self.id}"


class Keywords(models.Model):
    id = models.BigAutoField(primary_key=True)
    doc_id = models.BigIntegerField(blank=True, null=True)
    keyword_s = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "keywords"

    def __str__(self):
        return self.keyword_s or f"Keyword {self.id}"


class Organisms(models.Model):
    hal_structure_id = models.BigIntegerField(primary_key=True)
    structidname_fs = models.CharField(
        db_column="structIdName_fs", max_length=255, blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = "organisms"

    def __str__(self):
        return self.structidname_fs or f"Organism {self.hal_structure_id}"
