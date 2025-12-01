import streamlit as st
import subprocess
import os
import sys
import time

# --- 1. AUTO-INSTALL DEPENDENCIES (Fallback) ---
# This ensures the app doesn't crash if requirements.txt is ignored
try:
    from pyngrok import ngrok
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyngrok"])
    from pyngrok import ngrok

# --- CONFIGURATION ---
ISO_FILE = "android-x86-4.4-r5.iso"
ISO_URL = "https://sourceforge.net/projects/android-x86/files/Release%204.4/android-x86-4.4-r5.iso/download"
NOVNC_PORT = 6080

st.set_page_config(layout="wide", page_title="Android 4.4.4 Cloud")
st.title("📱 Android 4.4.4 (KitKat) - Safe Mode")

# --- 2. SETUP FUNCTIONS ---
def setup_environment():
    status = st.empty()
    
    # Download Android ISO if missing
    if not os.path.exists(ISO_FILE):
        status.info("⬇️ Downloading Android ISO (approx 30s)...")
        subprocess.run(["wget", "-q", "-O", ISO_FILE, ISO_URL], check=True)
    
    # Download noVNC Web Interface if missing
    if not os.path.exists("noVNC-1.4.0"):
        status.info("⬇️ Installing noVNC Web Interface...")
        subprocess.run("wget -q -O novnc.zip https://github.com/novnc/noVNC/archive/refs/tags/v1.4.0.zip", shell=True)
        subprocess.run("unzip -q novnc.zip && rm novnc.zip", shell=True)
        # Link the special vnc.html to index.html so it loads automatically
        if os.path.exists("noVNC-1.4.0/index.html"):
            os.remove("noVNC-1.4.0/index.html")
        subprocess.run("ln -s vnc.html noVNC-1.4.0/index.html", shell=True)
    
    status.empty()

def kill_existing_processes():
    # Kill any stuck processes to free up ports
    subprocess.run("pkill -f qemu-system-i386", shell=True)
    subprocess.run("pkill -f websockify", shell=True)

def start_system():
    # 1. Authenticate Ngrok using Secrets
    # This is safe because the token isn't in the code
    if "NGROK_AUTH_TOKEN" not in st.secrets:
        st.error("❌ Error: NGROK_AUTH_TOKEN not found in Secrets!")
        st.info("Go to Manage App -> Settings -> Secrets and add your token.")
        st.stop()
        
    auth_token = st.secrets["NGROK_AUTH_TOKEN"]
    ngrok.set_auth_token(auth_token)

    # 2. Start QEMU (The Android Emulator)
    # -usb: Creates the USB controller (FIXES 'No usb-bus' ERROR)
    # -cpu qemu32: Uses 32-bit CPU (FIXES 'TCG' WARNINGS)
    # -m 256: Low RAM mode (FIXES CLOUD CRASHES)
    qemu_cmd = [
        "qemu-system-i386",
        "-m", "256",
        "-smp", "1",
        "-cpu", "qemu32",
        "-machine", "pc",
        "-usb",               # <--- This fixes your specific crash
        "-vga", "std",
        "-net", "nic,model=virtio", "-net", "user",
        "-cdrom", ISO_FILE,
        "-device", "usb-tablet",
        "-vnc", ":0",
        "-snapshot"
    ]
    
    # Launch QEMU in background
    qemu_proc = subprocess.Popen(qemu_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(4) # Wait for boot
    
    # Check if it died immediately
    if qemu_proc.poll() is not None:
        stdout, stderr = qemu_proc.communicate()
        st.error("🚨 QEMU Crashed! Error details:")
        st.code(stderr.decode())
        st.stop()

    # 3. Start Websockify (The Bridge)
    # Connects the web viewer to the emulator
    websockify_cmd = [
        sys.executable, "-m", "websockify", 
        str(NOVNC_PORT), "localhost:5900", 
        "--web", "./noVNC-1.4.0"
    ]
    subprocess.Popen(websockify_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 4. Create Internet Tunnel
    ngrok.kill() # Kill old tunnels
    public_url = ngrok.connect(NOVNC_PORT, "http").public_url
    return public_url

# --- 3. MAIN APP UI ---
setup_environment()

col1, col2 = st.columns([1, 3])

with col1:
    st.write("### 🎮 Controls")
    if st.button("▶️ Start Android", type="primary"):
        with st.spinner("Booting up (256MB RAM)..."):
            kill_existing_processes()
            try:
                url = start_system()
                st.session_state['android_url'] = url
                st.success("System Running!")
                time.sleep(1)
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Failed to start: {e}")

    st.markdown("---")
    st.info("""
    **Instructions:**
    1. Wait for black screen.
    2. Tap **'Live CD - VESA'**.
    3. If asked, choose **800x600** or **480x800**.
    4. **Scaling:** Open Left Menu ⚙️ -> Scaling -> **Remote Resizing**.
    """)

with col2:
    if 'android_url' in st.session_state:
        final_url = f"{st.session_state['android_url']}/vnc.html?autoconnect=true"
        st.write(f"🔗 [Direct Link to Phone]({final_url})")
        st.components.v1.iframe(final_url, height=850)
    else:
        st.warning("System is offline. Click 'Start Android' to boot.")


