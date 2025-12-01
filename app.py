import streamlit as st
import subprocess
import os
import time
import shutil

# --- CONFIGURATION ---
ISO_FILE = "android-x86-4.4-r5.iso"
ISO_URL = "https://sourceforge.net/projects/android-x86/files/Release%204.4/android-x86-4.4-r5.iso/download"
NOVNC_PORT = 6080
VNC_PORT = 5900

st.set_page_config(layout="wide", page_title="Streamlit Android")

st.title("📱 Android 4.4.4 on CPU")
st.markdown("Running pure x86 emulation. **Touch inputs enabled.**")

# --- HELPER FUNCTIONS ---

def download_files():
    """Downloads Android ISO and noVNC if they don't exist."""
    status_text = st.empty()
    
    # 1. Download Android ISO
    if not os.path.exists(ISO_FILE):
        status_text.info("Downloading Android 4.4.4 ISO (443MB)... This takes about 30s.")
        subprocess.run(["wget", "-q", "-O", ISO_FILE, ISO_URL], check=True)
    
    # 2. Setup noVNC (Web Viewer)
    if not os.path.exists("noVNC-1.4.0"):
        status_text.info("Setting up noVNC Interface...")
        subprocess.run("wget -q -O novnc.zip https://github.com/novnc/noVNC/archive/refs/tags/v1.4.0.zip", shell=True)
        subprocess.run("unzip -q novnc.zip && rm novnc.zip", shell=True)
        
        # Websockify
        subprocess.run("wget -q -O websockify.zip https://github.com/novnc/websockify/archive/refs/tags/v0.11.0.zip", shell=True)
        subprocess.run("unzip -q websockify.zip && rm websockify.zip", shell=True)
        subprocess.run("mv websockify-0.11.0 noVNC-1.4.0/utils/websockify", shell=True)
        
        # Symlink index
        if os.path.exists("noVNC-1.4.0/index.html"):
            os.remove("noVNC-1.4.0/index.html")
        subprocess.run("ln -s vnc.html noVNC-1.4.0/index.html", shell=True)
        
    status_text.success("System Ready!")
    time.sleep(1)
    status_text.empty()

def start_emulator():
    """Starts QEMU and websockify in the background."""
    
    # Check if QEMU is already running
    check = subprocess.run("pgrep -f qemu-system-i386", shell=True, stdout=subprocess.PIPE)
    if check.returncode == 0:
        st.sidebar.success("✅ Emulator Running")
        return

    st.sidebar.warning("🚀 Booting Emulator...")
    
    # 1. Start Websockify (Bridge VNC -> Web)
    # We bridge localhost:5900 (QEMU) to Port 6080
    subprocess.Popen(
        ["./noVNC-1.4.0/utils/novnc_proxy", "--vnc", "localhost:5900", "--listen", str(NOVNC_PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # 2. Start QEMU (Android)
    # -m 1024: 1GB RAM
    # -device usb-tablet: CRITICAL for mobile touch
    # -snapshot: Don't write to disk (saves storage)
    qemu_cmd = [
        "qemu-system-i386",
        "-m", "1024",
        "-smp", "1",
        "-cpu", "qemu64",
        "-vga", "std",
        "-net", "nic,model=virtio", "-net", "user",
        "-cdrom", ISO_FILE,
        "-device", "usb-tablet", 
        "-vnc", ":0",
        "-snapshot" 
    ]
    subprocess.Popen(qemu_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    time.sleep(5) # Give it a moment to boot
    st.experimental_rerun()

# --- MAIN APP LOGIC ---

# 1. Prepare Environment
download_files()

# 2. Controls
col1, col2 = st.columns([1, 3])

with col1:
    st.write("### Controls")
    if st.button("Start Android"):
        start_emulator()
    
    st.info("""
    **Instructions:**
    1. Click 'Start Android'.
    2. Wait for the screen on the right.
    3. Tap **'Live CD - VESA'**.
    4. If prompted for resolution, try **800x600** or **480x800**.
    """)

# 3. Display the Phone
with col2:
    # We embed the noVNC viewer running on localhost:6080 inside an iframe
    # Note: On Streamlit Cloud, localhost might need to be adjusted to the internal proxy, 
    # but for local/docker setups, this works. 
    # For Streamlit Cloud specifically, we use a relative path trick or rely on Streamlit's port exposure.
    
    st.write("### Screen")
    
    # We use an iframe to show the noVNC viewer
    # height=850 fits a vertical phone screen nicely
    st.components.v1.iframe(f"http://localhost:{NOVNC_PORT}/vnc.html?autoconnect=true", height=850)

