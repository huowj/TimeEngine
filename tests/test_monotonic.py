from engine import TimeEngine, Packet


def test_corrected_monotonic():
    engine = TimeEngine()

    outputs = []

    for i in range(100):
        pkt = Packet(
            type="SENSOR_EVENT",
            sensor_id="imu",
            board_time_us=i * 1000
        )
        out = engine.process_packet(pkt)
        outputs.append(out.timestamp_corrected_us)

    assert all(x <= y for x, y in zip(outputs, outputs[1:]))


def test_board_time_non_monotonic_protection():
    engine = TimeEngine()

    engine.process_packet(Packet(type="SENSOR_EVENT", sensor_id="imu", board_time_us=1000))
    engine.process_packet(Packet(type="SENSOR_EVENT", sensor_id="imu", board_time_us=900))

    assert engine.state.last_board_time_us >= 1000
