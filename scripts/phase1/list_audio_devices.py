from innobrain.audio import get_default_device_indices, list_audio_devices


def main() -> int:
    input_default, output_default = get_default_device_indices()

    print(f"Default input: {input_default}")
    print(f"Default output: {output_default}")
    print()

    for device in list_audio_devices():
        roles = []
        if device.can_capture:
            roles.append("INPUT")
        if device.can_playback:
            roles.append("OUTPUT")

        print(
            f"[{device.index}] {'/'.join(roles) or 'NONE'} | "
            f"{device.name} | default_sr={device.default_sample_rate}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
