from engine import TimeEngine, Packet


def pps(board_time_us):
    return Packet(
        type="TIMING_EVENT",
        source="pps",
        board_time_us=board_time_us,
    )


def sensor(board_time_us):
    return Packet(
        type="SENSOR_EVENT",
        sensor_id="imu",
        board_time_us=board_time_us,
    )


def lock_engine(engine: TimeEngine):
    engine.process_packet(pps(996_500))
    engine.process_packet(pps(1_996_512))
    engine.process_packet(pps(2_996_524))
    engine.process_packet(pps(3_996_536))


# ============================================================
# 1. LOCKED 不应在 jitter 很大时进入
# ============================================================

def test_should_not_lock_when_pps_jitter_is_large():
    engine = TimeEngine()

    # 第一个 PPS 建立 anchor
    engine.process_packet(pps(996_500))

    # 后续 PPS interval 明显不是 1s，jitter 很大
    engine.process_packet(pps(1_996_500 + 800))
    engine.process_packet(pps(2_996_500 - 900))
    engine.process_packet(pps(3_996_500 + 1000))
    engine.process_packet(pps(4_996_500 - 850))

    assert engine.state.sync_state.value != "LOCKED"


# ============================================================
# 2. confidence 在 HOLDOVER 持续下降
# ============================================================

def test_confidence_decreases_during_holdover():
    engine = TimeEngine()
    lock_engine(engine)

    assert engine.state.sync_state.value == "LOCKED"

    # 超过 holdover_timeout，进入 HOLDOVER
    out1 = engine.process_packet(sensor(5_700_000))
    c1 = out1.confidence

    out2 = engine.process_packet(sensor(6_700_000))
    c2 = out2.confidence

    out3 = engine.process_packet(sensor(7_700_000))
    c3 = out3.confidence

    assert out1.sync_state == "HOLDOVER"
    assert c1 > c2 > c3


# ============================================================
# 3. relock 后 confidence 恢复
# ============================================================

def test_confidence_recovers_after_relock():
    engine = TimeEngine()
    lock_engine(engine)

    # 进入 HOLDOVER
    holdover_out = engine.process_packet(sensor(5_700_000))
    holdover_conf = holdover_out.confidence

    assert holdover_out.sync_state == "HOLDOVER"

    # PPS 恢复，并连续稳定
    engine.process_packet(pps(5_996_560))
    engine.process_packet(pps(6_996_572))
    relock_out = engine.process_packet(pps(7_996_584))

    assert relock_out.sync_state == "LOCKED"
    assert relock_out.confidence > holdover_conf


# ============================================================
# 4. drift 变化时 offset 收敛行为
# ============================================================

def test_offset_converges_after_drift_change():
    engine = TimeEngine()

    # 初始稳定 drift：每秒 board_time 增加约 1_000_012 us
    engine.process_packet(pps(996_500))
    engine.process_packet(pps(1_996_512))
    engine.process_packet(pps(2_996_524))
    engine.process_packet(pps(3_996_536))

    old_offset = engine.state.offset_us

    # drift jump：后续变成每秒约 1_000_040 us
    engine.process_packet(pps(4_996_576))
    engine.process_packet(pps(5_996_616))
    engine.process_packet(pps(6_996_656))
    engine.process_packet(pps(7_996_696))

    new_offset = engine.state.offset_us

    # offset 应该发生变化，说明模型在重新收敛
    assert abs(new_offset - old_offset) > 1.0

    # drift 应该朝新的方向变化
    assert abs(engine.state.drift_ppm) > 0.0
