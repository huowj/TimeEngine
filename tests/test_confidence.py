from engine import TimeEngine, Packet


def test_confidence_increases_when_locked():
    engine = TimeEngine()

    for i in range(1, 6):
        engine.process_packet(Packet(
            type="TIMING_EVENT",
            source="pps",
            board_time_us=i * 1_000_000
        ))

    assert engine.state.confidence > 0.5


def test_confidence_decreases_in_holdover():
    engine = TimeEngine()

    # lock
    for i in range(1, 6):
        engine.process_packet(Packet(
            type="TIMING_EVENT",
            source="pps",
            board_time_us=i * 1_000_000
        ))

    conf_before = engine.state.confidence

    # simulate gap
    engine.process_packet(Packet(
        type="SENSOR_EVENT",
        sensor_id="imu",
        board_time_us=10_000_000
    ))

    conf_after = engine.state.confidence

    assert conf_after < conf_before
