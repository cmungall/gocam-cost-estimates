"""End-to-end test of the DuckDB build on a tiny 2-version fixture.

Verifies that the OWL-axiom blank node is skolemized to a stable IRI across
versions (so a date change shows as 1 removed + 1 added, not full churn) and
that triple add/remove counts are correct.
"""
import duckdb

from gocam_cost import config as C
from gocam_cost import db
from gocam_cost.extract import extract_to_parquet
from gocam_cost.fetch import _cache_path
from gocam_cost.gitdata import Version

AXIOM = """_:x a <http://www.w3.org/2002/07/owl#Axiom> ;
    <http://www.w3.org/2002/07/owl#annotatedSource> <http://model.geneontology.org/M/a> ;
    <http://www.w3.org/2002/07/owl#annotatedProperty> <http://purl.obolibrary.org/obo/BFO_0000050> ;
    <http://www.w3.org/2002/07/owl#annotatedTarget> <http://model.geneontology.org/M/b> ;
    <http://purl.org/dc/elements/1.1/date> "{date}"^^<http://www.w3.org/2001/XMLSchema#string> ."""

BASE = """<http://model.geneontology.org/M> a <http://www.w3.org/2002/07/owl#Ontology> .
<http://model.geneontology.org/M/a> <http://purl.obolibrary.org/obo/BFO_0000050> <http://model.geneontology.org/M/b> .
"""

V1 = (BASE + AXIOM.format(date="2025-01-01")).encode()
V2 = (BASE + AXIOM.format(date="2025-01-02")
      + '\n<http://model.geneontology.org/M/a> <http://purl.obolibrary.org/obo/RO_0002333> <http://model.geneontology.org/M/c> .\n').encode()


def _write_blob(oid: str, data: bytes) -> None:
    p = _cache_path(oid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def test_skolem_stability_and_diff(tmp_path):
    _write_blob("testfixv1", V1)
    _write_blob("testfixv2", V2)
    versions = [
        Version("M", "sha1", "2025-01-01T10:00:00-07:00", "testfixv1"),
        Version("M", "sha2", "2025-01-02T10:00:00-07:00", "testfixv2"),
    ]
    raw = tmp_path / "raw"
    extract_to_parquet(versions, raw)
    dbp = tmp_path / "t.duckdb"
    db.build(versions, raw, dbp)

    con = duckdb.connect(str(dbp), read_only=True)
    rows = con.execute(
        "SELECT ord, n_triples, triples_added, triples_removed FROM versions ORDER BY ord"
    ).fetchall()
    # v1: 7 triples all added; v2: 8 triples, +2 (new edge + new date) -2... -1 (old date)
    assert rows[0] == (1, 7, 7, 0)
    assert rows[1] == (2, 8, 2, 1)
    # the axiom skolem IRI is identical across both versions (stable identity)
    n_skolem = con.execute(
        "SELECT count(DISTINCT subject) FROM triples WHERE subject LIKE 'urn:skolem:axiom:%'"
    ).fetchone()[0]
    assert n_skolem == 1
    assert con.execute("SELECT count(*) FROM triples WHERE subject LIKE 'urn:bnode:%'").fetchone()[0] == 0
    con.close()
