from engine import TimeEngine, Packet


def test_holdover_prediction_continues():
    engine = TimeEngine()

    # lock
    for i in range(1, 6):
        engine.process_packet(Packet(
            type="TIMING_EVENT",
            source="pps",
            board_time_us=i * 1_000_000
        ))

    last = None

    # no PPS
    for t in range(6, 10):
        out = engine.process_packet(Packet(
            type="SENSOR_EVENT",
            sensor_id="imu",
            board_time_us=t * 1_000_000
        ))

        if last:
            assert out.timestamp_corrected_us > last

        last = out.timestamp_corrected_us
