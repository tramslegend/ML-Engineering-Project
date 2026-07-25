"""
§10.3 PII red team: adversarial cases the detector must survive. Each case
notes which entity SHOULD be found and why it's hard — used by score_pii.py
in "red team mode" to report recall broken out by adversarial category
rather than pooled with the easy synthetic corpus.

Run: python generate_pii_red_team.py > pii_red_team.jsonl
"""
import json

CASES = [
    # NIK with spaces or dots
    {"id": "rt_nik_spaced", "text": "NIK saya 32 71 01 23 03 90 00 21 kalau tidak salah.",
     "adversarial_category": "nik_spaced", "pii_spans": [{"entity_type": "NIK", "text": "32 71 01 23 03 90 00 21"}]},
    {"id": "rt_nik_dotted", "text": "Nomor identitas: 3271.0123.0390.0021 ya pak.",
     "adversarial_category": "nik_dotted", "pii_spans": [{"entity_type": "NIK", "text": "3271.0123.0390.0021"}]},

    # phone numbers written as words
    {"id": "rt_phone_words", "text": "Nomor saya nol delapan satu dua tiga empat lima enam tujuh delapan sembilan.",
     "adversarial_category": "phone_as_words", "pii_spans": [{"entity_type": "PHONE", "text": "nol delapan satu dua tiga empat lima enam tujuh delapan sembilan"}]},

    # names embedded mid-sentence without capitalization
    {"id": "rt_name_lowercase", "text": "saya adalah budi santoso dan saya ingin komplain soal kartu saya.",
     "adversarial_category": "name_no_capitalization", "pii_spans": [{"entity_type": "PERSON_NAME", "text": "budi santoso"}]},

    # addresses in non-standard order
    {"id": "rt_address_nonstandard", "text": "Kebayoran Baru, dekat Kelurahan Senayan, di jalan yang namanya Sudirman itu, nomor 5, itu rumah saya.",
     "adversarial_category": "address_nonstandard_order", "pii_spans": [{"entity_type": "ADDRESS", "text": "Kebayoran Baru, dekat Kelurahan Senayan, di jalan yang namanya Sudirman itu, nomor 5"}]},

    # account numbers split across lines
    {"id": "rt_account_split_lines", "text": "Nomor rekening saya\n1234-5678\n-90 kalau digabung.",
     "adversarial_category": "account_split_lines", "pii_spans": [{"entity_type": "BANK_ACCOUNT", "text": "1234-5678\n-90"}]},

    # mononym names
    {"id": "rt_mononym", "text": "Nama saya Sukarno, saya ingin melaporkan masalah transaksi.",
     "adversarial_category": "mononym", "pii_spans": [{"entity_type": "PERSON_NAME", "text": "Sukarno"}]},

    # nickname references
    {"id": "rt_nickname", "text": "Panggil saja saya Budi, itu keluhan dari si Budi soal kartu ATM-nya.",
     "adversarial_category": "nickname_reference", "pii_spans": [{"entity_type": "PERSON_NAME", "text": "Budi"}]},

    # NIK embedded in a run-on sentence without a labelling cue
    {"id": "rt_nik_no_cue", "text": "Saya sudah coba hubungi tapi 3271012303900021 itu nomor yang saya pakai daftar dulu.",
     "adversarial_category": "nik_no_context_cue", "pii_spans": [{"entity_type": "NIK", "text": "3271012303900021"}]},

    # card number with dashes and mid-sentence
    {"id": "rt_card_dashed", "text": "kartu saya yang nomornya 4532-0151-1283-0366 itu tiba-tiba tidak aktif",
     "adversarial_category": "card_dashed", "pii_spans": [{"entity_type": "CARD_NUMBER", "text": "4532-0151-1283-0366"}]},
]

if __name__ == "__main__":
    for case in CASES:
        print(json.dumps(case, ensure_ascii=False))
