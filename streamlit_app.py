import streamlit as st
import subprocess
import os
import time
from pyngrok import ngrok

# --- CONFIGURATION ---
ISO_FILE = "android-x86-4.4-r5.iso"
ISO_URL = "https://sourceforge.net/projects/android-x86/files/Release%204.4/android-x86-4.4-r5.iso/download"
NOVNC_PORT = 6080

st.set_page_config(layout="wide", page_title="Android Cloud")

st.title("📱 Android 4.4.4 on Streamlit Cloud")

# --- 1. GET NGROK TOKEN ---
# We need this to tunnel the video out of the cloud server
auth_token = st.secrets.get("NGROK_AUTH_TOKEN")
if not auth_token:
    st.error("⚠️ Ngrok Auth Token missing! Please add it to Streamlit Secrets.")
    st.stop()

# --- 2. SETUP FUNCTIONS ---

def setup_environment():
    status = st.empty()
    
    # Download Android ISO
    if not os.path.exists(ISO_FILE):
        status.info("Downloading Android ISO...")
        subprocess.run(["wget", "-q", "-O", ISO_FILE, ISO_URL], check=True)
    
    # Download noVNC
    if not os.path.exists("noVNC-1.4.0"):
        status.info("Installing Web Viewer...")
        subprocess.run("wget -q -O novnc.zip https://github.com/novnc/noVNC/archive/refs/tags/v1.4.0.zip", shell=True)
        subprocess.run("unzip -q novnc.zip && rm novnc.zip", shell=True)
        subprocess.run("wget -q -O websockify.zip https://github.com/novnc/websockify/archive/refs/tags/v0.11.0.zip", shell=True)
        subprocess.run("unzip -q websockify.zip && rm websockify.zip", shell=True)
        subprocess.run("mv websockify-0.11.0 noVNC-1.4.0/utils/websockify", shell=True)
        subprocess.run("ln -s vnc.html noVNC-1.4.0/index.html", shell=True)

    status.empty()

def start_system():
    # A. Set Ngrok Token
    ngrok.set_auth_token(auth_token)

    # B. Start noVNC (The Bridge)
    # We bridge QEMU (5900) to Web (6080)
    subprocess.Popen(
        ["./noVNC-1.4.0/utils/novnc_proxy", "--vnc", "localhost:5900", "--listen", str(NOVNC_PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # C. Start QEMU (The Android Phone)
    qemu_cmd = [
        "qemu-system-i386",
        "-m", "1024",       # 1GB RAM
        "-smp", "1",        # 1 Core
        "-cpu", "qemu64",
        "-vga", "std",
        "-net", "nic,model=virtio", "-net", "user",
        "-cdrom", ISO_FILE,
        "-device", "usb-tablet", # Touch support
        "-vnc", ":0",
        "-snapshot"
    ]
    # Check if already running to avoid duplicates
    if subprocess.run("pgrep -f qemu-system-i386", shell=True).returncode != 0:
        subprocess.Popen(qemu_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(5) # Wait for boot

    # D. Create Tunnel
    # This gives us a public URL (e.g., http://random.ngrok-free.app)
    # We disconnect old tunnels first
    tunnels = ngrok.get_tunnels()
    public_url = None
    
    if not tunnels:
        public_url = ngrok.connect(NOVNC_PORT, "http").public_url
    else:
        public_url = tunnels[0].public_url

    return public_url

# --- 3. RUN APP ---
setup_environment()

col1, col2 = st.columns([1, 3])

with col1:
    if st.button("🚀 Start Android"):
        with st.spinner("Booting System & Creating Tunnel..."):
            try:
                url = start_system()
                st.session_state['android_url'] = url
                st.success("Running!")
            except Exception as e:
                st.error(f"Error: {e}")

    st.info("""
    **Controls:**
    1. Tap **'Live CD - VESA'**.
    2. Select resolution **800x600**.
    3. Open Side Menu -> Settings -> **Scale to Fit**.
    """)

with col2:
    if 'android_url' in st.session_state:
        # Display the phone in an iframe
        final_url = f"{st.session_state['android_url']}/vnc.html?autoconnect=true"
        st.write(f"Direct Link: [Open in new tab]({final_url})")
        st.components.v1.iframe(final_url, height=800)
    else:
        st.write("Click Start to boot the phone.")
