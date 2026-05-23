"""Tests for the Stage 2 ingestion pipeline.

Covers:
    - Citation/ID builder helpers
    - Recursive text splitter behaviour (graceful fallback if langchain missing)
    - XML parsing of a synthetic fragment (lxml required)
    - PDF module detection (no PDF I/O — pure filename logic)
"""

from __future__ import annotations

import pytest

from backend.graph.ingest_xml import (
    LegislationSource,
    _build_cite,
    _build_id,
    _maybe_chunk,
    parse_legislation_xml,
)
from backend.graph.extract_pdfs import _detect_module, _slug


# Synthetic fragments match the *actual* legislation.gov.uk schema: titles
# live on `P1group`, the provision body is `P1`, content is in `P1para/Text`.
# For Acts, `Pnumber` is often empty so the number lives in the `id` attribute.

_SYNTHETIC_ACT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation">
  <Primary>
    <Body>
      <P1group>
        <Title>General prohibition</Title>
        <P1 id="section-19">
          <Pnumber/>
          <P1para>
            <Text>The general prohibition makes it an offence to carry on a regulated activity in the United Kingdom unless one is an authorised person or an exempt person. This rule sits at the heart of the regulatory perimeter.</Text>
          </P1para>
        </P1>
      </P1group>
      <P1group>
        <Title>Authorised persons</Title>
        <P1 id="section-20">
          <Pnumber/>
          <P1para>
            <Text>Authorised persons may carry on regulated activities to the extent provided for in their Part 4A permission, subject to threshold conditions and the relevant rule books.</Text>
          </P1para>
        </P1>
      </P1group>
    </Body>
  </Primary>
</Legislation>
"""


_SYNTHETIC_SI_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Legislation xmlns="http://www.legislation.gov.uk/namespaces/legislation">
  <Secondary>
    <Body>
      <P1group>
        <Title>Customer due diligence measures</Title>
        <P1 id="regulation-27">
          <Pnumber>27</Pnumber>
          <P1para>
            <Text>A relevant person must apply customer due diligence measures when establishing a business relationship or carrying out an occasional transaction, and at appropriate moments thereafter as part of ongoing monitoring.</Text>
          </P1para>
        </P1>
      </P1group>
    </Body>
  </Secondary>
</Legislation>
"""


def _src_fsma():
    return LegislationSource(
        slug="fsma_2000",
        url="",
        document="FSMA 2000",
        short_doc="FSMA 2000",
        regulator="HMT",
        domain="FSMA",
        cite_kind="s",
    )


def _src_mlr():
    return LegislationSource(
        slug="mlr_2017",
        url="",
        document="MLR 2017",
        short_doc="MLR 2017",
        regulator="HMT",
        domain="AML",
        cite_kind="reg",
    )


def test_build_cite_uses_doc_and_kind():
    src = _src_fsma()
    assert _build_cite(src, "19") == "FSMA 2000 s.19"
    src = _src_mlr()
    assert _build_cite(src, "27") == "MLR 2017 reg.27"


def test_build_id_is_safe_and_unique():
    src = _src_fsma()
    a = _build_id(src, "19")
    b = _build_id(src, "20")
    assert a != b
    assert a.startswith("FSMA2000_")


def test_chunker_short_text_returns_one():
    chunks = _maybe_chunk("short text")
    assert chunks == ["short text"]


def test_chunker_long_text_splits():
    long_text = ("paragraph A. " * 200).strip()  # ~2600 chars, well above 1500
    chunks = _maybe_chunk(long_text)
    assert len(chunks) >= 2
    assert all(len(c) <= 1600 for c in chunks)  # allow small overshoot for word boundaries


def test_parse_act_xml_yields_provisions():
    pytest.importorskip("lxml")
    src = _src_fsma()
    provisions = list(parse_legislation_xml(_SYNTHETIC_ACT_XML, src))
    assert len(provisions) == 2
    cites = {p["cite"] for p in provisions}
    assert cites == {"FSMA 2000 s.19", "FSMA 2000 s.20"}
    p19 = next(p for p in provisions if p["cite"] == "FSMA 2000 s.19")
    assert "general prohibition" in p19["text"].lower()
    assert p19["title"] == "General prohibition"
    assert p19["document"] == "FSMA 2000"
    assert p19["regulator"] == "HMT"


def test_parse_si_xml_yields_regulations():
    pytest.importorskip("lxml")
    src = _src_mlr()
    provisions = list(parse_legislation_xml(_SYNTHETIC_SI_XML, src))
    assert len(provisions) == 1
    p = provisions[0]
    assert p["cite"] == "MLR 2017 reg.27"
    assert p["title"] == "Customer due diligence measures"
    assert "due diligence" in p["text"].lower()


def test_pdf_detect_module_fca_sourcebook():
    mod, reg, prefix = _detect_module("COBS.pdf", "fca")
    assert mod == "COBS"
    assert reg == "FCA"
    assert prefix == "COBS"


def test_pdf_detect_module_pra():
    mod, reg, prefix = _detect_module("some-rule.pdf", "pra_pdfs")
    assert mod == "PRA"
    assert reg == "PRA"


def test_pdf_detect_module_unknown_fca():
    # An FCA-folder PDF whose name isn't a known sourcebook
    mod, reg, prefix = _detect_module("misc-doc.pdf", "fca")
    assert reg == "FCA"


def test_slug_strips_punctuation():
    assert _slug("annex-i-to-chapter-5-of-the-securitisation-part.pdf") == "annex_i_to_chapter_5_of_the_securitisation_part"
