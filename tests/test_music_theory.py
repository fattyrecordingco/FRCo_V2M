from v2m.music_theory import infer_best_key, parse_key, snap_pitch_to_scale


def test_parse_extended_scale_mode() -> None:
    tonic, mode = parse_key("A harmonic minor")
    assert tonic == "A"
    assert mode == "harmonic minor"


def test_snap_pitch_to_scale_keeps_in_range() -> None:
    snapped = snap_pitch_to_scale(61, "C major")
    assert 0 <= snapped <= 127
    assert snapped % 12 in {0, 2, 4, 5, 7, 9, 11}


def test_infer_best_key_from_major_scale_pitch_set() -> None:
    key, score = infer_best_key([60, 62, 64, 65, 67, 69, 71, 72])
    assert key.endswith("major")
    assert score >= 0.75
