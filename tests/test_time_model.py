from engine import TimeEngine, Packet


def test_offset_initialization():
    engine = TimeEngine()

    # 模拟有 offset（比如板子慢了 3500us）
    pkt = Packet(
        type="TIMING_EVENT",
        source="pps",
        board_time_us=996_500   # ❗不是整秒
    )
    engine.process_packet(pkt)

    assert abs(engine.state.offset_us) > 0


def test_predicted_offset_changes():
    engine = TimeEngine()

    # 模拟带 offset 的 PPS
    engine.process_packet(Packet(type="TIMING_EVENT", source="pps", board_time_us=996_500))
    engine.process_packet(Packet(type="TIMING_EVENT", source="pps", board_time_us=1_996_600))

    out = engine.process_packet(Packet(
        type="SENSOR_EVENT",
        sensor_id="imu",
        board_time_us=2_500_000
    ))

    assert abs(out.offset_us) > 0
