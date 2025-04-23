# Queue Accepter

A lightweight GUI application for automatically detecting and clicking a game's “Accept” button (e.g., LoL queue pop), using ORB feature matching. Optionally notifies you on Discord when a queue pops.

---

## Quick Start

1. **Clone or download** this repo and `cd` into it.  
2. **Install dependencies**:
   ```bash
   pip install opencv-python numpy pyautogui pillow requests
   ```
3. **Configure `config.json`** (optional fields shown):
   ```json
   {
     "templates_folder": "templates",
     "raw_roi": [0.4, 0.75, 0.2, 0.2],
     "min_matches": 12,
     "discord_webhook_url": "",          # Optional: your Discord webhook URL
     "discord_user_id": ""               # Optional: your Discord user ID
   }
   ```
4. **Populate templates**: place one or more button screenshots (`*.png`) in the `templates/` folder.  
5. **Run the app**:
   ```bash
   python queue_auto_accept.py
   ```

---

## Basic Usage

Once the GUI launches:

1. **Select ROI**  
   - Click **Select ROI**, drag a box over your game's accept button area, then press **ENTER** or **SPACE** to confirm. (only need to do once, it saves the configuration file) 
2. **Toggle Options**  
   - **Debug**: show live scanning algorithm view and overlay.  
   - **Sound**: play a beep on click.  
   - **Notify**: send a Discord ping (requires webhook setup).  
3. **Adjust Sensitivity**  
   - Use the **Min matches** slider to set how many ORB keypoint matches are required.  
   - The numeric value beside the slider shows the current setting.  
4. **Start/Pause/Quit**  
   - **Start**: begin detection.  
   - **Pause**: pause detection.  
   - **Quit**: exit the application.  
5. **View status**  
   - The status line displays **Current matches: X** in real-time.

---

## Configuration

### `templates_folder`
- Directory containing one or more template images of the accept button.  
- The app attempts matching each frame against *all* templates; clicks when any template has ≥ `min_matches`.

### `raw_roi`
- Normalized `[x, y, width, height]` (0–1) specifying the screen region to capture.  
- Saved automatically when you confirm via **Select ROI**.

### `min_matches`
- Number of ORB feature matches required to trigger a click.  
- **Increase** to reduce false positives; **decrease** to catch subtler pops.

---

## Optional: Discord Notifications

Receive a ping on Discord when a queue pops:

1. **Create or copy a Webhook**  
   - In Discord: **Server Settings → Integrations → Webhooks**.  
   - Copy an existing Webhook URL, or click **New Webhook**, select a channel, name it, and copy the URL.  
2. **Find your Discord User ID**  
   - Enable **Developer Mode** in Discord (User Settings → Advanced).  
   - Right-click your username in a server and select **Copy ID**.  
3. **Update `config.json`**:  
   ```json
   {
     "discord_webhook_url": "https://discord.com/api/webhooks/…",
     "discord_user_id": "123456789012345678"
   }
   ```  
4. **Enable** the **Notify** checkbox in the GUI.

---

## Advanced Usage & Tuning

- **Multiple Templates**: include different scale/UI variants to improve detection.  
- **ROI Padding**: add margin if matches drop near edges (ORB needs context).  
- **Debug Overlay**: watch **Debug** window to fine-tune `min_matches`.  
- **Logging**: see `queue_accept.log` for timestamps, match counts, and errors.

---

## Troubleshooting

- **Empty Screenshots**: verify ROI selection is on-screen and non-zero.  
- **Slow Performance**: reduce template count or raise `min_matches`.  
- **False Positives**: increase `min_matches` or remove noisy templates.

---