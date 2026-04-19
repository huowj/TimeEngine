from engine import TimeEngine, Packet


def test_drift_estimation():
    engine = TimeEngine()

    # simulate drift
    times = [1_000_000, 2_010_000, 3_020_000, 4_030_000]

    for t in times:
        engine.process_packet(Packet(
            type="TIMING_EVENT",
            source="pps",
            board_time_us=t
        ))

    assert abs(engine.state.drift_ppm) > 0


def test_drift_clamped():
    engine = TimeEngine()

    # extreme jump
    engine.process_packet(Packet(type="TIMING_EVENT", source="pps", board_time_us=1_000_000))
    engine.process_packet(Packet(type="TIMING_EVENT", source="pps", board_time_us=10_000_000))

    assert abs(engine.state.drift_ppm) <= engine.max_drift_ppm
