# Monocle Cloud Status (Home Assistant)
Unofficial read-only Home Assistant integration for viewing hot water status from a Monocle-compatible installation. Not affiliated with or endorsed by the vendor.

## Features

* Live power telemetry (mains, solar, house, battery)
* Device online status
* Hot water state visibility
* Hot water override control (on/off with duration)
* Native Home Assistant config flow (UI setup)
* Uses official app authentication (no hardcoded credentials)

## Installation (HACS)

1. Open HACS
2. Go to **Integrations**
3. Click **⋮ → Custom repositories**
4. Add this repository URL
5. Select **Integration**
6. Install **Monocle Cloud Status**
7. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services**
2. Click **Add Integration**
3. Search for **Monocle Cloud Status**
4. Enter your Monocle account credentials

## Entities

### Sensors

* Mains Power
* Solar Power
* House Power
* Battery Power
* Device Status
* Hot Water State
* Override Mode
* Override Valid Until

### Controls

* Override Mode (Select)
* Override Duration (Number)
* Apply Override (Button)
* Clear Override (Button)

## Disclaimer

This project is not affiliated with Catch Power or Monocle.

Use at your own risk.

## License

This project is licensed under CC BY-NC 4.0.
