"""RES-77 regression gates: every template/sex, exact insertions, IDs, contacts, immutable output."""

import random
import re

import pytest

from europriv_bench.national_id import parse_national_id
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from klusai.privacy.datasets.data.localepack import _fill
from klusai.privacy.datasets.data.pl_skeletons_v2 import pl_skeleton_v2_pack
from klusai.privacy.datasets.data.ro_documents import TEMPLATES as TOY_TEMPLATES
from klusai.privacy.datasets.data.ro_documents import _fields as toy_fields
from klusai.privacy.datasets.data.ro_skeletons import _fields as patched_fields
from klusai.privacy.datasets.data.ro_skeletons_v2 import LOCALITIES, ro_skeleton_v2_pack
from scripts.generate_realskeleton_v2 import samples, validate_rows, write_once


@pytest.mark.parametrize("pack,country", [(ro_skeleton_v2_pack, "RO"), (pl_skeleton_v2_pack, "PL")])
def test_all_templates_exact_offsets_gender_contacts_and_ids(pack, country):
    sexes = set()
    for seed in range(100):
        fields = pack.fields(random.Random(seed))
        pid = fields["cnp" if country == "RO" else "pesel"][0]
        info = parse_national_id(pid, country)
        assert info.valid
        sexes.add(info.extra["sex"])
        assert fields["dob"][0] == ".".join(reversed(info.extra["birth_date"].split("-")))
        assert 1950 <= int(info.extra["birth_date"][:4]) <= 1995
        assert fields["patient"] != fields["sender"]
        assert fields["phone"] != fields["sender_phone"]
        assert fields["email"] != fields["sender_email"]
        for domain, template in pack.templates:
            text, spans = _fill(template, fields)
            # Compare to the original slot sequence, not re-extracted text used as its own oracle.
            slots = re.findall(r"\{([a-z_]+\d?)\}", template)
            assert len(slots) == len(spans)
            for slot, span in zip(slots, spans, strict=True):
                assert text[span["start"]:span["end"]] == fields[slot][0] == span["value"]
            gold = [s for s in spans if s["label"] != "O"]
            validate_bioes(char_spans_to_bioes(text, [Span(s["start"], s["end"], s["label"]) for s in gold]))
            assert not re.search(r"[^\S\n]+[,.;]", text)
            assert not set("şţŞŢ") & set(text)
            validate_rows([{"text": text, "spans": gold, "country": country, "domain": domain}])
            if domain == "admin":
                assert fields["sender_phone"][0] in text and fields["sender_email"][0] in text
                assert fields["phone"][0] not in text and fields["email"][0] not in text
            if country == "RO":
                assert any(city in fields["address"][0] for city in LOCALITIES.values())
                if domain == "legal" and template.startswith("DECLARAȚIE"):
                    assert ("Subsemnatul" if info.extra["sex"] == "M" else "Subsemnata") in text
                    assert ("contactat la" if info.extra["sex"] == "M" else "contactată la") in text
            elif domain == "admin":
                assert ("Pana wniosku" if info.extra["sex"] == "M" else "Pani wniosku") in text
                assert "Pana/Pani" not in text
            elif domain == "legal" and template.startswith("OŚWIADCZENIE"):
                assert ("niżej podpisany" if info.extra["sex"] == "M" else "niżej podpisana") in text
    assert sexes == {"M", "F"}
    pack.checksum_self_test()


@pytest.mark.parametrize("pack", [ro_skeleton_v2_pack, pl_skeleton_v2_pack])
def test_deterministic_disjoint_review_and_reservation(pack):
    rows = list(pack.generate_dataset(1500, 2026101177))
    assert rows[:5] == list(pack.generate_dataset(5, 2026101177))
    review, heldout, counts = samples(rows)
    assert len(review) == 100 and len(heldout) == 300 and sum(counts.values()) == 1500
    assert {r["source_index"] for r in review}.isdisjoint(r["source_index"] for r in heldout)
    assert {r["text_sha256"] for r in review}.isdisjoint(r["text_sha256"] for r in heldout)
    assert (review, heldout, counts) == samples(rows)
    assert all(sum(r["stratum"] == kind for r in review) == 25 for kind in counts)
    assert all(sum(r["stratum"] == kind for r in heldout) == 75 for kind in counts)


def test_immutable_artifacts_resume_but_refuse_changes(tmp_path):
    path = tmp_path / "test.jsonl"
    write_once(path, b"original\n")
    write_once(path, b"original\n")
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        write_once(path, b"changed\n")
    assert path.read_bytes() == b"original\n"


def test_validation_rejects_corrupt_national_id():
    row = next(r for r in ro_skeleton_v2_pack.generate_dataset(20, 9) if r["domain"] == "clinical")
    row["country"] = "RO"
    span = next(s for s in row["spans"] if s["label"] == "NATIONAL_ID")
    pos = span["end"] - 1
    row["text"] = row["text"][:pos] + str((int(row["text"][pos]) + 1) % 10) + row["text"][pos + 1:]
    with pytest.raises(AssertionError):
        validate_rows([row])


def test_supplied_patch_gender_and_sender_regressions():
    female = None
    for seed in range(100):
        fields = toy_fields(random.Random(seed))
        if fields["subsemnat"][0] == "Subsemnata":
            female = fields
            break
    assert female is not None
    rendered = [_fill(template, female)[0] for _, template in TOY_TEMPLATES]
    assert "Subsemnata" in rendered[0] and "domiciliată" in rendered[0]
    assert "internată" in rendered[2] and "domiciliată" in rendered[3]
    fields = patched_fields(random.Random(0))
    assert fields["sender_phone"] != fields["phone"]
    assert fields["sender_email"] != fields["email"]


def test_polish_wroclaw_euphony():
    hospitals = {pl_skeleton_v2_pack.fields(random.Random(seed))["hospital"][0] for seed in range(100)}
    assert "Centrum Medyczne we Wrocławiu" in hospitals
    assert "Centrum Medyczne w Wrocławiu" not in hospitals
