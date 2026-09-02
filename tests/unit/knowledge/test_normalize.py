from innobrain.knowledge.normalize import normalize_arabic_retrieval


def test_arabic_normalization_preserves_meaningful_letters() -> None:
    source = "  الـSession في القاعـة رقم ٣ — إِسأل أحمد  "

    assert normalize_arabic_retrieval(source) == "الsession في القاعة رقم 3 — اسال احمد"


def test_arabic_normalization_retains_teh_marbuta() -> None:
    assert normalize_arabic_retrieval("القاعَة") == "القاعة"
