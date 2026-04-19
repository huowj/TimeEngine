from engine import TimeEngine, Packet


def test_pps_outlier_rejected():
    engine = TimeEngine()

    # normal PPS
    for i in range(1, 4):
        engine.process_packet(Packet(
            type="TIMING_EVENT",
            source="pps",
            board_time_us=i * 1_000_000
        ))

    offset_before = engine.state.offset_us

    # big outlier
    engine.process_packet(Packet(
        type="TIMING_EVENT",
        source="pps",
        board_time_us=10_000_000
    ))

    offset_after = engine.state.offset_us

    # offset should not jump wildly
    assert abs(offset_after - offset_before) < 2000
