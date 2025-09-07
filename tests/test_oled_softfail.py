from momo.apps.momo_oled import try_init_display, render_status, OledStatus


def test_oled_soft_fail():
    device = try_init_display()
    status = OledStatus(mode="passive", channel=None, handshakes=0, files=0, temperature_c=None)
    # Should not raise if device is None
    render_status(device, status)


