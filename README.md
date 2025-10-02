# Minut4backers Minut Point HACS Integration

Integrate your Minut Point devices into Home Assistant. This custom integration polls the Minut REST API to retrieve temperature, humidity and noise level readings and exposes motion and alarm events as binary sensors. The integration is installable through [HACS](https://hacs.xyz/) and does **not** require the official enterprise API credentials. The name Minut4backers is because Minut has been unfair to it's original Kickstarter backers who helped the company get started with it's first device. Don't be evil Minut. Do not make promises you can't keep.

## Features

- Discover all Minut Point devices associated with your account
- Expose sensors for temperature (°C), humidity (%) and noise level (dBA)
- Expose binary sensors for motion (`activity_detected`) and alarm events (`alarm_heard`, `avg_sound_high`, `sound_level_dropped_normal`)
- Support token refresh when a refresh token is provided
- Configurable via the Home Assistant UI

## Installation

1. **Add the repository to HACS**

   - Open HACS in Home Assistant and navigate to **Integrations**.
   - Click the three‑dot menu in the top right and select **Custom repositories**.
   - Enter the URL of this repository and select **Integration** as the category.
   - Click **Add**. The integration will now be available in the HACS store.

2. **Install the integration**

   - Search for **Minut Point (HACS)** in the HACS integrations list.
   - Click **Download** and follow the on‑screen instructions.
   - Restart Home Assistant when prompted.

3. **Configure the integration**

   - Navigate to **Settings → Devices & Services** and click **Add Integration**.
   - Search for and select **Minut Point (HACS)**.
   - You have two options for authentication:

     **a. Provide tokens and user ID** – recommended if you already use the Minut web dashboard. The integration uses the same tokens as the web dashboard.

     1. Log in to [Minut web](https://web.minut.com) in your browser and open the developer tools (usually `F12`).
     2. Go to the **Network** tab and refresh the page. Look for a request to `https://api.minut.com/draft1/auth/token`. The response JSON contains `access_token`, `refresh_token` and `user_id` fields【309709768529123†L230-L263】.
     3. Copy the values of **User ID**, **Access Token** and **Refresh Token**.
     4. In the Home Assistant configuration form, paste these values into the corresponding fields. You may leave the username and password fields blank.
     5. Click **Submit**. The integration will validate the tokens and create devices and sensors.

     **b. Provide username and password** – the integration will use the password grant to obtain tokens for you. Enter your Minut account username (email) and password in the form. Leave the access token, refresh token and user ID fields blank. On submission the integration authenticates with the Minut API to retrieve the tokens.

After configuration, your Minut devices will appear under **Settings → Devices & Services**. Each device has temperature, humidity and noise sensors as well as motion and alarm binary sensors.

## Entities

### Sensors

| Entity                 | Description                                 | Unit |
| ---------------------- | ------------------------------------------- | ---- |
| `<device> Temperature` | Latest temperature reading from the Point   | °C   |
| `<device> Humidity`    | Latest humidity reading from the Point      | %    |
| `<device> Noise Level` | Latest average noise level (sound pressure) | dBA  |

The integration polls the Minut API every 15 seconds and updates these sensor values accordingly【309709768529123†L230-L263】. If no recent value is available, the entity will show `unknown`.

### Binary Sensors

| Entity | Device class | Trigger conditions |
| --- | --- | --- |
| `<device> Motion` | `motion` | Turns on when a recent `activity_detected` event is present in the timeline【186261486540357†L90-L121】 |
| `<device> Alarm` | `sound` | Turns on when `alarm_heard`, `avg_sound_high` or `sound_level_dropped_normal` events occur |

Binary sensors rely on timeline events returned by the API【56322294618823†L266-L294】. When an event is detected within the last two minutes, the corresponding sensor will be `on` for one polling interval.

## Example automation

You can use the entities created by this integration in your automations. For example, turn on a light when motion is detected and it is dark:

```yaml
automation:
  - alias: "Turn on hallway light when Minut detects motion"
    trigger:
      - platform: state
        entity_id: binary_sensor.living_room_point_motion
        to: "on"
    condition:
      - condition: state
        entity_id: light.hallway
        state: "off"
    action:
      - service: light.turn_on
        entity_id: light.hallway
```

## Troubleshooting

- **Invalid authentication** – make sure the user ID and tokens are copied exactly as provided by the web dashboard. Tokens are long strings; avoid spaces or hidden characters. If using username/password, verify the credentials by logging into the Minut app.
- **Cannot connect** – the integration uses the same API endpoints as the web dashboard. If the Minut API is down, the integration will fail to authenticate or update. Try again later.
- **No devices appear** – ensure the account used actually has Point devices registered. The integration will show no entities if none are returned.

If you encounter issues, enable debug logging for the integration by adding the following to your `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.minut4backers: debug
```

## Disclaimer

This integration is an unofficial community project and is not endorsed by Minut. It relies on the same endpoints used by the Minut web dashboard and therefore may break if Minut changes their API. Which they will probably do soon. Use at your own risk. If you have an enterprise subscription with official API access, you're better of using the official Home Assistant **Point** integration instead.
