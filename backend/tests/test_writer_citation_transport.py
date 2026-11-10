import uuid

import pytest
from pydantic import ValidationError

from app.services.sectional_writer import group_schema,group_message


def schema(identifier):
    return group_schema(['Introduction','Methods'],layout={
        'Introduction':{'citation_required':True},'Methods':{}},allowed_claim_ids={identifier})


def test_evidence_bearing_sections_cannot_be_saved_as_uncited_prose():
    identifier=str(uuid.uuid4())
    with pytest.raises(ValidationError,match='citation_marker'):
        schema(identifier)(sections=[{'heading':'Introduction','body':'A confident summary without any actual source marker.'},
            {'heading':'Methods','body':'The search procedure was recorded by the system.'}])


def test_known_marker_in_subsection_is_preserved_but_a_made_up_marker_is_rejected():
    identifier=str(uuid.uuid4()); marker=f'[[@claim:{identifier}]]'
    payload={'sections':[{'heading':'Introduction','body':'','subsections':[
        {'heading':'Scoped evidence','body':'One supplied study supports a bounded observation under its own conditions. '+marker}]},
        {'heading':'Methods','body':'The recorded search procedure does not need a borrowed citation.'}]}
    value=schema(identifier)(**payload)
    assert marker in group_message(value,['Introduction','Methods']).content
    payload['sections'][0]['subsections'][0]['body']=payload['sections'][0]['subsections'][0]['body'].replace(marker,f'[[@claim:{uuid.uuid4()}]]')
    with pytest.raises(ValidationError,match='supplied'):
        schema(identifier)(**payload)


def test_a_method_only_group_without_literature_does_not_require_a_citation():
    value=group_schema(['Methods'],layout={'Methods':{}},allowed_claim_ids=set())(
        sections=[{'heading':'Methods','body':'Only the recorded study procedure is described here.'}])
    assert value.sections[0].body
