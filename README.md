# Haier AC Local (uSDK) for Home Assistant

Local control (no cloud, no account) of Haier air conditioners whose Wi-Fi module
speaks the plaintext uSDK protocol on TCP port **56800** (e.g. `uplus-haier-ac-*`).

- `climate` entity: on/off, mode (auto/cool/heat/fan/dry), target temperature,
  fan (auto/low/medium/high/quiet/turbo), vertical swing
- Local polling every 30 s; one short TCP connection per operation

## Install
HACS -> Custom repositories -> add this repo (Integration), or copy
`custom_components/haier_local` to your HA `config/custom_components`, restart HA.
Then Settings -> Devices & Services -> Add Integration -> *Haier AC Local*:
name, IP address, MAC address.

## Notes
- The module serves one TCP client at a time: close the Haier phone app.
- Modules that encrypt the LAN protocol (require a cloud "localkey") are not supported.
- Status/command layout follows
  [bwitosze/haier-smartair2-cloud-for-homeassistant](https://github.com/bwitosze/haier-smartair2-cloud-for-homeassistant) (MIT).
- Unofficial; not affiliated with Haier. Use at your own risk.
