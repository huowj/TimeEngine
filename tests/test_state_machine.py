from engine import TimeEngine, Packet


def test_lock_transition():
    engine = TimeEngine()

    for i in range(1, 6):
        engine.process_packet(Packet(
            type="TIMING_EVENT",
            source="pps",
            board_time_us=i * 1_000_000
        ))

    assert engine.state.sync_state == "LOCKED"


def test_holdover_transition():
    engine = TimeEngine()

    # lock
    for i in range(1, 6):
        engine.process_packet(Packet(
            type="TIMING_EVENT",
            source="pps",
            board_time_us=i * 1_000_000
        ))

    # simulate gap
    engine.process_packet(Packet(
        type="SENSOR_EVENT",
        sensor_id="imu",
        board_time_us=10_000_000
    ))

    assert engine.state.sync_state in ("HOLDOVER", "LOST")
