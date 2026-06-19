from gocam_cost.extract import triples_from_bytes

# Minimal long-form Turtle with an owl:Axiom reification (blank node), like minerva output.
TTL = b"""
<http://model.geneontology.org/M1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Ontology> .
<http://model.geneontology.org/M1/a> <http://purl.obolibrary.org/obo/BFO_0000050> <http://model.geneontology.org/M1/b> .
<http://model.geneontology.org/M1> <http://purl.org/dc/elements/1.1/title> "My model"^^<http://www.w3.org/2001/XMLSchema#string> .
_:ax1 a <http://www.w3.org/2002/07/owl#Axiom> ;
    <http://www.w3.org/2002/07/owl#annotatedSource> <http://model.geneontology.org/M1/a> ;
    <http://www.w3.org/2002/07/owl#annotatedProperty> <http://purl.obolibrary.org/obo/BFO_0000050> ;
    <http://www.w3.org/2002/07/owl#annotatedTarget> <http://model.geneontology.org/M1/b> ;
    <http://purl.org/dc/elements/1.1/date> "2025-01-01"^^<http://www.w3.org/2001/XMLSchema#string> .
"""


def test_parses_all_triples():
    rows = list(triples_from_bytes(TTL))
    assert len(rows) == 8


def test_blank_node_subject_flagged():
    rows = list(triples_from_bytes(TTL))
    bnode_rows = [r for r in rows if r[1]]  # subj_is_bnode
    assert len(bnode_rows) == 5             # the 5 triples on _:ax1
    assert all(not r[0].startswith("_:") for r in bnode_rows)  # bare label, no prefix


def test_literal_objects_flagged():
    rows = list(triples_from_bytes(TTL))
    title = [r for r in rows if r[3].startswith('"My model"')]
    assert len(title) == 1 and title[0][4] is True  # obj_is_literal
